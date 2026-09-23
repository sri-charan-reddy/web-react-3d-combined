import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * The Python mission-control server (run_dashboard.py) owns the simulation
 * engine and every /api route. In dev we proxy to it so the React app runs on
 * Vite's HMR server while talking to the real backend; `npm run build` emits a
 * static bundle the Python server can serve directly.
 */
const BACKEND = process.env.VITE_BACKEND_URL ?? 'http://localhost:8080';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: BACKEND,
        changeOrigin: true,
        // SSE (/api/stream) must not be buffered or the telemetry feed stalls.
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              proxyRes.headers['cache-control'] = 'no-cache, no-transform';
            }
          });
        },
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    // The only chunk over the default 500 kB warning is three.js, which is
    // lazy-loaded with the 3D tab and never touches the initial page load.
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom'],
          // three lands in its own chunk, fetched only when the 3D tab opens.
          three: ['three'],
        },
      },
    },
  },
});
