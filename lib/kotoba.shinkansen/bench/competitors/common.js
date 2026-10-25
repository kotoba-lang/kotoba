// Comparison fixture (not tooling): each competitor is written the way its
// own docs write it, so the numbers compare frameworks, not our Clojure.
// This is why these are plain JS — see bench/README.md.
const fs = require('node:fs');
const crypto = require('node:crypto');
const fx = JSON.parse(fs.readFileSync(process.env.FIXTURE, 'utf8'));
const head = fx.home.slice(0, fx.home.indexOf('<body>') + 6);
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const todoHtml = (id) => {
  const t = fx.todos.find((x) => x.id === id);
  return t
    ? `${head}<h1>${esc(t.text)}</h1><p>id ${t.id}${t.done ? ' — done' : ''}</p></body></html>`
    : `${head}<h1>no such todo</h1><p>${esc(id)}</p></body></html>`;
};
let n = 0;
const liveHtml = () => {
  n += 1;
  return `${head}<h1>live ${n}</h1><ul>${fx.todos.map((t) => `<li>${esc(t.text)}${t.done ? ' ✓' : ''}</li>`).join('')}</ul></body></html>`;
};
const homeEtag = '"' + crypto.createHash('sha256').update(fx.home).digest('hex') + '"';
module.exports = { fx, home: fx.home, homeEtag, todoHtml, liveHtml, port: +(process.env.PORT || 0) };
