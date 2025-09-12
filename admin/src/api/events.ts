import { apiFetch } from './client';

/**
 * Representation of an event returned by the API.  Dates are
 * represented as ISO strings; UI components can convert them to
 * localized formats when rendering.
 */
export interface Event {
  id: number;
  title: string;
  description?: string | null;
  start_time: string;
  duration_minutes: number;
  max_participants: number;
  is_paid: boolean;
}

export interface EventsQueryParams {
  limit?: number;
  offset?: number;
  sort_by?: string;
  order?: 'asc' | 'desc';
  is_paid?: boolean;
  date_from?: string;
  date_to?: string;
}

/**
 * Payload for creating a new event.  Matches the EventCreate schema
 * defined in the OpenAPI spec.  All fields are required except
 * description.
 */
export interface EventCreate {
  title: string;
  description?: string | null;
  /** ISO 8601 datetime string when the event starts */
  start_time: string;
  /** Duration in minutes */
  duration_minutes: number;
  /** Maximum number of participants */
  max_participants: number;
  /** Whether the event is paid */
  is_paid: boolean;
}

/**
 * Payload for updating an existing event.  All fields are optional
 * because the server will merge undefined values with the existing
 * record.  A null value will explicitly clear the field on the
 * server.  Matches the EventUpdate schema from the spec.
 */
export interface EventUpdate {
  title?: string | null;
  description?: string | null;
  start_time?: string | null;
  duration_minutes?: number | null;
  max_participants?: number | null;
  is_paid?: boolean | null;
}

/**
 * Create a new event via POST /api/v1/events/.
 * Returns the created Event on success.
 */
export async function createEvent(data: EventCreate): Promise<Event> {
  return apiFetch<Event>('/api/v1/events/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing event via PUT /api/v1/events/{id}.
 * Returns the updated Event on success.
 */
export async function updateEvent(
  id: number,
  data: EventUpdate,
): Promise<Event> {
  return apiFetch<Event>(`/api/v1/events/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * Delete an event.  Returns void on success.  If the event has
 * associated bookings or dependencies, the server will return
 * an error which is surfaced via apiFetch.
 */
export async function deleteEvent(id: number): Promise<void> {
  await apiFetch<void>(`/api/v1/events/${id}`, {
    method: 'DELETE',
  });
}

/**
 * Duplicate an event.  Requires a new start_time.  Other fields
 * are copied from the original event.
 *
 * @param id ID of the event to duplicate
 * @param start_time ISO 8601 datetime string for the new event
 */
export async function duplicateEvent(
  id: number,
  start_time: string,
): Promise<Event> {
  return apiFetch<Event>(`/api/v1/events/${id}/duplicate`, {
    method: 'POST',
    body: JSON.stringify({ start_time }),
  });
}

/**
 * Fetch a list of events from the API with optional pagination,
 * sorting and filters.  The API returns an array of events; it does
 * not currently include total count, so callers must handle their
 * own pagination logic.
 */
export async function getEvents(params: EventsQueryParams): Promise<Event[]> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set('limit', String(params.limit));
  if (params.offset !== undefined) query.set('offset', String(params.offset));
  if (params.sort_by) query.set('sort_by', params.sort_by);
  if (params.order) query.set('order', params.order);
  if (params.is_paid !== undefined) query.set('is_paid', String(params.is_paid));
  if (params.date_from) query.set('date_from', params.date_from);
  if (params.date_to) query.set('date_to', params.date_to);
  const qs = query.toString();
  const url = qs ? `/api/v1/events/?${qs}` : '/api/v1/events/';
  return apiFetch<Event[]>(url);
}