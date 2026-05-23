import api from "./api";

export type TicketStatus = "open" | "in_progress" | "resolved" | "closed";

export type Ticket = {
  ticket_id: number;
  issue: string | null;
  category: string | null;
  priority: string | null;
  summary?: string | null;
  response?: string | null;
  assigned_team: string | null;
  status: TicketStatus;
  created_at: string | null;
  updated_at?: string | null;
};

export type CreateTicketPayload = {
  action?: "create";
  user_email: string;
  message: string;
};

export type UpdateTicketStatusPayload = {
  status: TicketStatus;
};

export type TicketStatusUpdateResponse = {
  email_sent?: boolean | null;
  email_message?: string | null;
};

export const ticketService = {
  async createTicket(payload: CreateTicketPayload) {
    const response = await api.post("/api/tickets/create", payload);
    return response.data;
  },
  async fetchTickets() {
    const response = await api.get<Ticket[]>("/api/tickets");
    return response.data;
  },
  async updateTicketStatus(ticketId: number, payload: UpdateTicketStatusPayload) {
    const response = await api.patch<TicketStatusUpdateResponse>(`/api/tickets/${ticketId}/status`, payload);
    return response.data;
  },
};
