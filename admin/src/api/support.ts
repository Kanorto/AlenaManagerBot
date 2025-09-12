import { apiFetch } from './client';

/**
 * Represents a support ticket without its message thread.  Status
 * values are strings such as 'open', 'in_progress', 'resolved'
 * and 'closed'.  Only administrators can view all tickets.
 */
export interface SupportTicket {
  id: number;
  user_id: number;
  subject: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

/** Input schema for creating a support ticket.  Users supply a
 * subject and initial message content. */
export interface SupportTicketCreate {
  subject: string;
  content: string;
}

/** Input schema for updating the status of a ticket. */
export interface SupportTicketUpdate {
  status: string;
}

/** Represents an individual message on a ticket.  Sender_role
 * identifies whether the message was authored by a user or admin. */
export interface SupportMessage {
  id: number;
  ticket_id: number;
  content: string;
  created_at: string;
  sender_role: string;
  user_id?: number | null;
  admin_id?: number | null;
  attachments?: string[] | null;
}

/** Composite return type for ticket details and its messages. */
export interface TicketWithMessages {
  ticket: SupportTicket;
  messages: SupportMessage[];
}

/** Query parameters for listing tickets. */
export interface TicketsQueryParams {
  status?: string | null;
  limit?: number;
  offset?: number;
  sort_by?: string | null;
  order?: string | null;
}

/**
 * List support tickets visible to the current user.  Administrators can
 * view all tickets; regular users see only their own.  Supports
 * optional filtering by status and pagination.
 */
export async function getTickets(params: TicketsQueryParams = {}): Promise<SupportTicket[]> {
  const search = new URLSearchParams();
  if (params.status) search.set('status', params.status);
  if (params.limit !== undefined) search.set('limit', String(params.limit));
  if (params.offset !== undefined) search.set('offset', String(params.offset));
  if (params.sort_by) search.set('sort_by', params.sort_by);
  if (params.order) search.set('order', params.order);
  const query = search.toString();
  const url = `/api/v1/support/tickets${query ? `?${query}` : ''}`;
  return apiFetch<SupportTicket[]>(url);
}

/** Create a new support ticket. */
export async function createTicket(data: SupportTicketCreate): Promise<SupportTicket> {
  return apiFetch<SupportTicket>('/api/v1/support/tickets', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/** Delete a support ticket.  Only administrators can delete tickets. */
export async function deleteTicket(id: number): Promise<void> {
  await apiFetch<void>(`/api/v1/support/tickets/${id}`, {
    method: 'DELETE',
  });
}

/** Retrieve a ticket along with its message thread. */
export async function getTicketWithMessages(id: number): Promise<TicketWithMessages> {
  return apiFetch<TicketWithMessages>(`/api/v1/support/tickets/${id}`);
}

/** Reply to a support ticket.  Returns the created message. */
export async function replyToTicket(
  id: number,
  data: { content: string; attachments?: string[] | null },
): Promise<SupportMessage> {
  return apiFetch<SupportMessage>(`/api/v1/support/tickets/${id}/reply`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/** Update the status of a support ticket. */
export async function updateTicketStatus(id: number, status: string): Promise<SupportTicket> {
  return apiFetch<SupportTicket>(`/api/v1/support/tickets/${id}/status`, {
    method: 'PUT',
    body: JSON.stringify({ status }),
  });
}