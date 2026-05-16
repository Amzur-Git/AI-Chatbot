"""Pydantic models for API requests and responses."""
from pydantic import BaseModel
from typing import Optional


class GameStateResponse(BaseModel):
    """Response containing game state."""
    board: list[str]
    current_player: str
    game_over: bool
    winner: Optional[str] = None
    result: Optional[str] = None  # "win", "loss", "draw"
    available_moves: list[int]


class MakeMoveRequest(BaseModel):
    """Request to make a move."""
    position: int  # 0-8


class MakeMoveResponse(BaseModel):
    """Response after making a move."""
    success: bool
    message: str
    game_state: GameStateResponse
    ai_move: Optional[int] = None


class ResetGameResponse(BaseModel):
    """Response after resetting game."""
    message: str
    game_state: GameStateResponse
