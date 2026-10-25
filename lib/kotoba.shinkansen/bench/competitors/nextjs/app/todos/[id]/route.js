import { fixture, html } from '../../../lib/fixture';
export const dynamic = 'force-dynamic';
export async function GET(_request, { params }) {
  const { id } = await params;
  return html(fixture().todoHtml(id));
}
