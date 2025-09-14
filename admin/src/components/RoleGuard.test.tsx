/** @vitest-environment jsdom */

import React from 'react';
import { render, waitFor } from '@testing-library/react';
import { vi, describe, it, expect } from 'vitest';
import { withRoleGuard } from './RoleGuard';

// Mock authentication hook to return low privileged role
vi.mock('../store/auth', () => ({
  useAuth: () => ({ roleId: 3, token: 'fake' }),
}));

// Mock notifications store
const addNotification = vi.fn();
vi.mock('../store/notifications', () => ({
  useNotifications: () => ({ addNotification }),
}));

// Mock navigate hook
const navigate = vi.fn();
vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigate,
}));

describe('withRoleGuard', () => {
  it('redirects and notifies when role is below required', async () => {
    const Protected = () => <div>Protected content</div>;
    const Guarded = withRoleGuard(Protected, 1);
    const { getByText } = render(<Guarded />);

    // Ensure side effects executed
    await waitFor(() => {
      expect(navigate).toHaveBeenCalledWith({ to: '/login' });
      expect(addNotification).toHaveBeenCalledWith('Access denied', 'error');
    });

    // Access denied message rendered
    getByText('Access denied');
  });
});
