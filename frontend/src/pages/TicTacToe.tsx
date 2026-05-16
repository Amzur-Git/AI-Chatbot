import { useEffect, useState } from "react";

type GameState = {
  board: string[];
  current_player: string;
  game_over: boolean;
  winner: string | null;
  result: string | null; // "win", "loss", "draw"
  available_moves: number[];
};

const BOARD_SIZE = 3;
const API_BASE = "http://127.0.0.1:8011";

export default function TicTacToe() {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [moveInProgress, setMoveInProgress] = useState(false);
  const [wins, setWins] = useState(0);
  const [losses, setLosses] = useState(0);
  const [draws, setDraws] = useState(0);

  // Load initial game state
  useEffect(() => {
    loadGameState();
  }, []);

  const loadGameState = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API_BASE}/game/state`);
      if (!response.ok) throw new Error(`Backend error: ${response.status}`);
      const data = (await response.json()) as GameState;
      setGameState(data);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Failed to load game";
      console.error("TicTacToe error:", errorMsg, err);
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const makeMove = async (position: number) => {
    if (moveInProgress || !gameState || gameState.game_over) return;
    if (!gameState.available_moves.includes(position)) return;

    setMoveInProgress(true);
    try {
      const response = await fetch(`${API_BASE}/game/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ position }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to make move");
      }

      const data = (await response.json()) as {
        game_state: GameState;
        ai_move: number | null;
      };

      setGameState(data.game_state);

      // Update scores
      if (data.game_state.game_over) {
        if (data.game_state.result === "win") {
          setWins((prev) => prev + 1);
        } else if (data.game_state.result === "loss") {
          setLosses((prev) => prev + 1);
        } else if (data.game_state.result === "draw") {
          setDraws((prev) => prev + 1);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Move failed");
    } finally {
      setMoveInProgress(false);
    }
  };

  const resetGame = async () => {
    try {
      setMoveInProgress(true);
      const response = await fetch(`${API_BASE}/game/reset`, {
        method: "POST",
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Reset failed (${response.status}): ${errorText}`);
      }

      const data = (await response.json()) as {
        game_state: GameState;
      };

      setGameState(data.game_state);
      setError(null);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Reset failed";
      console.error("Reset error:", errorMsg);
      setError(errorMsg);
    } finally {
      setMoveInProgress(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 flex items-center justify-center p-4">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto mb-4"></div>
          <p className="text-slate-600">Loading Tic Tac Toe game...</p>
        </div>
      </div>
    );
  }

  if (!gameState) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 flex items-center justify-center p-4">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 max-w-md">
          <p className="text-red-700 font-semibold">{error || "Failed to load game"}</p>
          <button
            onClick={() => location.reload()}
            className="mt-4 w-full rounded-lg bg-red-600 px-4 py-2 text-white font-semibold hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 p-4 sm:p-6 lg:p-8">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-slate-900 mb-2">Tic Tac Toe Agent</h1>
          <p className="text-slate-600">Play against an AI opponent using minimax algorithm</p>
        </div>

        {/* Score Card */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-4 text-center">
            <div className="text-sm font-semibold text-emerald-700 mb-1">Wins</div>
            <div className="text-3xl font-bold text-emerald-600">{wins}</div>
          </div>
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-4 text-center">
            <div className="text-sm font-semibold text-slate-700 mb-1">Draws</div>
            <div className="text-3xl font-bold text-slate-600">{draws}</div>
          </div>
          <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-center">
            <div className="text-sm font-semibold text-red-700 mb-1">Losses</div>
            <div className="text-3xl font-bold text-red-600">{losses}</div>
          </div>
        </div>

        {/* Game Board */}
        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-lg mb-8">
          {/* Status */}
          <div className="mb-6 text-center">
            {gameState.game_over ? (
              <>
                {gameState.result === "win" && (
                  <div className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-4 py-2">
                    <span className="text-2xl">🎉</span>
                    <span className="font-semibold text-emerald-700">You won!</span>
                  </div>
                )}
                {gameState.result === "loss" && (
                  <div className="inline-flex items-center gap-2 rounded-full bg-red-100 px-4 py-2">
                    <span className="text-2xl">🤖</span>
                    <span className="font-semibold text-red-700">AI won!</span>
                  </div>
                )}
                {gameState.result === "draw" && (
                  <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-4 py-2">
                    <span className="text-2xl">🤝</span>
                    <span className="font-semibold text-slate-700">Draw!</span>
                  </div>
                )}
              </>
            ) : (
              <div className="text-lg font-semibold text-slate-700">
                Your turn (X)
              </div>
            )}
          </div>

          {/* Board Grid */}
          <div className="mb-8 flex justify-center">
            <div className="grid grid-cols-3 gap-3 bg-gradient-to-br from-slate-100 to-slate-200 p-4 rounded-lg shadow-md">
              {gameState.board.map((cell, index) => (
                <button
                  key={index}
                  onClick={() => makeMove(index)}
                  disabled={
                    moveInProgress ||
                    gameState.game_over ||
                    !gameState.available_moves.includes(index)
                  }
                  className={`w-20 h-20 rounded-lg font-bold text-4xl transition ${
                    cell === "X"
                      ? "bg-blue-500 text-white shadow-lg"
                      : cell === "O"
                        ? "bg-orange-500 text-white shadow-lg"
                        : "bg-white text-slate-400 hover:bg-slate-50 cursor-pointer shadow"
                  } ${
                    gameState.available_moves.includes(index) && !gameState.game_over
                      ? "hover:shadow-lg hover:scale-105"
                      : ""
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {cell && cell !== " " ? cell : ""}
                </button>
              ))}
            </div>
          </div>

          {/* Controls */}
          <div className="flex gap-3 justify-center">
            <button
              onClick={resetGame}
              disabled={moveInProgress}
              className="rounded-lg bg-purple-600 px-6 py-2 text-sm font-semibold text-white hover:bg-purple-700 transition disabled:opacity-60"
            >
              New Game
            </button>
            {error && (
              <button
                onClick={() => setError(null)}
                className="rounded-lg bg-slate-200 px-6 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-300 transition"
              >
                Clear Error
              </button>
            )}
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4">
            <p className="text-red-700 text-sm">{error}</p>
          </div>
        )}

        {/* Instructions */}
        <div className="rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">How to Play</h2>
          <ul className="space-y-2 text-sm text-slate-600">
            <li>• Click on any empty cell to make your move (X)</li>
            <li>• AI automatically responds with its move (O)</li>
            <li>• First player to get 3 in a row wins</li>
            <li>• AI uses minimax algorithm for optimal play</li>
            <li>• Click "New Game" to start a fresh game</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
