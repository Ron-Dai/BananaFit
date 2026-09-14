import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backend = 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': backend,
      '/video_feed': backend,
      '/equipment_feed': backend,
      '/login': backend,
      '/register': backend,
      '/intake': backend,
      '/auth-static': backend,
    },
  },
});
