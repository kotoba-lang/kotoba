const express = require('express');
const { home, homeEtag, todoHtml, liveHtml, port } = require('./common');
const app = express();
app.get('/', (req, res) => {
  res.set({ 'cache-control': 'no-cache', etag: homeEtag }).type('html');
  if (req.fresh) return res.status(304).end();
  res.send(home);
});
app.get('/live', (req, res) => { res.set('cache-control', 'no-cache').type('html').send(liveHtml()); });
app.get('/todos/:id', (req, res) => { res.set('cache-control', 'no-cache').type('html').send(todoHtml(req.params.id)); });
const s = app.listen(port, '127.0.0.1', () => console.log('PORT\t' + s.address().port));
