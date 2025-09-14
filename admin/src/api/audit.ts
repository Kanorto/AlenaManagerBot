import { apiFetch } from './client';
import type { operations } from './types.gen';

export type AuditQueryParams =
  operations['list_audit_logs_api_v1_audit_logs_get']['parameters']['query'];
export type AuditLog =
  operations['list_audit_logs_api_v1_audit_logs_get']['responses'][200]['content']['application/json'][number];

/**
 * Retrieve a list of audit logs filtered by optional parameters.
 * Only users with the super admin role may access this endpoint.
 */
export async function getAuditLogs(params: AuditQueryParams = {}): Promise<AuditLog[]> {
  const search = new URLSearchParams();
  if (params.user_id !== undefined && params.user_id !== null) search.set('user_id', String(params.user_id));
  if (params.object_type) search.set('object_type', params.object_type);
  if (params.action) search.set('action', params.action);
  if (params.start_date) search.set('start_date', params.start_date);
  if (params.end_date) search.set('end_date', params.end_date);
  if (params.limit !== undefined) search.set('limit', String(params.limit));
  if (params.offset !== undefined) search.set('offset', String(params.offset));
  const query = search.toString();
  const url = `/api/v1/audit/logs${query ? `?${query}` : ''}`;
  return apiFetch<AuditLog[]>(url);
}