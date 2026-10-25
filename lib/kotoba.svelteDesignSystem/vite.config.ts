import { svelte } from '@sveltejs/vite-plugin-svelte';
import { resolve } from 'path';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [svelte()],
  build: {
    target: 'esnext',
    lib: {
      entry: resolve(__dirname, 'src/lib/index.ts'),
      formats: ['es'],
    },
  },
});
