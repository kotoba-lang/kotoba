import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { safeBuilder } from '@etzhayyim/vite-plugin-safe-builder';

export default defineConfig({
  plugins: [...safeBuilder({ routeCanonical: { trailingSlash: 'always' } }), sveltekit()],
  server: { allowedHosts: true }
});
