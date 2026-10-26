import { defineConfig } from 'vite';

// base './' keeps every asset URL relative, so dist/ works at any sub-path
// (https://sh1ftmaker.github.io/spa-walkthrough/ and https://terminal.sels.tech/lp/<port>/).
export default defineConfig({
  base: './',
  publicDir: 'public',
  build: {
    target: 'es2022',
    outDir: 'dist',
    emptyOutDir: true,
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 1500,
  },
  server: { host: '127.0.0.1', port: 5173, strictPort: true, allowedHosts: true },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true, allowedHosts: true },
});
