import { fixture, html } from '../../lib/fixture';
// The 304 scenario for Next.js. A force-static Route Handler ignores
// If-None-Match (it answers 200 + full body from its cache: measured with
// next 16.3.6), so revalidation has to be a dynamic handler that reads it.
export const dynamic = 'force-dynamic';
export function GET(request) {
  const { home, homeEtag } = fixture();
  if (request.headers.get('if-none-match') === homeEtag) return new Response(null, { status: 304, headers: { etag: homeEtag } });
  return html(home, { etag: homeEtag });
}
