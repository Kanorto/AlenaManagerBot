import { apiFetch } from './client';

/**
 * Represents a single application setting.  The backend stores settings
 * as key/value pairs with an associated type.  Keys may be namespaced
 * (e.g. ``booking.waitlist_delay``) but are returned as a flat list.
 */
export interface Setting {
  key: string;
  value: unknown;
  type: string;
}

/** Fetch all settings.  Only super administrators can access this endpoint. */
export async function getSettings(): Promise<Setting[]> {
  const res = await apiFetch<Setting[]>('/api/v1/settings/');
  return res ?? [];
}

/** Retrieve a specific setting by key. */
export async function getSetting(key: string): Promise<Setting> {
  const res = await apiFetch<Setting>(`/api/v1/settings/${encodeURIComponent(key)}`);
  return res!;
}

/** Upsert (create or update) a setting.  Provide the new value and its
 * type.  Supported types include 'string', 'int', 'float' and 'bool'. */
export async function upsertSetting(key: string, value: unknown, type: string): Promise<Setting> {
  const res = await apiFetch<Setting>(`/api/v1/settings/${encodeURIComponent(key)}`, {
    method: 'POST',
    body: JSON.stringify({ value, type }),
  });
  return res!;
}