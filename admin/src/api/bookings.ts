import { apiFetch } from './client';

/**
 * Representation of a booking returned by the API.  Matches the
 * BookingRead schema from the OpenAPI spec.  Some fields may be
 * nullable.
 */
export interface Booking {
  id: number;
  user_id: number;
  event_id: number;
  group_size: number;
  status: string;
  created_at: string;
  is_paid?: boolean | null;
  is_attended?: boolean | null;
  group_names?: string[] | null;
}

/** Schema for creating a booking.  Matches BookingCreate. */
export interface BookingCreate {
  group_size: number;
  group_names?: string[] | null;
}

/**
 * Fetch bookings for a specific event via GET /api/v1/events/{event_id}/bookings.
 */
export async function getEventBookings(eventId: number): Promise<Booking[]> {
  const res = await apiFetch<Booking[]>(`/api/v1/events/${eventId}/bookings`);
  return res ?? [];
}

/**
 * Create a booking for an event via POST /api/v1/events/{event_id}/bookings.
 */
export async function createBooking(
  eventId: number,
  data: BookingCreate,
): Promise<Booking> {
  const res = await apiFetch<Booking>(`/api/v1/events/${eventId}/bookings`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
  return res!;
}

/**
 * Delete a booking via DELETE /api/v1/bookings/{booking_id}.
 */
export async function deleteBooking(bookingId: number): Promise<void> {
  await apiFetch<void>(`/api/v1/bookings/${bookingId}`, {
    method: 'DELETE',
  });
}

/**
 * Toggle payment status on a booking via POST /api/v1/bookings/{booking_id}/toggle-payment.
 * Returns the updated booking.
 */
export async function togglePayment(bookingId: number): Promise<Booking> {
  const res = await apiFetch<Booking>(`/api/v1/bookings/${bookingId}/toggle-payment`, {
    method: 'POST',
  });
  return res!;
}

/**
 * Toggle attendance status on a booking via POST /api/v1/bookings/{booking_id}/toggle-attendance.
 * Returns the updated booking.
 */
export async function toggleAttendance(
  bookingId: number,
): Promise<Booking> {
  const res = await apiFetch<Booking>(`/api/v1/bookings/${bookingId}/toggle-attendance`, {
    method: 'POST',
  });
  return res!;
}

/**
 * Representation of a waitlist entry returned by the API.  The
 * endpoint does not have an explicit schema definition, so we
 * declare it here.
 */
export interface WaitlistEntry {
  id: number;
  user_id: number;
  position: number;
  created_at: string;
}

/**
 * Fetch the waitlist for a specific event via GET /api/v1/events/{event_id}/waitlist.
 */
export async function getEventWaitlist(
  eventId: number,
): Promise<WaitlistEntry[]> {
  const res = await apiFetch<WaitlistEntry[]>(`/api/v1/events/${eventId}/waitlist`);
  return res ?? [];
}