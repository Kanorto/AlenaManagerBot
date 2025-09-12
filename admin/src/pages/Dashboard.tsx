import React from 'react';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { getStatisticsOverview, StatisticsOverview } from '../api/statistics';
import { useNotifications } from '../store/notifications';

/**
 * Dashboard page displays high‑level system statistics to administrators.
 * It fetches aggregated counts from the backend and renders them as
 * cards.  A date range picker is included as a placeholder for
 * future charts.  Loading and error states are handled gracefully.
 */
const DashboardPage: React.FC = () => {
  const { addNotification } = useNotifications();
  // Date range state for future statistics (not yet used)
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // Fetch statistics overview from the API.  We set a stale time of
  // 60 seconds to avoid refetching on every render.  Errors are
  // surfaced via the notifications store.
  const { data, error, isLoading } = useQuery<StatisticsOverview, Error>({
    queryKey: ['statisticsOverview'],
    queryFn: getStatisticsOverview,
    staleTime: 60 * 1000,
    onError: (err) => {
      addNotification(err.message, 'error');
    },
  });

  // Define card configurations: label, key, and formatting if needed.
  const metrics: { key: keyof StatisticsOverview; label: string; color: string }[] = [
    { key: 'users_count', label: 'Users', color: 'bg-blue-500' },
    { key: 'events_count', label: 'Events', color: 'bg-green-500' },
    { key: 'bookings_count', label: 'Bookings', color: 'bg-indigo-500' },
    { key: 'payments_count', label: 'Payments', color: 'bg-purple-500' },
    { key: 'reviews_count', label: 'Reviews', color: 'bg-teal-500' },
    { key: 'support_tickets_total', label: 'Total Tickets', color: 'bg-orange-500' },
    { key: 'support_tickets_open', label: 'Open Tickets', color: 'bg-yellow-500' },
    { key: 'waitlist_count', label: 'Waitlist', color: 'bg-pink-500' },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold">Dashboard</h2>
      {/* Date range picker (placeholder for charts) */}
      <div className="flex flex-wrap gap-4 items-end">
        <div>
          <label htmlFor="startDate" className="block text-sm font-medium mb-1">
            Start Date
          </label>
          <input
            id="startDate"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label htmlFor="endDate" className="block text-sm font-medium mb-1">
            End Date
          </label>
          <input
            id="endDate"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm"
          />
        </div>
        {/* Placeholder for future action, e.g. applying the date range */}
        <button
          type="button"
          className="ml-auto px-4 py-2 text-sm font-medium bg-primary text-white rounded-md disabled:opacity-50"
          disabled
        >
          Apply Range
        </button>
      </div>

      {/* Statistics cards */}
      {isLoading ? (
        <div>Loading statistics…</div>
      ) : error ? (
        <div className="text-red-600 dark:text-red-400">
          Failed to load statistics.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {metrics.map((metric) => {
            const value = data?.[metric.key] ?? 0;
            return (
              <div
                key={metric.key}
                className={`rounded-lg shadow p-4 text-white ${metric.color}`}
              >
                <div className="text-sm font-medium mb-1">{metric.label}</div>
                <div className="text-2xl font-bold">{value}</div>
              </div>
            );
          })}
          {/* Display revenue separately with currency formatting */}
          <div className="rounded-lg shadow p-4 text-white bg-red-500">
            <div className="text-sm font-medium mb-1">Total Revenue</div>
            <div className="text-2xl font-bold">
              {data?.total_revenue?.toLocaleString(undefined, {
                style: 'currency',
                currency: 'USD',
                maximumFractionDigits: 0,
              }) || '$0'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DashboardPage;