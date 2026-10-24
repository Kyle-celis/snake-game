"""
Reverse Snake — Multiplayer server.

- GRID 40x40 playing field
- Snake 1 (BIG) spawns at start, Snake 2 at 1min, Snake 3 at 2min, Snake 4 at 3min
- 10-second grace period before Snake 1 moves
- Winner = longest survivor
"""

from flask import Flask, send_from_directory, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import os

# ---------- CONFIG ----------
GRID = 40
TICK_MS = 50
BALL_TICKS = 3
SNAKE_TICKS = 3
WANDER = 0.20
MAX_PLAYERS = 5
GRACE_TICKS = 200
SPAWN_SNAKE_2_AT = 1200
SPAWN_SNAKE_3_AT = 2400
SPAWN_SNAKE_4_AT = 3600

COLORS = [
    '#ff4f79', '#4fc3f7', '#81c784', '#ffb74d', '#ba68c8',
]

SNAKE_CONFIGS = [
    {"length": 10, "size": 0.20, "head_size": 0.08},   # Snake 1 — BIG
    {"length": 8,  "size": 0.10, "head_size": 0.04},   # Snake 2 — normal
    {"length": 8,  "size": 0.10, "head_size": 0.04},   # Snake 3 — normal
    {"length": 8,  "size": 0.10, "head_size": 0.04},   # Snake 4 — normal
]


# ---------- APP ----------
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

rooms = {}


# ---------- HELPERS ----------
def request_sid():
    return request.sid


def make_code():
    while True:
        code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=6))
        if code not in rooms:
            return code


def inside(x, y):
    return 0 <= x < GRID and 0 <= y < GRID


def make_ball(index):
    spawns = [(30, 30), (10, 30), (30, 10), (10, 10), (20, 30), (20, 10)]
    x, y = spawns[index % len(spawns)]
    return {"x": x, "y": y, "alive": True}


def make_snake(config_index, grid_start_x, grid_start_y):
    config = SNAKE_CONFIGS[config_index]
    length = config["length"]
    return {
        "dir": {"x": 1, "y": 0},
        "body": [
            {"x": grid_start_x - i, "y": grid_start_y}
            for i in range(length)
        ],
        "config_index": config_index,
    }


def make_snakes_for_start():
    return [make_snake(0, 15, 5)]


def make_room():
    return {
        "code": None,
        "host": None,
        "players": {},
        "snakes": make_snakes_for_start(),
        "status": "waiting",
        "ticks": 0,
        "elapsed": 0.0,
        "winner": None,
        "spawned_snake_2": False,
        "spawned_snake_3": False,
        "spawned_snake_4": False,
    }


# ---------- GAME LOGIC ----------
def step_ball(ball, input_dir, room):
    if not ball["alive"]:
        return
    dx, dy = input_dir
    if not dx and not dy:
        return

    body_coords = []
    for snake in room["snakes"]:
        body_coords.extend((c["x"], c["y"]) for c in snake["body"][1:])

    for mx, my in [(dx, dy), (dx, 0), (0, dy)]:
        if not mx and not my:
            continue
        nx, ny = ball["x"] + mx, ball["y"] + my
        if inside(nx, ny) and (nx, ny) not in body_coords:
            ball["x"] = nx
            ball["y"] = ny
            return


