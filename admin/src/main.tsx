import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from '@tanstack/react-router';
import { router } from './router';
import './index.css';

// Create a single QueryClient instance for the entire application.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Do not refetch on window focus by default; individual queries can override.
      refetchOnWindowFocus: false,
    },
  },
});

// Mount the React application to the DOM.  We use the new root API from React 18.
ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* RouterProvider wires the TanStack Router into React. */}
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);