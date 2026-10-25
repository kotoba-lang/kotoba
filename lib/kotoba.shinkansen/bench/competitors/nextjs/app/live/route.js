import { fixture, html } from '../../lib/fixture';
export const dynamic = 'force-dynamic';
export function GET() {
  return html(fixture().liveHtml());
}
