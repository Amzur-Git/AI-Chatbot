import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import axios from "axios";
import api from "../services/api";

type TicketDetail = {
  ticket_id: number;
  issue: string | null;
  category: string | null;
  priority: string | null;
  assigned_team: string | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
};

const TicketDetailPage: React.FC = () => {
  const { ticketId } = useParams<{ ticketId: string }>();
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadTicket = async () => {
      if (!ticketId) {
        setError("Ticket id is missing");
        setLoading(false);
        return;
      }

      try {
        const response = await api.get(`/api/tickets/${encodeURIComponent(ticketId)}`);
        const data = response.data;
        setTicket(data);
      } catch (err) {
        let message = "Failed to load ticket";
        if (axios.isAxiosError(err)) {
          message =
            (err.response?.data as { detail?: string } | undefined)?.detail ||
            err.message ||
            message;
        } else if (err instanceof Error) {
          message = err.message;
        }
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    void loadTicket();
  }, [ticketId]);

  const formatDate = (value: string | null) => {
    if (!value) {
      return "-";
    }
    const date = new Date(value);
    return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4 sm:p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Ticket Details</h1>
          <Link to="/tickets" className="text-sm font-semibold text-blue-600 hover:text-blue-700">
            Back to Tickets
          </Link>
        </div>

        {loading && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <p className="text-gray-600">Loading ticket...</p>
          </div>
        )}

        {!loading && error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <p className="font-semibold text-red-700">Unable to load ticket</p>
            <p className="text-sm text-red-600 mt-1">{error}</p>
          </div>
        )}

        {!loading && !error && ticket && (
          <div className="bg-white rounded-lg shadow-md p-6 space-y-5">
            <div>
              <p className="text-sm text-gray-500">Ticket</p>
              <p className="text-xl font-bold text-gray-900">TKT-{ticket.ticket_id}</p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Category</p>
                <p className="font-semibold text-gray-800">{ticket.category || "N/A"}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Priority</p>
                <p className="font-semibold text-gray-800">{ticket.priority || "N/A"}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Status</p>
                <p className="font-semibold text-gray-800">{ticket.status.replace("_", " ")}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Assigned Team</p>
                <p className="font-semibold text-gray-800">{ticket.assigned_team || "N/A"}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Created</p>
                <p className="font-semibold text-gray-800">{formatDate(ticket.created_at)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Updated</p>
                <p className="font-semibold text-gray-800">{formatDate(ticket.updated_at)}</p>
              </div>
            </div>

            <div>
              <p className="text-sm text-gray-500">Issue Description</p>
              <p className="mt-2 text-gray-800 whitespace-pre-wrap">{ticket.issue || "No description provided."}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TicketDetailPage;
