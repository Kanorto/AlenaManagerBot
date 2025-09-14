import { apiFetch } from './client';
import type { components, operations } from './types.gen';

export type Faq = components['schemas']['FAQRead'];
export type FaqCreate = components['schemas']['FAQCreate'];
export type FaqUpdate = components['schemas']['FAQUpdate'];
export type FaqQueryParams =
  NonNullable<operations['list_faqs_api_v1_faqs__get']['parameters']['query']>;

/** Fetch a paginated list of FAQ entries. */
export async function getFaqs(params: FaqQueryParams = {}): Promise<Faq[]> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set('limit', String(params.limit));
  if (params.offset !== undefined) search.set('offset', String(params.offset));
  const query = search.toString();
  const url = `/api/v1/faqs/${query ? `?${query}` : ''}`;
  return apiFetch<Faq[]>(url);
}

/** Create a new FAQ entry. */
export async function createFaq(data: FaqCreate): Promise<Faq> {
  return apiFetch<Faq>('/api/v1/faqs/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/** Update an existing FAQ entry by its ID. */
export async function updateFaq(id: number, data: FaqUpdate): Promise<Faq> {
  return apiFetch<Faq>(`/api/v1/faqs/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/** Delete an FAQ entry. */
export async function deleteFaq(id: number): Promise<void> {
  await apiFetch<void>(`/api/v1/faqs/${id}`, {
    method: 'DELETE',
  });
}