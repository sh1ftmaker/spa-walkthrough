import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

const page = (f) => fileURLToPath(new URL(f, import.meta.url));

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
    // two pages: the walkthrough and the model gallery (gallery.html, data in public/gallery/)
    rollupOptions: { input: { main: page('./index.html'), gallery: page('./gallery.html') } },
  },
  server: { host: '127.0.0.1', port: 5173, strictPort: true, allowedHosts: true },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true, allowedHosts: true },
});
