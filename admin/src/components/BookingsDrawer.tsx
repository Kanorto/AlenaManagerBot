import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getEventBookings,
  createBooking,
  deleteBooking,
  togglePayment,
  toggleAttendance,
  getEventWaitlist,
  Booking,
  WaitlistEntry,
} from '../api/bookings';
import { useNotifications } from '../store/notifications';
import { z } from 'zod';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

interface BookingsDrawerProps {
  eventId: number;
  eventTitle: string;
  isOpen: boolean;
  onClose: () => void;
}

// Form schema for creating a booking.  Group size must be >= 1.
const bookingSchema = z.object({
  group_size: z
    .preprocess((v) => (v === '' ? undefined : parseInt(v as string, 10)), z.number().int().min(1)),
  group_names: z.string().optional().nullable(),
});
type BookingFormData = z.infer<typeof bookingSchema>;

/**
 * BookingsDrawer displays participants and waitlist for a given event.
 * It also includes a small form to create new bookings and provides
 * actions to toggle payment/attendance and delete bookings.  Errors
 * are surfaced via the global notifications system.
 */
const BookingsDrawer: React.FC<BookingsDrawerProps> = ({
  eventId,
  eventTitle,
  isOpen,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<'participants' | 'waitlist'>('participants');
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();

  // Fetch bookings (participants)
  const {
    data: bookings,
    isLoading: bookingsLoading,
    error: bookingsError,
  } = useQuery<Booking[], Error>(['eventBookings', eventId], () => getEventBookings(eventId), {
    enabled: isOpen,
    onError: (err) => addNotification(err.message, 'error'),
  });

  // Fetch waitlist
  const {
    data: waitlist,
    isLoading: waitlistLoading,
    error: waitlistError,
  } = useQuery<WaitlistEntry[], Error>(['eventWaitlist', eventId], () => getEventWaitlist(eventId), {
    enabled: isOpen,
    onError: (err) => addNotification(err.message, 'error'),
  });

  // Mutation for toggling payment
  const togglePaymentMutation = useMutation((bookingId: number) => togglePayment(bookingId), {
    onSuccess: () => queryClient.invalidateQueries(['eventBookings', eventId]),
    onError: (err: Error) => addNotification(err.message, 'error'),
  });
  // Mutation for toggling attendance
  const toggleAttendanceMutation = useMutation((bookingId: number) => toggleAttendance(bookingId), {
    onSuccess: () => queryClient.invalidateQueries(['eventBookings', eventId]),
    onError: (err: Error) => addNotification(err.message, 'error'),
  });
  // Mutation for deleting booking
  const deleteBookingMutation = useMutation((bookingId: number) => deleteBooking(bookingId), {
    onSuccess: () => queryClient.invalidateQueries(['eventBookings', eventId]),
    onError: (err: Error) => addNotification(err.message, 'error'),
  });
  // Mutation for creating booking
  const createBookingMutation = useMutation(
    (data: { group_size: number; group_names?: string[] | null }) =>
      createBooking(eventId, data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['eventBookings', eventId]);
        addNotification('Booking created', 'success');
      },
      onError: (err: Error) => addNotification(err.message, 'error'),
    },
  );

  // Booking creation form
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BookingFormData>({ resolver: zodResolver(bookingSchema) });
  const handleCreateBooking = handleSubmit(async (data) => {
    const payload = {
      group_size: data.group_size,
      group_names: data.group_names
        ? data.group_names
            .split(',')
            .map((n) => n.trim())
            .filter((n) => n.length > 0)
        : undefined,
    };
    await createBookingMutation.mutateAsync(payload);
    reset();
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-40 flex">
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black bg-opacity-30"
        onClick={onClose}
      />
      {/* Drawer */}
      <div className="ml-auto w-full max-w-lg bg-white dark:bg-gray-900 h-full shadow-xl overflow-y-auto p-6 z-50 flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold dark:text-gray-100">
            {eventTitle} — Details
          </h3>
          <button
            className="text-gray-600 dark:text-gray-300 hover:text-black dark:hover:text-white"
            onClick={onClose}
          >
            ✕
          </button>
        </div>
        {/* Tabs */}
        <div className="flex border-b border-gray-200 dark:border-gray-700 mb-4">
          <button
            className={`px-3 py-2 text-sm font-medium ${
              activeTab === 'participants'
                ? 'border-b-2 border-blue-600 text-blue-600'
                : 'text-gray-500 dark:text-gray-400'
            }`}
            onClick={() => setActiveTab('participants')}
          >
            Participants
          </button>
          <button
            className={`ml-4 px-3 py-2 text-sm font-medium ${
              activeTab === 'waitlist'
                ? 'border-b-2 border-blue-600 text-blue-600'
                : 'text-gray-500 dark:text-gray-400'
            }`}
            onClick={() => setActiveTab('waitlist')}
          >
            Waitlist
          </button>
        </div>
        {/* Content */}
        {activeTab === 'participants' && (
          <div className="flex-1 flex flex-col">
            {/* Create booking form */}
            <form
              onSubmit={handleCreateBooking}
              className="mb-4 space-y-2 border border-gray-200 dark:border-gray-700 rounded-md p-3"
            >
              <h4 className="font-medium text-sm mb-1 dark:text-gray-100">Add Booking</h4>
              <div className="flex items-end gap-2">
                <div className="flex-1">
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">
                    Group Size
                  </label>
                  <input
                    type="number"
                    min="1"
                    {...register('group_size')}
                    className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-800"
                  />
                  {errors.group_size && (
                    <p className="text-xs text-red-600 mt-1">
                      {errors.group_size.message}
                    </p>
                  )}
                </div>
                <div className="flex-1">
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">
                    Group Names (comma separated)
                  </label>
                    <input
                      type="text"
                      {...register('group_names')}
                      className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-800"
                    />
                    {errors.group_names && (
                      <p className="text-xs text-red-600 mt-1">
                        {errors.group_names.message}
                      </p>
                    )}
                </div>
                <button
                  type="submit"
                  className="h-8 px-3 rounded-md bg-green-600 text-white text-sm self-end"
                >
                  Add
                </button>
              </div>
            </form>

            {/* Export participants */}
            <div className="mb-4">
              <button
                onClick={() => {
                  if (!bookings || bookings.length === 0) {
                    addNotification('No participants to export', 'info');
                    return;
                  }
                  // Build CSV content
                  const header = [
                    'ID',
                    'UserID',
                    'GroupSize',
                    'Status',
                    'CreatedAt',
                    'Paid',
                    'Attended',
                  ];
                  const rows = bookings.map((b) => [
                    b.id,
                    b.user_id,
                    b.group_size,
                    b.status,
                    b.created_at,
                    b.is_paid ? 'Paid' : 'Unpaid',
                    b.is_attended ? 'Attended' : 'Absent',
                  ]);
                  const csv = [header, ...rows]
                    .map((r) =>
                      r
                        .map((v) =>
                          typeof v === 'string' && v.includes(',')
                            ? `"${v.replace(/"/g, '""')}"`
                            : v,
                        )
                        .join(','),
                    )
                    .join('\n');
                  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
                  const url = URL.createObjectURL(blob);
                  const link = document.createElement('a');
                  link.setAttribute('href', url);
                  link.setAttribute('download', `${eventTitle.replace(/\s+/g, '_')}_participants.csv`);
                  link.click();
                  URL.revokeObjectURL(url);
                }}
                className="px-3 py-1 rounded-md bg-blue-600 text-white text-sm"
              >
                Export Participants
              </button>
            </div>
            {/* Participants table */}
            <div className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-md flex-1">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-sm">
                <thead className="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">ID</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">User</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">Group Size</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">Status</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">Created</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">Paid</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">Attended</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                  {bookingsLoading ? (
                    <tr>
                      <td colSpan={8} className="px-3 py-3 text-center">
                        Loading...
                      </td>
                    </tr>
                  ) : bookingsError ? (
                    <tr>
                      <td colSpan={8} className="px-3 py-3 text-center text-red-600 dark:text-red-400">
                        Failed to load bookings.
                      </td>
                    </tr>
                  ) : bookings && bookings.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-3 py-3 text-center text-gray-500 dark:text-gray-400">
                        No bookings found.
                      </td>
                    </tr>
                  ) : (
                    bookings?.map((booking) => (
                      <tr key={booking.id}>
                        <td className="px-3 py-2 whitespace-nowrap">{booking.id}</td>
                        <td className="px-3 py-2 whitespace-nowrap">{booking.user_id}</td>
                        <td className="px-3 py-2 whitespace-nowrap">{booking.group_size}</td>
                        <td className="px-3 py-2 whitespace-nowrap">{booking.status}</td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          {new Date(booking.created_at).toLocaleString()}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <button
                            onClick={() => togglePaymentMutation.mutate(booking.id)}
                            className={`px-2 py-1 rounded-md text-xs ${
                              booking.is_paid ? 'bg-green-600' : 'bg-gray-300 dark:bg-gray-700'
                            } text-white`}
                          >
                            {booking.is_paid ? 'Paid' : 'Unpaid'}
                          </button>
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <button
                            onClick={() => toggleAttendanceMutation.mutate(booking.id)}
                            className={`px-2 py-1 rounded-md text-xs ${
                              booking.is_attended ? 'bg-green-600' : 'bg-gray-300 dark:bg-gray-700'
                            } text-white`}
                          >
                            {booking.is_attended ? 'Attended' : 'Absent'}
                          </button>
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap space-x-2">
                          <button
                            onClick={() => deleteBookingMutation.mutate(booking.id)}
                            className="px-2 py-1 rounded-md bg-red-600 text-white text-xs"
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
        {activeTab === 'waitlist' && (
          <div className="flex-1 flex flex-col">
            <div className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-md flex-1">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-sm">
                <thead className="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">ID</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">User</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">Position</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">Added</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                  {waitlistLoading ? (
                    <tr>
                      <td colSpan={4} className="px-3 py-3 text-center">
                        Loading...
                      </td>
                    </tr>
                  ) : waitlistError ? (
                    <tr>
                      <td colSpan={4} className="px-3 py-3 text-center text-red-600 dark:text-red-400">
                        Failed to load waitlist.
                      </td>
                    </tr>
                  ) : waitlist && waitlist.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-3 py-3 text-center text-gray-500 dark:text-gray-400">
                        No one in waitlist.
                      </td>
                    </tr>
                  ) : (
                    waitlist?.map((entry) => (
                      <tr key={entry.id}>
                        <td className="px-3 py-2 whitespace-nowrap">{entry.id}</td>
                        <td className="px-3 py-2 whitespace-nowrap">{entry.user_id}</td>
                        <td className="px-3 py-2 whitespace-nowrap">{entry.position}</td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          {new Date(entry.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BookingsDrawer;