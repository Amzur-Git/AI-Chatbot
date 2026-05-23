/**
 * TicketList.tsx - Table view for user's tickets with inline status updates
 */
import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { ticketService } from "../services/tickets";

interface Ticket {
  ticket_id: number;
  issue: string | null;
  category: string | null;
  priority: string | null;
  assigned_team: string | null;
  status: "open" | "in_progress" | "resolved" | "closed";
  created_at: string | null;
  updated_at?: string | null;
}

interface TicketStatusUpdateResponse {
  email_sent?: boolean | null;
  email_message?: string | null;
}

type StatusFilter = "all" | "open" | "in_progress" | "resolved" | "closed";
type PrioritySort = "all" | "critical" | "high" | "medium" | "low";

interface TicketListProps {
  refreshTrigger?: number;
  onTicketSelect?: (ticket: Ticket) => void;
  onTicketCountChange?: (count: number) => void;
}

const normalizeStatus = (value: string | null | undefined): Ticket["status"] => {
  const normalized = (value || "").toString().trim().toLowerCase().replace(/\s+/g, "_");
  switch (normalized) {
    case "open":
      return "open";
    case "in_progress":
      return "in_progress";
    case "resolved":
      return "resolved";
    case "closed":
      return "closed";
    default:
      return "open";
  }
};

