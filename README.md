# Reverse Snake 🐍

A multiplayer twist on the classic Snake game. In the original, you control the snake and eat the ball to score. In **Reverse Snake**, the roles are flipped: **you are the ball**, and you have to run away from the snake for as long as you can.

Play with up to 5 friends in the same room and see who survives the longest.

## How It Works

- Players join a room using a 6-character room code and play as colored balls on a 40×40 grid.
- The host starts the game. The snake stays still for a **10-second grace period** so everyone can get into position.
- The snake chases the nearest ball, with a bit of random wandering so it isn't perfectly predictable.
- **More snakes join over time:**

  | Time | What happens |
  |------|--------------|
  | 0:00 | Snake 1 (the big one) appears |
  | 1:00 | Snake 2 appears |
  | 2:00 | Snake 3 appears |
  | 3:00 | Snake 4 appears |

- If a snake's head touches your ball, you're out. Snake bodies also block your movement.
- The game ends when every ball is caught. **The longest survivor wins.**

## Features

- Real-time multiplayer with WebSockets (Flask-SocketIO)
- Room creation and joining with shareable codes (up to 5 players per room)
- Server-side game loop (20 ticks per second), so all players see the same game state
- Keyboard controls on desktop and a touch joystick on mobile
- Results screen with rankings and survival times

## Tech Stack

- **Backend:** Python, Flask, Flask-SocketIO, eventlet
- **Frontend:** HTML, CSS, JavaScript (Canvas API, Socket.IO client)
- **Deployment:** Linux VPS with nginx as a reverse proxy and systemd to keep the server running

## Project Structure

```
snake-game/
├── backend/
│   ├── snake_server.py     # Game server and game logic
│   └── requirements.txt    # Python dependencies
└── frontend/
    └── index.html          # Game client (served by the Flask server)
```

## Getting Started

### Prerequisites

- Python 3.10 or newer
- A modern web browser

### Run locally

```bash
git clone https://github.com/Kyle-celis/snake-game.git
cd snake-game/backend

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 snake_server.py
```

Then open **http://localhost:5001** in your browser.

### Play with friends on the same network

Open `http://<your-computer-ip>:5001` on the other devices (find your IP with `hostname -I`).

## Controls

| Device | Controls |
|--------|----------|
| Desktop | Arrow keys or **W A S D** |
| Mobile | On-screen joystick |

## Configuration

Game settings are at the top of `backend/snake_server.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `GRID` | 40 | Size of the board |
| `MAX_PLAYERS` | 5 | Players per room |
| `GRACE_TICKS` | 200 | Delay before the snake moves (10 seconds) |
| `WANDER` | 0.20 | Chance the snake moves randomly instead of chasing |
| `SPAWN_SNAKE_2_AT` / `_3_AT` / `_4_AT` | 1200 / 2400 / 3600 | When extra snakes appear (in ticks, 20 ticks = 1 second) |

## Deployment

The game is designed to run on a Linux VPS:

1. Run `snake_server.py` as a **systemd** service on port 5001.
2. Put **nginx** in front of it as a reverse proxy, with the `Upgrade` and `Connection` headers set so WebSockets work.
3. Add HTTPS with Let's Encrypt (`certbot --nginx`).

Rooms are stored in the server's memory, so run it as a **single process** (no multiple workers).

## Author

**Kyle Celis**: [GitHub](https://github.com/Kyle-celis) · [LinkedIn](https://www.linkedin.com/in/kylecelis6b7b4632b)
