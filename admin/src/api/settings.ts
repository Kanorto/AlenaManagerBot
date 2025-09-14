import { apiFetch } from './client';
import type { operations } from './types.gen';

export type Setting =
  operations['list_settings_api_v1_settings__get']['responses'][200]['content']['application/json'][number];

/** Fetch all settings.  Only super administrators can access this endpoint. */
export async function getSettings(): Promise<Setting[]> {
  return apiFetch<Setting[]>('/api/v1/settings/');
}

/** Retrieve a specific setting by key. */
export async function getSetting(key: string): Promise<Setting> {
  return apiFetch<Setting>(`/api/v1/settings/${encodeURIComponent(key)}`);
}

/** Upsert (create or update) a setting.  Provide the new value and its
 * type.  Supported types include 'string', 'int', 'float' and 'bool'. */
export async function upsertSetting(key: string, value: unknown, type: string): Promise<Setting> {
  return apiFetch<Setting>(`/api/v1/settings/${encodeURIComponent(key)}`, {
    method: 'POST',
    body: JSON.stringify({ value, type }),
  });
}