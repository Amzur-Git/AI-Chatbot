/**
 * TicketForm.tsx - Component for creating tickets via AI workflow automation
 * 
 * Features:
 * - Natural language issue submission
 * - Real-time validation
 * - Character counter
 * - Loading state during n8n workflow
 * - Error handling
 */
import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ticketService } from "../services/tickets";

interface TicketFormProps {
  onTicketCreated?: (ticket: any) => void;
  onError?: (error: string) => void;
}

const TicketForm: React.FC<TicketFormProps> = ({ onTicketCreated, onError }) => {
  let defaultEmail = "";
  try {
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
      defaultEmail = JSON.parse(storedUser).email || "";
    }
  } catch {
    defaultEmail = "";
  }
  const [userEmail, setUserEmail] = useState(defaultEmail);
  const [issue, setIssue] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [charCount, setCharCount] = useState(0);

  const MIN_CHARS = 10;
  const MAX_CHARS = 5000;

  const handleIssueChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = e.target.value;
    setIssue(text);
    setCharCount(text.length);
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    // Validation
    if (!userEmail.trim() || !userEmail.includes("@")) {
      setError("Valid user email is required");
      return;
    }

    if (issue.trim().length < MIN_CHARS) {
      setError(`Issue must be at least ${MIN_CHARS} characters`);
      return;
    }

    if (issue.length > MAX_CHARS) {
      setError(`Issue cannot exceed ${MAX_CHARS} characters`);
      return;
    }

    setLoading(true);

    try {
      const ticket = await ticketService.createTicket({
        action: "create",
        user_email: userEmail.trim(),
        message: issue.trim(),
      });
      setSuccess(true);
      setUserEmail(userEmail.trim());
      setIssue("");
      setCharCount(0);

      // Notify parent component
      if (onTicketCreated) {
        onTicketCreated(ticket);
      }

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      if (onError) {
        onError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  const charPercentage = (charCount / MAX_CHARS) * 100;
  const isValid = charCount >= MIN_CHARS && charCount <= MAX_CHARS;

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl">
      <div className="bg-white rounded-lg shadow-md p-6 space-y-4">
        <div>
          <label
            htmlFor="issue"
            className="block text-sm font-semibold text-gray-700 mb-2"
          >
            Describe Your Issue
          </label>
          <p className="text-xs text-gray-500 mb-3">
            Be specific and detailed. Our AI workflow will automatically extract
            category, priority, and assign the appropriate team.
          </p>
          <textarea
            id="issue"
            value={issue}
            onChange={handleIssueChange}
            placeholder="Example: Login page is not loading on mobile devices, shows blank screen after tap..."
            className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 transition-all ${
              error
                ? "border-red-500 focus:ring-red-500"
                : isValid
                  ? "border-green-500 focus:ring-green-500"
                  : "border-gray-300 focus:ring-blue-500"
            }`}
            rows={6}
            disabled={loading}
          />
        </div>

        {/* Character counter and progress bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs text-gray-600">
            <span>
              {charCount} / {MAX_CHARS} characters
            </span>
            <span>
              {charCount < MIN_CHARS ? (
                <span className="text-red-600">
                  {MIN_CHARS - charCount} more required
                </span>
              ) : (
                <span className="text-green-600">✓ Ready</span>
              )}
            </span>
          </div>
          <div className="w-full h-1 bg-gray-200 rounded-full overflow-hidden">
            <motion.div
              className={`h-full ${
                charCount < MIN_CHARS
                  ? "bg-red-500"
                  : charCount <= MAX_CHARS
                    ? "bg-green-500"
                    : "bg-red-500"
              }`}
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(charPercentage, 100)}%` }}
              transition={{ duration: 0.3 }}
            />
          </div>
        </div>

        {/* Error message */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700"
            >
              ⚠️ {error}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Success message */}
        <AnimatePresence>
          {success && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-700"
            >
              ✓ Ticket created successfully! Check your email for confirmation.
            </motion.div>
          )}
        </AnimatePresence>

        {/* Submit button */}
        <button
          type="submit"
          disabled={!isValid || loading}
          className={`w-full py-3 px-4 rounded-lg font-semibold transition-all duration-200 ${
            loading
              ? "bg-gray-400 cursor-not-allowed"
              : isValid
                ? "bg-blue-600 hover:bg-blue-700 text-white cursor-pointer"
                : "bg-gray-300 text-gray-500 cursor-not-allowed"
          }`}
        >
          {loading ? (
            <div className="flex items-center justify-center gap-2">
              <svg
                className="animate-spin h-5 w-5"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Processing with AI...
            </div>
          ) : (
            "Create Ticket"
          )}
        </button>

        {/* Info section */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-700 space-y-1">
          <p className="font-semibold">🔒 Secure AI Workflow</p>
          <p>
            Your issue is securely sent to FastAPI, which safely processes it
            through our n8n AI workflow. You'll receive a confirmation email with
            your ticket ID and assigned team.
          </p>
        </div>
      </div>
    </form>
  );
};

export default TicketForm;
