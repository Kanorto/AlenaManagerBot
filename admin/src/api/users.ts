import { apiFetch } from './client';

/**
 * Representation of a user returned by the API.  This matches the
 * ``UserRead`` schema from the OpenAPI spec.  Additional fields
 * such as ``disabled`` or ``role_id`` may be present but are
 * optional on the frontend.  Whenever the backend adds new
 * properties they will be surfaced here automatically via index
 * signature.
 */
export interface User {
  id: number;
  email?: string | null;
  full_name?: string | null;
  disabled?: boolean | null;
  role_id?: number | null;
  [key: string]: unknown;
}

/**
 * Payload for creating a new user.  Administrators should provide
 * ``email`` and ``password``.  ``full_name`` is optional.  Social
 * providers may omit the password but supply ``social_provider`` and
 * ``social_id``.  See ``UserCreate`` schema for details.  For the
 * admin panel we limit creation to email/password based users.
 */
export interface UserCreate {
  email: string;
  password: string;
  full_name?: string | null;
  disabled?: boolean;
  role_id?: number | null;
}

/**
 * Payload for updating an existing user.  All fields are optional.
 * When a property is undefined it will not be sent to the server
 * (therefore no change).  Setting a property to null will clear it
 * on the backend if supported.  The ``role_id`` field will update
 * the user's role via the RoleService.
 */
export interface UserUpdate {
  email?: string | null;
  password?: string | null;
  full_name?: string | null;
  disabled?: boolean | null;
  role_id?: number | null;
}

/**
 * Fetch a list of users from the backend.  The API currently
 * returns all users without pagination.  In the future when
 * pagination is implemented this function should accept query
 * parameters for limit/offset and forward them accordingly.
 */
export async function getUsers(): Promise<User[]> {
  return apiFetch<User[]>('/api/v1/users/');
}

/**
 * Create a new user via POST /api/v1/users/.  Returns the created
 * user on success.  When the backend performs additional validation
 * (unique email, password strength) it may return 422 errors which
 * will surface through the apiFetch helper.
 */
export async function createUser(data: UserCreate): Promise<User> {
  return apiFetch<User>('/api/v1/users/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing user via PUT /api/v1/users/{id}.  Returns the
 * updated user on success.  Only fields present in the payload
 * will be updated; undefined values are omitted entirely.
 */
export async function updateUser(id: number, data: UserUpdate): Promise<User> {
  return apiFetch<User>(`/api/v1/users/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * Delete a user via DELETE /api/v1/users/{id}.  Returns void on
 * success.  Only administrators may delete users; the backend will
 * reject attempts to remove the primary administrator.
 */
export async function deleteUser(id: number): Promise<void> {
  await apiFetch<void>(`/api/v1/users/${id}`, {
    method: 'DELETE',
  });
}