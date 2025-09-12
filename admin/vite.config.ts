import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

/**
 * Vite configuration for the EPS admin panel.  This configuration
 * enables React, TypeScript and Tailwind CSS support.  It also
 * loads `VITE_*` environment variables from `.env` and exposes
 * them to the client.  Absolute imports starting with `@/` map
 * to the `src` directory for convenience.
 */
export default defineConfig(({ mode }) => {
  // Load env file based on the current mode (development, production, etc.)
  const env = loadEnv(mode, process.cwd(), '');

  // Determine the API base URL.  Some developers accidentally set
  // VITE_API_BASE_URL to the literal string "null" or "undefined"
  // which causes http-proxy to crash when it tries to parse the URL.
  // Treat these cases as unset and fall back to localhost.
  // Normalize the API base URL.  Reject relative paths (e.g. "/api")
  // because http-proxy cannot parse them.  We treat values that are
  // undefined, "null", "undefined", or begin with a slash as unset and
  // fall back to localhost.  Otherwise we assume the developer provided
  // a valid absolute URL (e.g. "http://localhost:8000").
  const rawBase = env.VITE_API_BASE_URL;
  let apiBase: string;
  if (!rawBase || rawBase === 'null' || rawBase === 'undefined' || rawBase.startsWith('/')) {
    apiBase = 'http://localhost:8000';
  } else {
    apiBase = rawBase;
  }

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
    },
    css: {
      postcss: {
        plugins: [
          require('tailwindcss'),
          require('autoprefixer'),
        ],
      },
    },
    server: {
      port: 5173,
      open: true,
      proxy: {
        // Proxy API requests to backend.  During development you can set
        // VITE_API_BASE_URL to another value (e.g. http://localhost:8000).
        // The `apiBase` variable above normalises common placeholder values.
        '/api': {
          target: apiBase,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, '/api'),
        },
      },
    },
  };
});