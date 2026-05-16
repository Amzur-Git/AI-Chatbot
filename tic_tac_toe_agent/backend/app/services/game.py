"""Tic Tac Toe game logic and AI agent."""
from enum import Enum
from typing import Optional, Tuple
from dataclasses import dataclass


class Player(str, Enum):
    """Players: Human (X) and AI (O)."""
    HUMAN = "X"
    AI = "O"
    EMPTY = " "


@dataclass
class GameState:
    """Represents the current game state."""
    board: list[str]  # 9-element list representing 3x3 board
    current_player: Player
    game_over: bool = False
    winner: Optional[Player] = None
    result: Optional[str] = None  # "win", "loss", "draw"


class TicTacToeGame:
    """Tic Tac Toe game with minimax AI."""

    WINNING_COMBINATIONS = [
        [0, 1, 2],  # Top row
        [3, 4, 5],  # Middle row
        [6, 7, 8],  # Bottom row
        [0, 3, 6],  # Left column
        [1, 4, 7],  # Center column
        [2, 5, 8],  # Right column
        [0, 4, 8],  # Diagonal
        [2, 4, 6],  # Anti-diagonal
    ]

    def __init__(self):
        """Initialize a new game."""
        self.board = [Player.EMPTY.value for _ in range(9)]

    def is_board_full(self) -> bool:
        """Check if board is full."""
        return all(cell != Player.EMPTY.value for cell in self.board)

    def get_winner(self) -> Optional[Player]:
        """Check if there's a winner. Returns Player.HUMAN, Player.AI, or None."""
        for combo in self.WINNING_COMBINATIONS:
            if (
                self.board[combo[0]] == self.board[combo[1]] == self.board[combo[2]]
                and self.board[combo[0]] != Player.EMPTY.value
            ):
                return Player(self.board[combo[0]])
        return None

    def is_game_over(self) -> Tuple[bool, Optional[Player]]:
        """Check if game is over. Returns (is_over, winner)."""
        winner = self.get_winner()
        if winner:
            return True, winner
        if self.is_board_full():
            return True, None
        return False, None

    def get_available_moves(self) -> list[int]:
        """Get list of available move positions."""
        return [i for i, cell in enumerate(self.board) if cell == Player.EMPTY.value]

    def make_move(self, position: int, player: Player) -> bool:
        """
        Make a move at the given position for the player.
        Returns True if move was valid, False otherwise.
        """
        if position < 0 or position > 8 or self.board[position] != Player.EMPTY.value:
            return False
        self.board[position] = player.value
        return True

    def get_state(self) -> GameState:
        """Get current game state."""
        game_over, winner = self.is_game_over()
        result = None
        if game_over:
            if winner == Player.HUMAN:
                result = "win"
            elif winner == Player.AI:
                result = "loss"
            else:
                result = "draw"

        return GameState(
            board=self.board.copy(),
            current_player=Player.HUMAN if not game_over else (Player.HUMAN if winner != Player.AI else Player.AI),
            game_over=game_over,
            winner=winner,
            result=result,
        )

    def minimax(self, player: Player, depth: int = 0) -> int:
        """
        Minimax algorithm to evaluate board position.
        Returns score: 10-depth if AI wins, -(10-depth) if human wins, 0 for draw.
        """
        game_over, winner = self.is_game_over()

        if game_over:
            if winner == Player.AI:
                return 10 - depth
            elif winner == Player.HUMAN:
                return -(10 - depth)
            else:
                return 0

        if player == Player.AI:
            # Maximizing player
            max_score = -float("inf")
            for move in self.get_available_moves():
                self.board[move] = Player.AI.value
                score = self.minimax(Player.HUMAN, depth + 1)
                self.board[move] = Player.EMPTY.value
                max_score = max(score, max_score)
            return max_score
        else:
            # Minimizing player
            min_score = float("inf")
            for move in self.get_available_moves():
                self.board[move] = Player.HUMAN.value
                score = self.minimax(Player.AI, depth + 1)
                self.board[move] = Player.EMPTY.value
                min_score = min(score, min_score)
            return min_score

    def get_best_move(self) -> Optional[int]:
        """
        Find best move for AI using minimax algorithm.
        Returns the position (0-8) or None if no valid moves.
        """
        available_moves = self.get_available_moves()
        if not available_moves:
            return None

        best_score = -float("inf")
        best_move = available_moves[0]

        for move in available_moves:
            self.board[move] = Player.AI.value
            score = self.minimax(Player.HUMAN)
            self.board[move] = Player.EMPTY.value

            if score > best_score:
                best_score = score
                best_move = move

        return best_move

    def reset(self):
        """Reset game to initial state."""
        self.board = [Player.EMPTY.value for _ in range(9)]
