import { apiFetch } from './client';
import type { components, operations } from './types.gen';

export type Booking = components['schemas']['BookingRead'];
export type BookingCreate = components['schemas']['BookingCreate'];
export type WaitlistEntry =
  operations['list_event_waitlist_api_v1_events__event_id__waitlist_get']['responses'][200]['content']['application/json'] extends Array<infer T>
    ? T
    : unknown;

/**
 * Fetch bookings for a specific event via GET /api/v1/events/{event_id}/bookings.
 */
export async function getEventBookings(eventId: number): Promise<Booking[]> {
  return apiFetch<Booking[]>(`/api/v1/events/${eventId}/bookings`);
}

/**
 * Create a booking for an event via POST /api/v1/events/{event_id}/bookings.
 */
export async function createBooking(
  eventId: number,
  data: BookingCreate,
): Promise<Booking> {
  return apiFetch<Booking>(`/api/v1/events/${eventId}/bookings`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
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
  return apiFetch<Booking>(`/api/v1/bookings/${bookingId}/toggle-payment`, {
    method: 'POST',
  });
}

/**
 * Toggle attendance status on a booking via POST /api/v1/bookings/{booking_id}/toggle-attendance.
 * Returns the updated booking.
 */
export async function toggleAttendance(
  bookingId: number,
): Promise<Booking> {
  return apiFetch<Booking>(`/api/v1/bookings/${bookingId}/toggle-attendance`, {
    method: 'POST',
  });
}

/**
 * Fetch the waitlist for a specific event via GET /api/v1/events/{event_id}/waitlist.
 */
export async function getEventWaitlist(
  eventId: number,
): Promise<WaitlistEntry[]> {
  return apiFetch<WaitlistEntry[]>(`/api/v1/events/${eventId}/waitlist`);
}