import { apiFetch } from './client';

/**
 * Representation of a role returned by the API.  Roles have an id,
 * name and optional permissions payload.  The shape of ``permissions``
 * is not strictly defined in the spec and may be a JSON object or
 * array of strings.  Additional fields may be returned by the
 * backend in the future.
 */
export interface Role {
  id: number;
  name: string;
  permissions?: unknown;
  [key: string]: unknown;
}

/**
 * Payload for creating a new role.  The ``name`` field is required
 * and should be unique.  ``permissions`` may be provided as an
 * array of strings describing the allowed actions.
 */
export interface RoleCreate {
  name: string;
  permissions?: string[];
}

/**
 * Payload for updating an existing role.  Any of the fields may
 * optionally be specified.  Undefined values are omitted from the
 * request body so that only explicitly provided fields are
 * modified.
 */
export interface RoleUpdate {
  name?: string;
  permissions?: string[];
}

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
export interface RoleAssignPayload {
  user_id: number;
  role_id: number;
}
export async function assignRole(payload: RoleAssignPayload): Promise<void> {
  await apiFetch<void>('/api/v1/roles/assign', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}