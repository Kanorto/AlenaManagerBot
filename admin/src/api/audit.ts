import { apiFetch } from './client';

/** Query parameters for retrieving audit logs. */
export interface AuditQueryParams {
  user_id?: number | null;
  object_type?: string | null;
  action?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  limit?: number;
  offset?: number;
}

/** The audit log API returns arbitrary JSON objects describing actions taken
 * within the system.  Each record typically includes fields such as
 * ``id``, ``user_id``, ``object_type``, ``object_id``, ``action`` and
 * ``timestamp``, but the schema is not formally defined.  We use a
 * catch-all type here and let consumers handle fields dynamically. */
export type AuditLog = Record<string, unknown>;

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