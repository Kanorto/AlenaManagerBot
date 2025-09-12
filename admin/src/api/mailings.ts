import { apiFetch } from './client';

/**
 * Interfaces describing the shape of mailing data returned from the API.
 * The backend returns ISO timestamps for created_at and scheduled_at fields
 * and allows an arbitrary JSON object for filters.  When creating or
 * updating a mailing the frontend may supply a subset of these fields.
 */
export interface Mailing {
  id: number;
  created_by: number;
  title: string;
  content: string;
  /** Criteria to select recipients, stored as an arbitrary object */
  filters: Record<string, unknown> | null;
  /** ISO 8601 datetime when the mailing is scheduled to send, or null */
  scheduled_at: string | null;
  /** ISO 8601 datetime when the mailing was created */
  created_at: string;
  /** List of messenger channels to send through (e.g. ['telegram']) */
  messengers: string[] | null;
}

/** Schema for creating a new mailing.  Only title and content are required. */
export interface MailingCreate {
  title: string;
  content: string;
  filters?: Record<string, unknown> | null;
  scheduled_at?: string | null;
  messengers?: string[] | null;
}

/** Schema for updating an existing mailing.  All fields are optional. */
export interface MailingUpdate {
  title?: string | null;
  content?: string | null;
  filters?: Record<string, unknown> | null;
  scheduled_at?: string | null;
  messengers?: string[] | null;
}

/** Shape of an individual mailing log entry returned by the API. */
export interface MailingLog {
  id: number;
  mailing_id: number;
  user_id: number;
  status: string;
  error_message: string | null;
  sent_at: string;
}

/** Parameters for querying the list of mailings.  All fields are optional. */
export interface MailingsQueryParams {
  limit?: number;
  offset?: number;
  sort_by?: string | null;
  order?: string | null;
}

/**
 * Retrieve a list of mailings.  Results may be paginated and sorted via
 * query parameters.  When omitted, the backend applies its defaults.
 */
export async function getMailings(params: MailingsQueryParams = {}): Promise<Mailing[]> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set('limit', String(params.limit));
  if (params.offset !== undefined) search.set('offset', String(params.offset));
  if (params.sort_by) search.set('sort_by', params.sort_by);
  if (params.order) search.set('order', params.order);
  const query = search.toString();
  const url = `/api/v1/mailings/${query ? `?${query}` : ''}`;
  return apiFetch<Mailing[]>(url);
}

/** Fetch details of a single mailing by ID. */
export async function getMailing(id: number): Promise<Mailing> {
  return apiFetch<Mailing>(`/api/v1/mailings/${id}`);
}

/** Create a new mailing.  Returns the created mailing. */
export async function createMailing(data: MailingCreate): Promise<Mailing> {
  return apiFetch<Mailing>('/api/v1/mailings/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/** Update an existing mailing.  Returns the updated mailing. */
export async function updateMailing(id: number, data: MailingUpdate): Promise<Mailing> {
  return apiFetch<Mailing>(`/api/v1/mailings/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/** Delete a mailing by its ID.  Returns void on success. */
export async function deleteMailing(id: number): Promise<void> {
  await apiFetch<void>(`/api/v1/mailings/${id}`, {
    method: 'DELETE',
  });
}

/** Trigger immediate sending of a mailing.  Returns the number of recipients. */
export async function sendMailing(id: number): Promise<number> {
  return apiFetch<number>(`/api/v1/mailings/${id}/send`, {
    method: 'POST',
  });
}

/** Retrieve delivery logs for a mailing.  Results may be paginated. */
export async function getMailingLogs(
  id: number,
  params: { limit?: number; offset?: number } = {},
): Promise<MailingLog[]> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set('limit', String(params.limit));
  if (params.offset !== undefined) search.set('offset', String(params.offset));
  const query = search.toString();
  const url = `/api/v1/mailings/${id}/logs${query ? `?${query}` : ''}`;
  return apiFetch<MailingLog[]>(url);
}