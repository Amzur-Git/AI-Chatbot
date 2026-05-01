import { useState, useEffect, type FormEvent } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { authService } from "./services/auth";
import { chatService } from "./services/chat";
import Login from "./components/Login";
import AuthCallback from "./components/AuthCallback";
import type { ChatMessage, User } from "./types";

function ChatApp() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);

  useEffect(() => {
    const initializeChat = async () => {
      try {
        const currentUser = await authService.getCurrentUser();
        setUser(currentUser);

        const history = await chatService.getChatHistory();
        setMessages(history.map((item) => ({
          id: item.id,
          role: item.role as "user" | "assistant" | "system",
          content: item.content,
          created_at: item.created_at,
        })));
      } catch (err) {
        setError("Unable to load your account or chat history. Please login again.");
      } finally {
        setLoadingHistory(false);
      }
    };

    initializeChat();
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!input.trim()) return;

    const userMessage: ChatMessage = { role: "user", content: input.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const data = await chatService.sendMessage(userMessage.content);
      const assistantMessage: ChatMessage = { role: "assistant", content: data.answer };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError("Unable to send message. Please try again.");
      // Remove the user message if sending failed
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    authService.logout();
    setUser(null);
    setMessages([]);
    window.location.href = '/login';
  };

  if (loadingHistory) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-slate-600">Loading chat history...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-3xl p-8">
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-3xl font-bold">Gemini Chatbot</h1>
          <div className="flex items-center gap-4">
            {user && (
              <span className="text-sm text-slate-600">
                Welcome, {user.name}
              </span>
            )}
            <button
              onClick={handleLogout}
              className="bg-red-600 hover:bg-red-700 text-white text-sm font-semibold py-2 px-4 rounded-2xl transition"
            >
              Logout
            </button>
          </div>
        </div>
        <p className="mt-2 text-slate-600">Ask the model a question and receive an answer from the backend.</p>

        <div className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="space-y-4">
            {messages.length === 0 && (
              <div className="text-center text-slate-500 py-8">
                <p>No messages yet. Start a conversation!</p>
              </div>
            )}
            {messages.map((message, index) => (
              <div key={message.id || index} className={message.role === "user" ? "text-right" : "text-left"}>
                <div className="inline-block rounded-2xl px-4 py-3 text-sm shadow-sm" style={{ backgroundColor: message.role === "user" ? "#2563eb" : "#f8fafc", color: message.role === "user" ? "white" : "#0f172a" }}>
                  {message.content}
                </div>
                {message.created_at && (
                  <div className="text-xs text-slate-400 mt-1">
                    {new Date(message.created_at).toLocaleString()}
                  </div>
                )}
              </div>
            ))}
          </div>

          <form className="mt-6 flex gap-3" onSubmit={handleSubmit}>
            <input
              className="flex-1 rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 focus:border-slate-500 focus:outline-none"
              placeholder="Type your question..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            <button
              type="submit"
              className="rounded-2xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
              disabled={loading}
            >
              {loading ? "Sending..." : "Send"}
            </button>
          </form>

          {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
        </div>
      </div>
    </div>
  );
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const checkAuth = async () => {
      if (!authService.isAuthenticated()) {
        setIsAuthenticated(false);
        return;
      }

      try {
        await authService.getCurrentUser();
        setIsAuthenticated(true);
      } catch {
        authService.logout();
        setIsAuthenticated(false);
      }
    };

    checkAuth();
  }, []);

  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <Router>
      <Routes>
        <Route
          path="/login"
          element={isAuthenticated ? <Navigate to="/" replace /> : <Login />}
        />
        <Route
          path="/auth/callback"
          element={<AuthCallback />}
        />
        <Route
          path="/"
          element={isAuthenticated ? <ChatApp /> : <Navigate to="/login" replace />}
        />
      </Routes>
    </Router>
  );
}

export default App;
