import { apiFetch } from './client';
import type { components, operations } from './types.gen';

export type User = components['schemas']['UserRead'];
export type UserCreate = components['schemas']['UserCreate'];
export type UserUpdate =
  operations['update_user_api_v1_users__user_id__put']['requestBody']['content']['application/json'];

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