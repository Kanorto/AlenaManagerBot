import React from 'react';
import {
  createRouter,
  RouterProvider,
  createRootRoute,
  createRoute,
} from '@tanstack/react-router';
import AppShell from './components/AppShell';
import LoginPage from './pages/Login';
import HomePage from './pages/Home';

// Import placeholder pages for each module.  These components
// will be replaced in later phases with fully functional views.
import DashboardPage from './pages/Dashboard';
import EventsPage from './pages/Events';
import UsersPage from './pages/Users';
import PaymentsPage from './pages/Payments';
import MailingsPage from './pages/Mailings';
import SupportPage from './pages/Support';
import ReviewsPage from './pages/Reviews';
import MessagesPage from './pages/Messages';
import FaqPage from './pages/Faq';
import SettingsPage from './pages/Settings';
import AuditPage from './pages/Audit';

// Import module definitions which drive dynamic route creation.
import { modules } from './modules/ModuleRegistry';
import { withRoleGuard } from './components/RoleGuard';

// We define a root route without a component.  This allows us to
// attach both the login route and the application shell as
// top‑level routes.  The root route simply renders an <Outlet/>,
// delegating all layout responsibility to its children.
const rootRoute = createRootRoute();

// The login route is attached directly under the root.  It does not
// render through the AppShell so that unauthenticated users see the
// login page instead of a blank screen.  Navigation to this route
// occurs when the user is not authenticated.
const loginRoute = createRoute({
  path: '/login',
  getParentRoute: () => rootRoute,
  component: LoginPage,
});

// Define an application wrapper route that uses the AppShell.  All
// authenticated pages live under this route.  When the user is
// logged in, AppShell will provide the sidebar, topbar and other
// chrome; when not authenticated, AppShell redirects to `/login`.
const appRoute = createRoute({
  path: '/',
  getParentRoute: () => rootRoute,
  component: AppShell,
});

// The home route lives under the application wrapper.  It simply
// redirects to the events module via the HomePage component.  This
// ensures that `/` acts as an alias for `/events` once inside the
// AppShell.
const homeRoute = createRoute({
  path: '/',
  getParentRoute: () => appRoute,
  component: HomePage,
});

// Dynamically create routes for each enabled module (except home).
// We map over the modules defined in ModuleRegistry and attach the
// appropriate placeholder component based on the module id.  In
// future phases these will point at real pages with server data.
const moduleRoutes = modules
  .filter((m) => m.id !== 'home' && m.enabled)
  .map((m) => {
    // Determine which placeholder component to render for this module.
    let Component: React.ComponentType;
    switch (m.id) {
      case 'dashboard':
        Component = DashboardPage;
        break;
      case 'events':
        Component = EventsPage;
        break;
      case 'users':
        Component = UsersPage;
        break;
      case 'payments':
        Component = PaymentsPage;
        break;
      case 'mailings':
        Component = MailingsPage;
        break;
      case 'support':
        Component = SupportPage;
        break;
      case 'reviews':
        Component = ReviewsPage;
        break;
      case 'messages':
        Component = MessagesPage;
        break;
      case 'faq':
        Component = FaqPage;
        break;
      case 'settings':
        Component = SettingsPage;
        break;
      case 'audit':
        Component = AuditPage;
        break;
      default:
        // Fallback for unknown modules; display a generic message.
        Component = () => <div className="p-4">Module not implemented.</div>;
    }
    // Wrap the component with a role guard.  This prevents users
    // with insufficient privileges from viewing the module even if
    // they manually navigate to its URL.
    const Guarded = withRoleGuard(Component, m.requiredRole);
    return createRoute({
      path: m.path,
      // Attach module routes to the application wrapper.  This ensures
      // they render within the AppShell and benefit from auth/role
      // guards.  Without this, the login route would erroneously
      // inherit the AppShell.
      getParentRoute: () => appRoute,
      component: Guarded,
    });
  });

// Build the route tree.  We include the login route, the home
// route, and all module routes.  Routes are declared here to
// enable code splitting and ensure TanStack Router knows about
// all available paths.
const routeTree = rootRoute.addChildren([
  // Login route lives directly under root
  loginRoute,
  // Application wrapper route (AppShell) with its children
  appRoute.addChildren([
    // Home redirect
    homeRoute,
    // All module routes
    ...moduleRoutes,
  ]),
]);

// Create the router instance.  The router controls navigation and
// provides hooks for redirects, loaders and actions.  See the
// implementation plan for integration with RBAC and guards.
export const router = createRouter({
  routeTree,
});

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

// Export a convenience component for providing the router.  This is
// consumed in `src/main.tsx`.
export function Router() {
  return <RouterProvider router={router} />;
}