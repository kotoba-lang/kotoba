// Comparison fixture: Nuxt 4 / Nitro with defaults. `/` is prerendered at
// build (served by Nitro's static handler, which answers If-None-Match
// itself); the rest are server routes. See bench/README.md.
export default defineNuxtConfig({
  compatibilityDate: '2026-09-01',
  ssr: true,
  nitro: { prerender: { routes: ['/'] } },
});