def step_snake(snake, players):
    body = snake["body"]
    head = body[0]

    alive_balls = [p["ball"] for p in players.values() if p["ball"]["alive"]]
    if not alive_balls:
        return

    target = min(
        alive_balls,
        key=lambda b: abs(head["x"] - b["x"]) + abs(head["y"] - b["y"])
    )

    candidates = [
        {"x": snake["dir"]["x"], "y": snake["dir"]["y"]},
        {"x": -snake["dir"]["y"], "y": snake["dir"]["x"]},
        {"x": snake["dir"]["y"], "y": -snake["dir"]["x"]},
    ]

    valid = []
    body_except_tail = [(c["x"], c["y"]) for c in body[:-1]]
    for d in candidates:
        nx, ny = head["x"] + d["x"], head["y"] + d["y"]
        if inside(nx, ny) and (nx, ny) not in body_except_tail:
            valid.append(d)

    if not valid:
        return

    if random.random() < WANDER:
        chosen = random.choice(valid)
    else:
        chosen = min(
            valid,
            key=lambda d: abs(head["x"] + d["x"] - target["x"]) +
                          abs(head["y"] + d["y"] - target["y"])
        )

    snake["dir"] = chosen
    body.insert(0, {"x": head["x"] + chosen["x"], "y": head["y"] + chosen["y"]})
    body.pop()


def check_collisions(room):
    caught = []
    for snake in room["snakes"]:
        head = snake["body"][0]
        for sid, player in room["players"].items():
            b = player["ball"]
            if b["alive"] and b["x"] == head["x"] and b["y"] == head["y"]:
                b["alive"] = False
                player["survived_time"] = room["elapsed"]
                caught.append(sid)
    return caught


def maybe_spawn_snakes(room):
    if not room["spawned_snake_2"] and room["ticks"] >= SPAWN_SNAKE_2_AT:
        new_snake = make_snake(1, 30, 7)
        room["snakes"].append(new_snake)
        room["spawned_snake_2"] = True
        socketio.emit("snake_spawned", {"count": len(room["snakes"])}, to=room["code"])

    if not room["spawned_snake_3"] and room["ticks"] >= SPAWN_SNAKE_3_AT:
        new_snake = make_snake(2, 30, 30)
        room["snakes"].append(new_snake)
        room["spawned_snake_3"] = True
        socketio.emit("snake_spawned", {"count": len(room["snakes"])}, to=room["code"])

    if not room["spawned_snake_4"] and room["ticks"] >= SPAWN_SNAKE_4_AT:
        new_snake = make_snake(3, 10, 30)
        room["snakes"].append(new_snake)
        room["spawned_snake_4"] = True
        socketio.emit("snake_spawned", {"count": len(room["snakes"])}, to=room["code"])


def build_state(room):
    grace_remaining = max(0, (GRACE_TICKS - room["ticks"]) * TICK_MS / 1000)
    return {
        "snakes": [
            {
                "body": s["body"],
                "config_index": s["config_index"],
            }
            for s in room["snakes"]
        ],
        "grace_remaining": round(grace_remaining, 1),
        "players": {
            sid: {
                "name": p["name"],
                "color": p["color"],
                "ball": p["ball"],
                "survived_time": round(p["survived_time"], 1),
            }
            for sid, p in room["players"].items()
        },
        "elapsed": round(room["elapsed"], 1),
        "status": room["status"],
        "winner": room["winner"],
    }


def game_tick(room_code):
    room = rooms.get(room_code)
    if not room or room["status"] != "playing":
        return

    room["ticks"] += 1
    room["elapsed"] = room["ticks"] * TICK_MS / 1000

    if room["ticks"] % BALL_TICKS == 0:
        for p in room["players"].values():
            step_ball(p["ball"], p["direction"], room)

    maybe_spawn_snakes(room)

    if room["ticks"] > GRACE_TICKS and room["ticks"] % SNAKE_TICKS == 0:
        for snake in room["snakes"]:
            step_snake(snake, room["players"])

    caught = check_collisions(room)
    for sid in caught:
        socketio.emit("player_caught", {"player_id": sid}, to=room_code)

    alive = [sid for sid, p in room["players"].items() if p["ball"]["alive"]]
    if len(alive) == 0:
        room["status"] = "finished"
        winner_sid = max(
            room["players"].items(),
            key=lambda item: item[1]["survived_time"]
        )[0]
        room["winner"] = winner_sid

        results = [
            {
                "name": p["name"],
                "time": round(p["survived_time"], 1),
                "socket_id": sid,
            }
            for sid, p in room["players"].items()
        ]
        results.sort(key=lambda r: r["time"], reverse=True)

        socketio.emit("game_over", {
            "winner": winner_sid,
            "winner_name": room["players"][winner_sid]["name"],
            "results": results,
            "elapsed": round(room["elapsed"], 1),
        }, to=room_code)
        return

    socketio.emit("game_state", build_state(room), to=room_code)


