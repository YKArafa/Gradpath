import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/register': 'http://localhost:8000',
      '/login': 'http://localhost:8000',
      '/token': 'http://localhost:8000',
      '/students': 'http://localhost:8000',
      '/analysis': 'http://localhost:8000',
      '/transcripts': 'http://localhost:8000',
    },
  },
});

