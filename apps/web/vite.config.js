import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    allowedHosts: ['airex.rohitpt.online'],
    proxy: {
      '/api': 'http://localhost:8000',
      '^/health$': { target: 'http://localhost:8000', rewrite: (path) => path },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-charts': ['recharts'],
          'vendor-icons': ['lucide-react'],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test-setup.js',
    // Only run our app tests, not dependency test suites
    include: [
      'src/**/*.{test,spec}.{js,jsx,ts,tsx}',
      'tests/**/*.{test,spec}.{js,jsx,ts,tsx}',
    ],
    // Exclude Playwright E2E specs; they run via Playwright, not Vitest
    exclude: ['tests/e2e/**', 'node_modules/**'],
  },
})
