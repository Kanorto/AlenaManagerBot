import { apiFetch } from './client';

/**
 * Shape of the statistics overview returned by the backend.  The
 * backend returns counts of various entities and total revenue.
 * Additional fields may be added in the future without breaking
 * existing consumers because TypeScript treats unspecified keys as
 * optional.  We use an index signature to allow unknown keys.
 */
export interface StatisticsOverview {
  users_count?: number;
  events_count?: number;
  bookings_count?: number;
  payments_count?: number;
  reviews_count?: number;
  support_tickets_total?: number;
  support_tickets_open?: number;
  waitlist_count?: number;
  total_revenue?: number;
  [key: string]: number | undefined;
}

/**
 * Fetch global statistics overview from the backend.  Uses the
 * generic apiFetch helper which handles authentication and error
 * propagation.  Returns a record of counts keyed by metric name.
 */
export async function getStatisticsOverview(): Promise<StatisticsOverview> {
  return apiFetch<StatisticsOverview>('/api/v1/statistics/overview');
}