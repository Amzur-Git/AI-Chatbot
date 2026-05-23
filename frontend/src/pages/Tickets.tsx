/**
 * Tickets.tsx - Main page for ticket automation workflow
 * 
 * Features:
 * - Create new tickets with AI workflow
 * - View ticket history
 * - Filter and sort tickets
 * - Real-time updates
 */
import React, { useState } from "react";
import TicketForm from "../components/TicketForm";
import TicketList from "../components/TicketList";

const Tickets: React.FC = () => {
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"create" | "list">("list");
  const [ticketCount, setTicketCount] = useState(0);

  const handleTicketCreated = (ticket: any) => {
    // Show success message
    setSuccessMessage(
      `Ticket ${ticket.ticket_id} created! Check your email for confirmation.`
    );

    // Refresh the ticket list
    setRefreshTrigger((prev) => prev + 1);
    setActiveTab("list");

    // Clear message after 5 seconds
    setTimeout(() => setSuccessMessage(null), 5000);
  };

  const handleError = (error: string) => {
    setErrorMessage(error);
    setTimeout(() => setErrorMessage(null), 5000);
  };

  return (
    <div className="w-full min-h-screen bg-gray-50 py-8 px-4">
      {successMessage && (
        <div className="fixed top-4 right-4 z-50 max-w-sm rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700 shadow">
          {successMessage}
        </div>
      )}
      {errorMessage && (
        <div className="fixed top-4 right-4 z-50 max-w-sm rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 shadow">
          {errorMessage}
        </div>
      )}

      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-bold text-gray-900">Ticket Automation</h1>
          <p className="text-lg text-gray-600">
            Submit issues in natural language. Our AI workflow automatically
            extracts category, priority, and assigns teams.
          </p>
        </div>

        {/* Success notification */}
        {successMessage && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-green-700">
            <p className="font-semibold">✓ {successMessage}</p>
          </div>
        )}

        <div className="bg-white rounded-lg shadow-md p-3">
          <div className="flex gap-2 border-b border-gray-200 pb-3">
            <button
              type="button"
              onClick={() => setActiveTab("create")}
              className={`px-4 py-2 rounded-md text-sm font-semibold transition-colors ${
                activeTab === "create"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              Create Ticket
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("list")}
              className={`px-4 py-2 rounded-md text-sm font-semibold transition-colors ${
                activeTab === "list"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              My Tickets ({ticketCount})
            </button>
          </div>

          <div className="pt-4">
            {activeTab === "create" ? (
              <div className="max-w-3xl">
                <TicketForm
                  onTicketCreated={handleTicketCreated}
                  onError={handleError}
                />
              </div>
            ) : (
              <TicketList
                refreshTrigger={refreshTrigger}
                onTicketCountChange={setTicketCount}
              />
            )}
          </div>
        </div>

        {/* Info section */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 space-y-4">
          <h3 className="text-lg font-bold text-blue-900">
            How AI Workflow Automation Works
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-2">
              <div className="text-2xl">1️⃣</div>
              <p className="font-semibold text-blue-900">You Submit Issue</p>
              <p className="text-sm text-blue-800">
                Describe your issue in natural language via React form
              </p>
            </div>
            <div className="space-y-2">
              <div className="text-2xl">2️⃣</div>
              <p className="font-semibold text-blue-900">FastAPI Validates</p>
              <p className="text-sm text-blue-800">
                Backend securely validates and forwards to n8n (React never touches n8n)
              </p>
            </div>
            <div className="space-y-2">
              <div className="text-2xl">3️⃣</div>
              <p className="font-semibold text-blue-900">AI Agent Processes</p>
              <p className="text-sm text-blue-800">
                n8n AI Agent extracts category, priority, and team assignment
              </p>
            </div>
            <div className="space-y-2">
              <div className="text-2xl">4️⃣</div>
              <p className="font-semibold text-blue-900">Ticket Created</p>
              <p className="text-sm text-blue-800">
                Ticket stored in PostgreSQL, confirmation email sent to you
              </p>
            </div>
          </div>

          <div className="border-t border-blue-200 pt-4">
            <h4 className="font-semibold text-blue-900 mb-2">🔒 Security</h4>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>✓ React frontend cannot call n8n directly</li>
              <li>✓ FastAPI acts as secure boundary with JWT authentication</li>
              <li>✓ n8n webhook has secret validation</li>
              <li>✓ All data encrypted in transit and at rest</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Tickets;
