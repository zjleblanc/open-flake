import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import basicSsl from '@vitejs/plugin-basic-ssl';

export default defineConfig(({ mode }) => ({
  plugins: [react(), ...(mode === 'https' ? [basicSsl()] : [])],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/oauth_token.do': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
}));
