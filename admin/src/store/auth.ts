import { create } from 'zustand';

/**
 * Zustand store for authentication state.  Holds the current JWT
 * token and the associated roleId.  Components can subscribe to
 * these values via the `useAuth` hook. Tokens are mirrored to
 * `sessionStorage` so that refreshing the page preserves the
 * session while still clearing credentials when the tab closes.
 * Avoid storing tokens in `localStorage` because data persists
 * indefinitely and can be exfiltrated by XSS.
 */
interface AuthState {
  token: string | null;
  roleId: number | null;
  setToken: (token: string, roleId: number | null) => void;
  logout: () => void;
}

const TOKEN_KEY = 'authToken';
const ROLE_KEY = 'authRoleId';

const loadToken = (): { token: string | null; roleId: number | null } => {
  if (typeof sessionStorage === 'undefined') {
    return { token: null, roleId: null };
  }
  const token = sessionStorage.getItem(TOKEN_KEY);
  const roleIdStr = sessionStorage.getItem(ROLE_KEY);
  return { token, roleId: roleIdStr ? Number(roleIdStr) : null };
};

export const useAuth = create<AuthState>((set) => ({
  ...loadToken(),
  setToken: (token: string, roleId: number | null) => {
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.setItem(TOKEN_KEY, token);
      if (roleId !== null) {
        sessionStorage.setItem(ROLE_KEY, roleId.toString());
      } else {
        sessionStorage.removeItem(ROLE_KEY);
      }
    }
    set({ token, roleId });
  },
  logout: () => {
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(ROLE_KEY);
    }
    set({ token: null, roleId: null });
  },
}));
