# Tic Tac Toe Agent Backend

FastAPI-based Tic Tac Toe game with minimax AI agent.

## Running the Backend

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run the server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8011 --reload
```

Server runs at: http://127.0.0.1:8011

## API Endpoints

- `GET /health` - Health check
- `GET /game/state` - Get current game state
- `POST /game/move` - Make a move (position 0-8)
- `POST /game/reset` - Reset the game

## Game Rules

- Human plays as X, AI plays as O
- Board positions are numbered 0-8 (left to right, top to bottom)
- First player to get 3 in a row wins
- AI uses minimax algorithm for optimal play
