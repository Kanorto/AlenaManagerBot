import React from 'react';

/**
 * Home page placeholder.  This page is rendered after a successful
 * login and will eventually display dashboard statistics or other
 * content once individual modules are implemented.
 */
import { useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  // Redirect to events page on mount.  This ensures that the root path
  // (`/`) acts as an alias for the events module.  Without this, users
  // landing on `/` would see a placeholder page rather than the primary
  // events list.
  useEffect(() => {
    navigate({ to: '/events', replace: true });
  }, [navigate]);
  return null;
};

export default HomePage;