const TicketList: React.FC<TicketListProps> = ({
  refreshTrigger,
  onTicketSelect,
  onTicketCountChange,
}) => {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusNotice, setStatusNotice] = useState<string | null>(null);
  const [statusNoticeType, setStatusNoticeType] = useState<"success" | "warning">("success");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [prioritySort, setPrioritySort] = useState<PrioritySort>("all");
  const [updatingTicketIds, setUpdatingTicketIds] = useState<Set<number>>(new Set());

  const priorityOrder: Record<string, number> = {
    critical: 4,
    high: 3,
    medium: 2,
    low: 1,
  };

  const getPriorityColor = (priority: string) => {
    switch (priority.toLowerCase()) {
      case "critical":
        return "bg-red-100 text-red-800 border-red-300";
      case "high":
        return "bg-orange-100 text-orange-800 border-orange-300";
      case "medium":
        return "bg-yellow-100 text-yellow-800 border-yellow-300";
      case "low":
        return "bg-green-100 text-green-800 border-green-300";
      default:
        return "bg-gray-100 text-gray-800 border-gray-300";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "open":
        return "bg-blue-100 text-blue-800 border-blue-300";
      case "in_progress":
        return "bg-purple-100 text-purple-800 border-purple-300";
      case "resolved":
        return "bg-green-100 text-green-800 border-green-300";
      case "closed":
        return "bg-gray-100 text-gray-800 border-gray-300";
      default:
        return "bg-gray-100 text-gray-800 border-gray-300";
    }
  };

  const formatDate = (value: string | null | undefined) => {
    if (!value) {
      return "-";
    }
    const date = new Date(value);
    return date.toLocaleDateString();
  };

  const fetchTickets = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await ticketService.fetchTickets();

      const normalizedData = data.map((ticket) => ({
        ...ticket,
        status: normalizeStatus(ticket.status),
      }));
      setTickets(normalizedData);
    } catch (err) {
      let message = "Failed to fetch tickets";
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

  useEffect(() => {
    fetchTickets();
  }, [refreshTrigger]);

  useEffect(() => {
    onTicketCountChange?.(tickets.length);
  }, [tickets, onTicketCountChange]);

  const updateTicketStatus = async (ticketId: number, nextStatus: Ticket["status"]) => {
    const normalizedNextStatus = normalizeStatus(nextStatus);
    setStatusNotice(null);
    const previous = tickets;
    setUpdatingTicketIds((prev) => new Set(prev).add(ticketId));
    setTickets((prev) =>
      prev.map((ticket) =>
        ticket.ticket_id === ticketId ? { ...ticket, status: normalizedNextStatus } : ticket
      )
    );

    try {
      const responsePayload = await ticketService.updateTicketStatus(ticketId, {
        status: normalizedNextStatus,
      });

      if (normalizedNextStatus === "closed") {
        if (responsePayload?.email_sent === true) {
          setStatusNotice(responsePayload.email_message || "Ticket closed and email sent.");
          setStatusNoticeType("success");
        } else if (responsePayload?.email_sent === false) {
          setStatusNotice(
            responsePayload.email_message || "Ticket closed, but email could not be sent."
          );
          setStatusNoticeType("warning");
        }
      }
    } catch (err) {
      setTickets(previous);
      let message = "Failed to update ticket status";
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
      setUpdatingTicketIds((prev) => {
        const next = new Set(prev);
        next.delete(ticketId);
        return next;
      });
    }
  };

  const filteredTickets = useMemo(() => {
    const filtered = tickets.filter((ticket) => {
      if (statusFilter !== "all" && ticket.status !== statusFilter) {
        return false;
      }
      return true;
    });

    if (prioritySort !== "all") {
      filtered.sort((a, b) => {
        const aOrder = priorityOrder[(a.priority || "").toLowerCase()] || 0;
        const bOrder = priorityOrder[(b.priority || "").toLowerCase()] || 0;
        return bOrder - aOrder;
      });
      return filtered;
    }

    filtered.sort(
      (a, b) =>
        new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
    );
    return filtered;
  }, [tickets, statusFilter, prioritySort]);

  const ticketCount = filteredTickets.length;

  const handleTicketIdClick = (
    event: React.MouseEvent<HTMLAnchorElement>,
    ticket: Ticket
  ) => {
    event.preventDefault();
    const ticketUrl = `/tickets/${ticket.ticket_id}`;
    onTicketSelect?.(ticket);
    window.open(ticketUrl, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="w-full space-y-4">
      <div className="bg-white rounded-lg shadow-md p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-800">My Tickets</h2>
          <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-1 text-xs font-semibold text-blue-700">
            {ticketCount}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">
              Filter by Status
            </label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Status</option>
              <option value="open">Open</option>
              <option value="in_progress">In Progress</option>
              <option value="resolved">Resolved</option>
              <option value="closed">Closed</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">
              Sort by Priority
            </label>
            <select
              value={prioritySort}
              onChange={(e) => setPrioritySort(e.target.value as PrioritySort)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">Newest First</option>
              <option value="critical">Critical First</option>
              <option value="high">High Priority</option>
              <option value="medium">Medium Priority</option>
              <option value="low">Low Priority</option>
            </select>
          </div>
        </div>
      </div>

      {loading && (
        <div className="flex justify-center items-center py-12">
          <div className="text-center">
            <div className="animate-spin inline-block w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full" />
            <p className="mt-2 text-gray-600">Loading tickets...</p>
          </div>
        </div>
      )}

      {error && !loading && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          <p className="font-semibold">Ticket Error</p>
          <p className="text-sm">{error}</p>
          <button
            onClick={fetchTickets}
            className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 text-sm"
          >
            Retry
          </button>
        </div>
      )}

      {statusNotice && !loading && (
        <div
          className={`rounded-lg p-4 text-sm ${
            statusNoticeType === "success"
              ? "bg-green-50 border border-green-200 text-green-700"
              : "bg-amber-50 border border-amber-200 text-amber-700"
          }`}
        >
          {statusNotice}
        </div>
      )}

      {!loading && !error && filteredTickets.length === 0 && (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <p className="text-gray-600">
            {tickets.length === 0
              ? "No tickets yet. Create one to get started!"
              : "No tickets match the current filters."}
          </p>
        </div>
      )}

      {!loading && !error && filteredTickets.length > 0 && (
        <div className="bg-white rounded-lg shadow-md overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Ticket</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Category</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Priority</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Status</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Created</th>
              </tr>
            </thead>
            <tbody>
              {filteredTickets.map((ticket) => {
                const isUpdating = updatingTicketIds.has(ticket.ticket_id);
                return (
                  <tr
                    key={ticket.ticket_id}
                    className="border-b border-gray-100 hover:bg-gray-50"
                  >
                    <td className="px-4 py-3 align-top">
                      <a
                        href={`/tickets/${ticket.ticket_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-semibold text-blue-700 hover:text-blue-900 hover:underline"
                        onClick={(event) => handleTicketIdClick(event, ticket)}
                      >
                        TKT-{ticket.ticket_id}
                      </a>
                      <p className="text-xs text-gray-600 mt-1 max-w-md truncate" title={ticket.issue || ""}>
                        {ticket.issue || "No description"}
                      </p>
                    </td>
                    <td className="px-4 py-3 align-top text-gray-700">{ticket.category || "N/A"}</td>
                    <td className="px-4 py-3 align-top">
                      <span className={`px-2 py-1 rounded text-xs font-semibold border ${getPriorityColor(ticket.priority || "")}`}>
                        {(ticket.priority || "N/A").toString()}
                      </span>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <div className="flex items-center gap-2">
                        <select
                          value={ticket.status}
                          disabled={isUpdating}
                          onChange={(e) => {
                            e.stopPropagation();
                            updateTicketStatus(ticket.ticket_id, e.target.value as Ticket["status"]);
                          }}
                          className={`px-2 py-1 rounded text-xs font-semibold border focus:outline-none ${getStatusColor(ticket.status)} ${isUpdating ? "opacity-60" : ""}`}
                        >
                          <option value="open">Open</option>
                          <option value="in_progress">In Progress</option>
                          <option value="resolved">Resolved</option>
                          <option value="closed">Closed</option>
                        </select>
                        {isUpdating && <span className="text-xs text-gray-500">Saving...</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3 align-top text-gray-600">{formatDate(ticket.created_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default TicketList;
