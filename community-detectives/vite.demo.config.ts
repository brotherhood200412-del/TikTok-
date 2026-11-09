import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

/** Browser-Vorschau ohne Server (statische Dateien mit relativen Pfaden). */
export default defineConfig({
  root: 'web',
  base: './',
  plugins: [react(), tailwindcss()],
  build: {
    outDir: '../dist/demo',
    emptyOutDir: true,
    chunkSizeWarningLimit: 2000,
    rollupOptions: {
      input: 'web/demo.html',
      output: { entryFileNames: 'assets/demo.js', chunkFileNames: 'assets/[name].js', assetFileNames: 'assets/[name][extname]' },
    },
  },
});
