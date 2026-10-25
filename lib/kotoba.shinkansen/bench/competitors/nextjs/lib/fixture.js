// Same page, same todos, same templates as ../common.js. Loaded lazily at the
// first request: `next build` imports route modules without FIXTURE set.
import fs from 'node:fs';
import crypto from 'node:crypto';

let fx;
export function fixture() {
  if (fx) return fx;
  const data = JSON.parse(fs.readFileSync(process.env.FIXTURE, 'utf8'));
  const head = data.home.slice(0, data.home.indexOf('<body>') + 6);
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
  let n = 0;
  fx = {
    home: data.home,
    homeEtag: '"' + crypto.createHash('sha256').update(data.home).digest('hex') + '"',
    todoHtml: (id) => {
      const t = data.todos.find((x) => x.id === id);
      return t
        ? `${head}<h1>${esc(t.text)}</h1><p>id ${t.id}${t.done ? ' — done' : ''}</p></body></html>`
        : `${head}<h1>no such todo</h1><p>${esc(id)}</p></body></html>`;
    },
    liveHtml: () => {
      n += 1;
      return `${head}<h1>live ${n}</h1><ul>${data.todos.map((t) => `<li>${esc(t.text)}${t.done ? ' ✓' : ''}</li>`).join('')}</ul></body></html>`;
    },
  };
  return fx;
}

export const html = (body, extra = {}) =>
  new Response(body, { headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-cache', ...extra } });
