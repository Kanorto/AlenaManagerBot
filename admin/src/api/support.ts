import { apiFetch } from './client';
import type { components, operations } from './types.gen';

export type SupportTicket = components['schemas']['SupportTicketRead'];
export type SupportTicketCreate = components['schemas']['SupportTicketCreate'];
export type SupportTicketUpdate = components['schemas']['SupportTicketUpdate'];
export type SupportMessage = components['schemas']['SupportMessageRead'];
export type SupportMessageCreate = components['schemas']['SupportMessageCreate'];
export type TicketWithMessages = components['schemas']['TicketWithMessages'];
export type TicketsQueryParams =
  NonNullable<operations['list_tickets_api_v1_support_tickets_get']['parameters']['query']>;

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
  data: SupportMessageCreate,
): Promise<SupportMessage> {
  return apiFetch<SupportMessage>(`/api/v1/support/tickets/${id}/reply`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/** Update the status of a support ticket. */
export async function updateTicketStatus(
  id: number,
  data: SupportTicketUpdate,
): Promise<SupportTicket> {
  return apiFetch<SupportTicket>(`/api/v1/support/tickets/${id}/status`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}