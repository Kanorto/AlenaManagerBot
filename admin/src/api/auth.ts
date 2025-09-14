import { apiFetch } from './client';
import type { operations } from './types.gen';

export type LoginRequest =
  operations['login_user_api_v1_users_login_post']['requestBody']['content']['application/json'];

export type LoginResponse =
  operations['login_user_api_v1_users_login_post']['responses'][200]['content']['application/json'];

/**
 * Authenticate the user with the backend.  On success, returns a JWT
 * token and an optional role ID.  When the credentials are invalid
 * the call will throw an error with the response message.
 */
export async function login(req: LoginRequest): Promise<LoginResponse> {
  return apiFetch<LoginResponse>('/api/v1/users/login', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}