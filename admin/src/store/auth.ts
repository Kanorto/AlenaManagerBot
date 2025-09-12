import { create } from 'zustand';

/**
 * Zustand store for authentication state.  Holds the current JWT
 * token and the associated roleId.  Components can subscribe to
 * these values via the `useAuth` hook.  In later phases this
 * implementation may be extended to persist tokens to localStorage
 * or cookies.  For security reasons, keeping the token in memory
 * reduces exposure surface (it disappears on page refresh).
 */
interface AuthState {
  token: string | null;
  roleId: number | null;
  setToken: (token: string, roleId: number | null) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  token: null,
  roleId: null,
  setToken: (token: string, roleId: number | null) => set({ token, roleId }),
  logout: () => set({ token: null, roleId: null }),
}));