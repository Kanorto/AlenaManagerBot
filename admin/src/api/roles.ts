import { apiFetch } from './client';
import type { operations } from './types.gen';

export type Role =
  operations['list_roles_api_v1_roles__get']['responses'][200]['content']['application/json'][number];
export type RoleCreate =
  operations['create_role_api_v1_roles__post']['requestBody']['content']['application/json'];
export type RoleUpdate =
  operations['update_role_api_v1_roles__role_id__put']['requestBody']['content']['application/json'];
export type RoleAssignPayload =
  operations['assign_role_api_v1_roles_assign_post']['requestBody']['content']['application/json'];

/**
 * Fetch a list of roles from the backend.  Only super
 * administrators may list roles.  The API does not currently
 * support pagination.
 */
export async function getRoles(): Promise<Role[]> {
  return apiFetch<Role[]>('/api/v1/roles/');
}

/**
 * Create a new role via POST /api/v1/roles/.  Returns the created
 * role.  Only super administrators may create roles.
 */
export async function createRole(data: RoleCreate): Promise<Role> {
  return apiFetch<Role>('/api/v1/roles/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing role via PUT /api/v1/roles/{id}.  Returns the
 * updated role.  Only super administrators may modify roles.
 */
export async function updateRole(id: number, data: RoleUpdate): Promise<Role> {
  return apiFetch<Role>(`/api/v1/roles/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * Delete a role via DELETE /api/v1/roles/{id}.  Returns void on
 * success.  Only super administrators may delete roles.
 */
export async function deleteRole(id: number): Promise<void> {
  await apiFetch<void>(`/api/v1/roles/${id}`, {
    method: 'DELETE',
  });
}

/**
 * Assign a role to a user via POST /api/v1/roles/assign.  The
 * request body must include ``user_id`` and ``role_id``.  The
 * backend returns no content on success.  Only super
 * administrators may assign roles.
 */
export async function assignRole(payload: RoleAssignPayload): Promise<void> {
  await apiFetch<void>('/api/v1/roles/assign', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}