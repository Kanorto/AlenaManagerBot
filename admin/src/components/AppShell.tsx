import React, { useEffect } from 'react';
import { Outlet, useNavigate } from '@tanstack/react-router';
import { useAuth } from '../store/auth';
import Sidebar from './Sidebar';
import Notifications from './Notifications';

/**
 * AppShell defines the chrome of the application: sidebar, topbar
 * and a content area.  All authenticated pages render as children
 * inside the <Outlet/> component provided by TanStack Router.
 */
const AppShell: React.FC = () => {
  const { token, logout } = useAuth();
  const navigate = useNavigate();

  // When the user is not authenticated, redirect to the login page.  Since
  // the login route resides outside of the AppShell, we simply trigger
  // navigation in an effect and render nothing while the redirect occurs.
  useEffect(() => {
    if (!token) {
      navigate({ to: '/login', replace: true });
    }
  }, [token, navigate]);

  if (!token) {
    return null;
  }

  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        {/* Topbar */}
        <header className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800">
          <h1 className="text-lg font-semibold">EPS Admin Panel</h1>
          <button
            onClick={logout}
            className="text-sm text-red-600 hover:text-red-800"
          >
            Logout
          </button>
        </header>
        {/* Page content */}
        <main className="p-4 flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
      {/* Notifications area */}
      <Notifications />
    </div>
  );
};

export default AppShell;