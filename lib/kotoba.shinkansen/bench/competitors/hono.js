const { Hono } = require('hono');
const { serve } = require('@hono/node-server');
const { home, homeEtag, todoHtml, liveHtml, port } = require('./common');
const app = new Hono();
app.get('/', (c) => {
  if (c.req.header('if-none-match') === homeEtag) return c.body(null, 304, { etag: homeEtag });
  return c.html(home, 200, { 'cache-control': 'no-cache', etag: homeEtag });
});
app.get('/live', (c) => c.html(liveHtml(), 200, { 'cache-control': 'no-cache' }));
app.get('/todos/:id', (c) => c.html(todoHtml(c.req.param('id')), 200, { 'cache-control': 'no-cache' }));
serve({ fetch: app.fetch, port, hostname: '127.0.0.1' }, (i) => console.log('PORT\t' + i.port));
