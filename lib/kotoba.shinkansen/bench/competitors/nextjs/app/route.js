import { fixture, html } from '../lib/fixture';
// The static page the way Next.js serves static content: prerendered at
// `next build` (FIXTURE is read then) and answered from Next's cache.
// Revalidation (If-None-Match -> 304) is Next's own, on the ETag it generates.
export const dynamic = 'force-static';
export function GET() {
  const { home, homeEtag } = fixture();
  return html(home, { etag: homeEtag });
}
