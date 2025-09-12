import { apiFetch } from './client';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  role_id?: number;
}

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