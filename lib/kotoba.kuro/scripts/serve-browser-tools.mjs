import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve, extname, sep} from 'node:path';
import {pathToFileURL} from 'node:url';
export function serve(root = resolve('target/browser-tools'), port = 0, {handleRequest} = {}) {
  root = resolve(root);
  const server = http.createServer(async (req, res) => {
    try {
      if(req.headers.host !== `127.0.0.1:${server.address().port}`){res.writeHead(403);res.end();return;}
      if (handleRequest && await handleRequest(req, res)) return;
      const url = new URL(req.url, 'http://localhost');
      const file = resolve(root, '.' + decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname));
      if (!file.startsWith(root + sep)) {res.writeHead(403); return res.end();}
      const data = await readFile(file);
      res.writeHead(200, {'Content-Type': ({'.js': 'text/javascript', '.mjs': 'text/javascript', '.wasm': 'application/wasm', '.html': 'text/html', '.json': 'application/json'})[extname(file)] || 'application/octet-stream',
        'Cross-Origin-Opener-Policy': 'same-origin', 'Cross-Origin-Embedder-Policy': 'require-corp', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'});
      res.end(data);
    } catch {res.writeHead(404); res.end('not found');}
  });
  return new Promise((resolveReady, reject) => {
    server.on('error', reject);
    server.listen(port, '127.0.0.1', () => resolveReady({server, url: `http://127.0.0.1:${server.address().port}`}));
  });
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const {url} = await serve(undefined, 8123);
  console.log(url);
}
