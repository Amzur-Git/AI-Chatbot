# Tic Tac Toe Agent

A complete Tic Tac Toe game application with an AI agent powered by the minimax algorithm. Play against an unbeatable AI opponent integrated into your existing application.

## Project Structure

```
tic_tac_toe_agent/
├── backend/                    # FastAPI backend server
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app and routes
│   │   ├── models.py          # Pydantic schemas
│   │   └── services/
│   │       ├── __init__.py
│   │       └── game.py        # Game logic and minimax AI
│   ├── requirements.txt
│   ├── .env
│   ├── start.ps1              # Startup script
│   └── README.md
└── README.md
```

## Features

- **Minimax AI Algorithm**: Optimal AI opponent that never loses
- **Real-time Game State**: Instant feedback on moves and game status
- **Score Tracking**: Win/loss/draw statistics
- **Responsive UI**: Beautiful Tailwind CSS interface
- **RESTful API**: Clean API design for game operations
- **Authentication**: Integrated with existing auth system

## Backend Setup

```bash
cd tic_tac_toe_agent/backend

# Create virtual environment (if not exists)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run the server
./start.ps1
# or manually:
python -m uvicorn app.main:app --host 127.0.0.1 --port 8011 --reload
```

Server runs at: **http://127.0.0.1:8011**

API Docs: **http://127.0.0.1:8011/docs**

## Frontend Integration

The game is integrated into the main application at `localhost:5173/tic-tac-toe`

- Click "Tic Tac Toe Agent" button in the header (🎮 icon)
- Play against the AI by clicking cells on the 3x3 board
- Track your win/loss/draw statistics
- Start new games anytime

## API Reference

### GET /health
Health check endpoint.

```bash
curl http://127.0.0.1:8011/health
```

### GET /game/state
Get the current game state.

```bash
curl http://127.0.0.1:8011/game/state
```

Response:
```json
{
  "board": [" ", " ", " ", " ", " ", " ", " ", " ", " "],
  "current_player": "Player.HUMAN",
  "game_over": false,
  "winner": null,
  "result": null,
  "available_moves": [0, 1, 2, 3, 4, 5, 6, 7, 8]
}
```

### POST /game/move
Make a player move (position 0-8).

```bash
curl -X POST http://127.0.0.1:8011/game/move \
  -H "Content-Type: application/json" \
  -d '{"position": 4}'
```

Response:
```json
{
  "success": true,
  "message": "Move successful",
  "game_state": { ... },
  "ai_move": 0
}
```

### POST /game/reset
Reset the game to initial state.

```bash
curl -X POST http://127.0.0.1:8011/game/reset
```

## Game Rules

- **Players**: Human (X) vs AI (O)
- **Board**: 3x3 grid with positions 0-8
- **Winning**: First to get 3 in a row (horizontal, vertical, or diagonal)
- **Draw**: All cells filled with no winner
- **AI Strategy**: Uses minimax with depth-based scoring

## Board Position Reference

```
0 | 1 | 2
---------
3 | 4 | 5
---------
6 | 7 | 8
```

## Technologies

- **Backend**: FastAPI, Pydantic, Python
- **Frontend**: React 18, TypeScript, Tailwind CSS
- **AI**: Minimax algorithm
- **API**: RESTful with CORS support
- **Deployment**: Uvicorn ASGI server

## Port Configuration

- Backend: 8011
- Frontend (Vite): 5173
- Other services: 8001 (data query), 8010 (research digest)

## No Breaking Changes

This project is fully integrated into the existing application:
- ✅ Main app continues to run on port 5173
- ✅ Authentication system is preserved
- ✅ All existing routes and features work unchanged
- ✅ New button added to header for easy access
- ✅ Isolated backend on separate port (8011)

## Future Enhancements

- [ ] LLM-based strategy explanation
- [ ] Difficulty levels (easy/medium/hard)
- [ ] Game history and replays
- [ ] Multiplayer support
- [ ] Different game modes (variants)
- [ ] Mobile-optimized UI

## License

Part of the AI Training application suite.
