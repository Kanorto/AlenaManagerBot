import { apiFetch } from './client';
import type { components, operations } from './types.gen';

export type Payment = components['schemas']['PaymentRead'];
export type PaymentsQueryParams =
  NonNullable<operations['list_payments_api_v1_payments__get']['parameters']['query']>;

/**
 * Fetch a list of payments with optional filters, sorting and
 * pagination.  Returns an array of Payment objects.  The server
 * currently does not return a total count; pagination must be
 * inferred by comparing returned length with the requested limit.
 */
export async function getPayments(params: PaymentsQueryParams = {}): Promise<Payment[]> {
  const query = new URLSearchParams();
  if (params.event_id !== undefined && params.event_id !== null)
    query.set('event_id', String(params.event_id));
  if (params.provider) query.set('provider', params.provider);
  if (params.status_param) query.set('status_param', params.status_param);
  if (params.sort_by) query.set('sort_by', params.sort_by);
  if (params.order) query.set('order', params.order);
  if (params.limit !== undefined && params.limit !== null)
    query.set('limit', String(params.limit));
  if (params.offset !== undefined && params.offset !== null)
    query.set('offset', String(params.offset));
  const qs = query.toString();
  const url = qs ? `/api/v1/payments/?${qs}` : '/api/v1/payments/';
  return apiFetch<Payment[]>(url);
}

/**
 * Confirm a payment via POST /api/v1/payments/{id}/confirm.  Only
 * administrators may confirm payments.  Returns void on success.
 */
export async function confirmPayment(id: number): Promise<void> {
  await apiFetch<void>(`/api/v1/payments/${id}/confirm`, {
    method: 'POST',
  });
}

/**
 * Delete a payment via DELETE /api/v1/payments/{id}.  Returns void on
 * success.  Only administrators may delete payments.
 */
export async function deletePayment(id: number): Promise<void> {
  await apiFetch<void>(`/api/v1/payments/${id}`, {
    method: 'DELETE',
  });
}