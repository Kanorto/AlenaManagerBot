import React from 'react';
import { Link, useRouterState } from '@tanstack/react-router';
import { useAuth } from '../store/auth';
import { modules } from '../modules/ModuleRegistry';

/**
 * Sidebar renders the navigation for enabled modules.  It highlights
 * the current route based on the router's location.  Modules are
 * defined in `ModuleRegistry` and filtered by feature flags and
 * permissions.  During the foundational phase, only the home route
 * is available.
 */
const Sidebar: React.FC = () => {
  const { token, roleId } = useAuth();
  const { location } = useRouterState();

  // Filter modules based on runtime permissions and feature flags.  A
  // module may specify a required role; only modules with a
  // requiredRole less than or equal to the user's roleId are shown.
  // Filter modules based on runtime permissions and feature flags.  A
  // module may specify a required role; only modules with a
  // requiredRole greater than or equal to the user's roleId are
  // shown.  Note that a lower numeric roleId corresponds to more
  // privileges (1 = super admin, 2 = admin, 3 = user).
  const availableModules = modules.filter((m) => {
    if (!m.enabled) return false;
    if (m.requiredRole === undefined) return true;
    // If no roleId (e.g. not logged in) hide modules with
    // required roles.  Otherwise allow viewing if the user's
    // roleId is less than or equal to the required role.
    if (roleId == null) return false;
    return roleId <= m.requiredRole;
  });

  return (
    <nav className="w-56 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 py-4 px-2">
      <ul className="space-y-2">
        {availableModules.map((mod) => {
          const active = location.pathname.startsWith(mod.path);
          return (
            <li key={mod.id}>
              <Link
                to={mod.path}
                className={`block px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-700 ${
                  active ? 'bg-gray-200 dark:bg-gray-900 font-semibold' : ''
                }`}
              >
                {mod.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
};

export default Sidebar;