def game_loop():
    while True:
        for code in list(rooms.keys()):
            try:
                game_tick(code)
            except Exception as e:
                print(f"[ERROR] room {code}: {e}")
        socketio.sleep(TICK_MS / 1000)


# ---------- SOCKET EVENTS ----------
@socketio.on("create_room")
def handle_create_room(data):
    name = (data.get("name") or "Player").strip()[:20]
    code = make_code()

    room = make_room()
    room["code"] = code
    room["host"] = request_sid()

    room["players"][request_sid()] = {
        "name": name,
        "color": COLORS[0],
        "ball": make_ball(0),
        "direction": [0, 0],
        "survived_time": 0.0,
    }

    rooms[code] = room
    join_room(code)

    emit("room_created", {
        "code": code,
        "color": COLORS[0],
        "players": list(room["players"].values()),
    })


@socketio.on("join_room")
def handle_join_room(data):
    code = (data.get("code") or "").strip().upper()
    name = (data.get("name") or "Player").strip()[:20]

    room = rooms.get(code)
    if not room:
        emit("error", {"message": "Room not found"})
        return
    if room["status"] != "waiting":
        emit("error", {"message": "Game already started"})
        return
    if len(room["players"]) >= MAX_PLAYERS:
        emit("error", {"message": "Room is full"})
        return

    index = len(room["players"])
    room["players"][request_sid()] = {
        "name": name,
        "color": COLORS[index],
        "ball": make_ball(index),
        "direction": [0, 0],
        "survived_time": 0.0,
    }

    join_room(code)

    emit("room_joined", {
        "code": code,
        "color": COLORS[index],
        "players": list(room["players"].values()),
    }, to=request_sid())

    socketio.emit("player_joined", {
        "players": list(room["players"].values()),
    }, to=code)


@socketio.on("start_game")
def handle_start_game():
    sid = request_sid()
    for code, room in rooms.items():
        if sid in room["players"]:
            if room["host"] != sid:
                emit("error", {"message": "Only host can start"})
                return
            room["status"] = "playing"
            room["ticks"] = 0
            room["elapsed"] = 0.0
            room["snakes"] = make_snakes_for_start()
            room["spawned_snake_2"] = False
            room["spawned_snake_3"] = False
            room["spawned_snake_4"] = False
            for p in room["players"].values():
                p["survived_time"] = 0.0
                p["ball"]["alive"] = True
            socketio.emit("game_started", build_state(room), to=code)
            return
    emit("error", {"message": "You are not in a room"})


@socketio.on("input")
def handle_input(data):
    sid = request_sid()
    dx = data.get("dx", 0)
    dy = data.get("dy", 0)
    for room in rooms.values():
        if sid in room["players"]:
            room["players"][sid]["direction"] = [dx, dy]
            return


@socketio.on("disconnect")
def handle_disconnect():
    sid = request_sid()
    for code, room in list(rooms.items()):
        if sid in room["players"]:
            del room["players"][sid]
            leave_room(code)
            if not room["players"]:
                del rooms[code]
            else:
                socketio.emit("player_left", {
                    "players": list(room["players"].values()),
                }, to=code)
            break


# ---------- HTTP ROUTES ----------
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ---------- RUN ----------
if __name__ == "__main__":
    print("Starting Reverse Snake server on port 5001...")
    socketio.start_background_task(game_loop)
    socketio.run(app, host="0.0.0.0", port=5001, debug=False)