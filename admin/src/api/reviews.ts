import { apiFetch } from './client';

/** Represents a user review for an event. */
export interface Review {
  id: number;
  user_id: number;
  event_id: number;
  rating: number;
  comment: string | null;
  approved: boolean;
  moderated_by: number | null;
  created_at: string;
}

/** Query parameters for listing reviews. */
export interface ReviewsQueryParams {
  event_id?: number | null;
  user_id?: number | null;
  approved?: boolean | null;
  limit?: number;
  offset?: number;
  sort_by?: string | null;
  order?: string | null;
}

/** Fetch a paginated list of reviews with optional filters. */
export async function getReviews(params: ReviewsQueryParams = {}): Promise<Review[]> {
  const search = new URLSearchParams();
  if (params.event_id !== undefined && params.event_id !== null) search.set('event_id', String(params.event_id));
  if (params.user_id !== undefined && params.user_id !== null) search.set('user_id', String(params.user_id));
  if (params.approved !== undefined && params.approved !== null) search.set('approved', String(params.approved));
  if (params.limit !== undefined) search.set('limit', String(params.limit));
  if (params.offset !== undefined) search.set('offset', String(params.offset));
  if (params.sort_by) search.set('sort_by', params.sort_by);
  if (params.order) search.set('order', params.order);
  const query = search.toString();
  const url = `/api/v1/reviews${query ? `?${query}` : ''}`;
  const res = await apiFetch<Review[]>(url);
  return res ?? [];
}

/** Delete a review by its ID. */
export async function deleteReview(id: number): Promise<void> {
  await apiFetch<void>(`/api/v1/reviews/${id}`, {
    method: 'DELETE',
  });
}

/** Approve or reject a review.  Returns the updated review. */
export async function moderateReview(id: number, approved: boolean): Promise<Review> {
  const res = await apiFetch<Review>(`/api/v1/reviews/${id}/moderate`, {
    method: 'PUT',
    body: JSON.stringify({ approved }),
  });
  return res!;
}