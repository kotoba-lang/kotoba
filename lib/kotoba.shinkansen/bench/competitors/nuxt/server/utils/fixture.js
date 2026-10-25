// Same page, same todos, same templates as ../../../common.js; loaded lazily.
import fs from 'node:fs';

let fx;
export function fixture() {
  if (fx) return fx;
  const data = JSON.parse(fs.readFileSync(process.env.FIXTURE, 'utf8'));
  const head = data.home.slice(0, data.home.indexOf('<body>') + 6);
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
  let n = 0;
  fx = {
    home: data.home,
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

export function sendHtml(event, body) {
  setResponseHeaders(event, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-cache' });
  return body;
}
