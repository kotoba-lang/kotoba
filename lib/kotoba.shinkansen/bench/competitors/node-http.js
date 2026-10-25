const http = require('node:http');
const { home, homeEtag, todoHtml, liveHtml, port } = require('./common');
http.createServer((req, res) => {
  const url = req.url;
  if (url === '/') {
    if (req.headers['if-none-match'] === homeEtag) { res.writeHead(304, { etag: homeEtag }); return res.end(); }
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-cache', etag: homeEtag });
    return res.end(home);
  }
  if (url === '/live') {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-cache' });
    return res.end(liveHtml());
  }
  if (url.startsWith('/todos/')) {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-cache' });
    return res.end(todoHtml(url.slice(7)));
  }
  res.writeHead(404); res.end();
}).listen(port, '127.0.0.1', function () { console.log('PORT\t' + this.address().port); });
