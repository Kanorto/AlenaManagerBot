import { useAuth } from '../store/auth';
import { useNotifications } from '../store/notifications';

/**
 * A simple wrapper around the fetch API that applies the base URL and
 * Authorization header if a token is present.  All requests to the
 * FastAPI backend should use this helper to ensure consistent
 * handling of the base path and errors.  It returns the parsed JSON
 * response or throws an error when the response is not ok.
 */
export async function apiFetch<T>(
  input: string,
  init: RequestInit = {},
): Promise<T> {
  const { token } = useAuth.getState();
  const { addNotification } = useNotifications.getState();
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string>),
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Log the request details before sending.  Wrapped in try/catch to
  // avoid errors in environments where console is undefined.
  try {
    console.debug('apiFetch request', input, init);
  } catch {
    // console methods may not be available in all environments
  }

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${input}`, {
      ...init,
      headers,
    });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : String(err);
    try {
      console.error('apiFetch fetch error', message);
    } catch {
      // noop
    }
    addNotification(message, 'error');
    throw new Error(`Network error while fetching ${input}: ${message}`);
  }

  // Optional debug logging: emit response info to the console.  This helps
  // diagnose connectivity issues when developing.  Adjust the log level or
  // remove in production if not needed.
  try {
    console.debug('apiFetch response', response.status, response.statusText);
  } catch {
    // console methods may not be available in all environments
  }
  if (response.status === 401) {
    // Logout and redirect to login.  We cannot import the router here,
    // so we simply clear the token.  The AppShell will pick up the
    // missing token and render the login link.
    useAuth.getState().logout();
    addNotification('Unauthorized', 'error');
    throw new Error('Unauthorized');
  }
  if (!response.ok) {
    const errorText = await response.text();
    // Surface non‑OK responses as notifications.  Provide a generic
    // message when the body is empty.
    const message = errorText || response.statusText;
    try {
      console.error('apiFetch error', response.status, message);
    } catch {
      // noop
    }
    addNotification(message, 'error');
    throw new Error(message);
  }
  // Attempt to parse JSON; fallback to undefined for empty responses.
  try {
    return (await response.json()) as T;
  } catch {
    return undefined as unknown as T;
  }
}