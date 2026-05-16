"""FastAPI application for Tic Tac Toe Agent."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app.services.game import TicTacToeGame, Player
from app.models import (
    GameStateResponse,
    MakeMoveRequest,
    MakeMoveResponse,
    ResetGameResponse,
)


# Global game instance
game = TicTacToeGame()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("🎮 Tic Tac Toe Agent starting...")
    yield
    # Shutdown
    print("🎮 Tic Tac Toe Agent shutting down...")


app = FastAPI(
    title="Tic Tac Toe Agent",
    description="Play Tic Tac Toe against an AI agent",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:8010").split(
    ","
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _game_state_to_response(game_state) -> GameStateResponse:
    """Convert game state to API response."""
    return GameStateResponse(
        board=game_state.board,
        current_player=game_state.current_player.value,
        game_over=game_state.game_over,
        winner=game_state.winner.value if game_state.winner else None,
        result=game_state.result,
        available_moves=game.get_available_moves(),
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "tic-tac-toe-agent", "version": "1.0.0"}


@app.get("/game/state")
async def get_game_state():
    """Get current game state."""
    return _game_state_to_response(game.get_state())


@app.post("/game/move")
async def make_move(request: MakeMoveRequest):
    """
    Make a player move and get AI response.

    Args:
        request: MakeMoveRequest with position (0-8)

    Returns:
        MakeMoveResponse with updated game state and AI's move
    """
    # Validate position
    if request.position < 0 or request.position > 8:
        raise HTTPException(status_code=400, detail="Position must be between 0 and 8")

    # Make player move
    if not game.make_move(request.position, Player.HUMAN):
        raise HTTPException(status_code=400, detail="Invalid move - position already occupied or game over")

    # Check if human won or board filled
    game_state = game.get_state()
    ai_move = None

    if game_state.game_over:
        return MakeMoveResponse(
            success=True,
            message="Game over",
            game_state=_game_state_to_response(game_state),
            ai_move=None,
        )

    # AI makes its move
    ai_move = game.get_best_move()
    if ai_move is not None:
        game.make_move(ai_move, Player.AI)

    game_state = game.get_state()

    return MakeMoveResponse(
        success=True,
        message="Move successful",
        game_state=_game_state_to_response(game_state),
        ai_move=ai_move,
    )


@app.post("/game/reset")
async def reset_game():
    """Reset the game to initial state."""
    game.reset()
    game_state = game.get_state()

    return ResetGameResponse(
        message="Game reset successfully",
        game_state=_game_state_to_response(game_state),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8011,
        log_level="info",
    )
