import { apiFetch } from './client';
import type { operations } from './types.gen';

export type StatisticsOverview =
  operations['statistics_overview_api_v1_statistics_overview_get']['responses'][200]['content']['application/json'];

/**
 * Fetch global statistics overview from the backend.  Uses the
 * generic apiFetch helper which handles authentication and error
 * propagation.  Returns a record of counts keyed by metric name.
 */
export async function getStatisticsOverview(): Promise<StatisticsOverview> {
  return apiFetch<StatisticsOverview>('/api/v1/statistics/overview');
}