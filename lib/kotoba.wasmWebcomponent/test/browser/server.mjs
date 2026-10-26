import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';

const root = normalize(new URL('../../', import.meta.url).pathname);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.wasm': 'application/wasm' };
const server = createServer(async (request, response) => {
  try {
    const relative = request.url === '/' ? 'test/browser/http-get-sab.html' : request.url.slice(1);
    const file = normalize(join(root, relative));
    if (!file.startsWith(root)) throw new Error('path denied');
    response.writeHead(200, {
      'content-type': types[extname(file)] || 'application/octet-stream',
      'cross-origin-opener-policy': 'same-origin',
      'cross-origin-embedder-policy': 'require-corp',
      'cross-origin-resource-policy': 'same-origin',
      'cache-control': 'no-store',
    });
    response.end(await readFile(file));
  } catch (_) {
    response.writeHead(404).end('not found');
  }
});
server.listen(Number(process.env.PORT || 0), '127.0.0.1', () => {
  console.log(`http://127.0.0.1:${server.address().port}/`);
});
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close(() => process.exit(0)));
