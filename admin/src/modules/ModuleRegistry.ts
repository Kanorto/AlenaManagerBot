import React from 'react';

/**
 * Module definitions for the EPS admin panel.  Each module defines a
 * route path, navigation label and required role.  Build‑time
 * feature flags (VITE_ENABLE_<MODULE>) and runtime flags (public/config.json)
 * determine whether a module is included and visible.  During the
 * foundational phase only the home module is enabled.
 */
export interface ModuleDef {
  id: string;
  label: string;
  path: string;
  // The minimal role required to view the module (lower means more
  // privileged, e.g. 1 = super admin, 2 = admin, 3 = user).  If
  // undefined, no role check is enforced.
  requiredRole?: number;
  enabled: boolean;
}

// Determine feature flags from environment variables.  Vite exposes
// variables prefixed with `VITE_` on `import.meta.env`.
const env = import.meta.env;

// Build the list of modules.  We always include the home module and
// then conditionally append additional modules based on build‑time
// feature flags.  Each module has an id, human friendly label, path
// and a minimal required role.  If no requiredRole is specified
// the module is visible to all authenticated users.  When
// implemented, role checks will hide or disable modules for users
// with insufficient privileges.
export const modules: ModuleDef[] = [];

// Always include the home module.
modules.push({
  id: 'home',
  label: 'Home',
  path: '/',
  requiredRole: undefined,
  enabled: true,
});

// Helper to read a boolean feature flag from the environment.  Vite
// exposes variables prefixed with `VITE_` as strings.  We treat
// `'true'` (case sensitive) as enabled and any other value as
// disabled.
function isEnabled(flag?: string): boolean {
  return flag === 'true';
}

// Dashboard module.  Requires super admin (role <= 1).
if (isEnabled(env.VITE_ENABLE_DASHBOARD)) {
  modules.push({
    id: 'dashboard',
    label: 'Dashboard',
    path: '/dashboard',
    requiredRole: 1,
    enabled: true,
  });
}

// Events module.  Accessible to admins and above (role <= 2).
if (isEnabled(env.VITE_ENABLE_EVENTS)) {
  modules.push({
    id: 'events',
    label: 'Events',
    path: '/events',
    requiredRole: 2,
    enabled: true,
  });
}

// Users & Roles module.  Super admin only by default.
if (isEnabled(env.VITE_ENABLE_USERS)) {
  modules.push({
    id: 'users',
    label: 'Users',
    path: '/users',
    requiredRole: 1,
    enabled: true,
  });
}

// Payments module.  Accessible to admins.
if (isEnabled(env.VITE_ENABLE_PAYMENTS)) {
  modules.push({
    id: 'payments',
    label: 'Payments',
    path: '/payments',
    requiredRole: 2,
    enabled: true,
  });
}

// Mailings module.  Accessible to admins.
if (isEnabled(env.VITE_ENABLE_MAILINGS)) {
  modules.push({
    id: 'mailings',
    label: 'Mailings',
    path: '/mailings',
    requiredRole: 2,
    enabled: true,
  });
}

// Support module.  Accessible to admins.
if (isEnabled(env.VITE_ENABLE_SUPPORT)) {
  modules.push({
    id: 'support',
    label: 'Support',
    path: '/support',
    requiredRole: 2,
    enabled: true,
  });
}

// Reviews module.  Accessible to admins.
if (isEnabled(env.VITE_ENABLE_REVIEWS)) {
  modules.push({
    id: 'reviews',
    label: 'Reviews',
    path: '/reviews',
    requiredRole: 2,
    enabled: true,
  });
}

// Messages (bot templates) module.  Accessible to admins.
if (isEnabled(env.VITE_ENABLE_MESSAGES)) {
  modules.push({
    id: 'messages',
    label: 'Messages',
    path: '/messages',
    requiredRole: 2,
    enabled: true,
  });
}

// FAQ module.  Accessible to admins.
if (isEnabled(env.VITE_ENABLE_FAQ)) {
  modules.push({
    id: 'faq',
    label: 'FAQ',
    path: '/faq',
    requiredRole: 2,
    enabled: true,
  });
}

// Settings module.  Super admin only.
if (isEnabled(env.VITE_ENABLE_SETTINGS)) {
  modules.push({
    id: 'settings',
    label: 'Settings',
    path: '/settings',
    requiredRole: 1,
    enabled: true,
  });
}

// Audit logs module.  Super admin only.
if (isEnabled(env.VITE_ENABLE_AUDIT)) {
  modules.push({
    id: 'audit',
    label: 'Audit Logs',
    path: '/audit',
    requiredRole: 1,
    enabled: true,
  });
}