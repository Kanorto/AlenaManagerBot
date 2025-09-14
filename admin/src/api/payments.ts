import { apiFetch } from './client';

/**
 * Representation of a payment returned by the API.  Matches the
 * ``PaymentRead`` schema in the OpenAPI spec.  Not all properties
 * are strictly typed here; unknown properties are preserved via the
 * index signature.
 */
export interface Payment {
  id: number;
  user_id?: number;
  event_id?: number | null;
  amount: number;
  currency: string;
  description?: string | null;
  provider?: string | null;
  status?: string | null;
  external_id?: string | null;
  confirmed_by?: number | null;
  confirmed_at?: string | null;
  created_at: string;
  updated_at?: string | null;
  [key: string]: unknown;
}

/**
 * Query parameters accepted by the list payments endpoint.  All
 * parameters are optional.  See the OpenAPI spec for detailed
 * semantics of each filter.  ``status`` expects raw API values
 * (pending/success/etc.).  ``provider`` expects yookassa/support/cash.
 */
export interface PaymentsQueryParams {
  event_id?: number;
  provider?: string;
  status?: string;
  sort_by?: string;
  order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

/**
 * Fetch a list of payments with optional filters, sorting and
 * pagination.  Returns an array of Payment objects.  The server
 * currently does not return a total count; pagination must be
 * inferred by comparing returned length with the requested limit.
 */
export async function getPayments(params: PaymentsQueryParams): Promise<Payment[]> {
  const query = new URLSearchParams();
  if (params.event_id !== undefined) query.set('event_id', String(params.event_id));
  if (params.provider) query.set('provider', params.provider);
  if (params.status) query.set('status_param', params.status);
  if (params.sort_by) query.set('sort_by', params.sort_by);
  if (params.order) query.set('order', params.order);
  if (params.limit !== undefined) query.set('limit', String(params.limit));
  if (params.offset !== undefined) query.set('offset', String(params.offset));
  const qs = query.toString();
  const url = qs ? `/api/v1/payments/?${qs}` : '/api/v1/payments/';
  const res = await apiFetch<Payment[]>(url);
  return res ?? [];
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