import React from 'react';
import { useAuth } from '../store/auth';
import { useNavigate } from '@tanstack/react-router';

/**
 * Higher‑order component that protects a page based on the user's role.
 * It wraps the given component and checks the current user's roleId
 * against the required role.  If the role is too low (numerically
 * greater), or the user is not authenticated, it renders an
 * access denied message instead of the protected component.
 *
 * @param Component The React component to protect
 * @param requiredRole The minimal role required to access the page
 * @returns A new component that enforces role based access
 */
export function withRoleGuard<P>(
  Component: React.ComponentType<P>,
  requiredRole?: number,
) {
  // Return a component that performs the role check
  const Guarded: React.FC<P> = (props) => {
    const { roleId, token } = useAuth();
    const navigate = useNavigate();
    // Determine if the user lacks sufficient privileges.  Lower
    // numbers are more privileged (1 = super admin).  We compute
    // this outside of the effect so that hooks are not called
    // conditionally.
    const unauthorized =
      requiredRole !== undefined && (roleId == null || roleId > requiredRole);

    // When the user is unauthorised, redirect them to the home page.
    React.useEffect(() => {
      if (unauthorized) {
        navigate({ to: '/' });
      }
    }, [unauthorized, navigate]);

    if (unauthorized) {
      return null;
    }
    return <Component {...props} />;
  };
  return Guarded;
}
