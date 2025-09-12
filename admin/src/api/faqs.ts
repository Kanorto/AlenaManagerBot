import { apiFetch } from './client';

/** Represents a frequently asked question entry. */
export interface Faq {
  id: number;
  question_short: string;
  question_full: string | null;
  answer: string;
  attachments: string[] | null;
  position: number;
  created_at: string;
  updated_at: string;
}

/** Schema for creating a new FAQ entry.  Only question_short and
 * answer are required; other fields are optional. */
export interface FaqCreate {
  question_short: string;
  question_full?: string | null;
  answer: string;
  attachments?: string[] | null;
  position?: number | null;
}

/** Schema for updating an existing FAQ entry.  All fields are
 * optional; omitted fields are left unchanged. */
export interface FaqUpdate {
  question_short?: string | null;
  question_full?: string | null;
  answer?: string | null;
  attachments?: string[] | null;
  position?: number | null;
}

/** Query parameters for listing FAQs. */
export interface FaqQueryParams {
  limit?: number;
  offset?: number;
  sort_by?: string | null;
  order?: string | null;
}

/** Fetch a paginated list of FAQ entries. */
export async function getFaqs(params: FaqQueryParams = {}): Promise<Faq[]> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set('limit', String(params.limit));
  if (params.offset !== undefined) search.set('offset', String(params.offset));
  if (params.sort_by) search.set('sort_by', params.sort_by);
  if (params.order) search.set('order', params.order);
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