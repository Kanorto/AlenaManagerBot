import { apiFetch } from './client';
import type { components, operations } from './types.gen';

export type Mailing = components['schemas']['MailingRead'];
export type MailingCreate = components['schemas']['MailingCreate'];
export type MailingUpdate = components['schemas']['MailingUpdate'];
export type MailingLog = components['schemas']['MailingLogRead'];
export type MailingsQueryParams =
  NonNullable<operations['list_mailings_api_v1_mailings__get']['parameters']['query']>;
export type MailingLogsQueryParams =
  NonNullable<operations['get_logs_api_v1_mailings__mailing_id__logs_get']['parameters']['query']>;

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
  params: MailingLogsQueryParams = {},
): Promise<MailingLog[]> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set('limit', String(params.limit));
  if (params.offset !== undefined) search.set('offset', String(params.offset));
  const query = search.toString();
  const url = `/api/v1/mailings/${id}/logs${query ? `?${query}` : ''}`;
  return apiFetch<MailingLog[]>(url);
}