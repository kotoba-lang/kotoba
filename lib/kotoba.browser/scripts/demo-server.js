#!/usr/bin/env node
'use strict';

/**
 * Real, minimal local dev server for kotoba-lang/browser's own runnable
 * demo (public/browser-demo.html + src/browser/demo.cljk, shadow-cljs's
 * :browser-demo build target).
 *
 * shadow-cljs's own devtools http server (see shadow-cljs.edn's
 * :http-root "public" / :http-port 8702) is a plain static file server:
 * fine for the demo's original flexbox/grid/WebGL/document.title proof,
 * but this demo now ALSO proves real WebSocket networking, real Worker
 * execution, and real fetch() response delivery (see
 * src/browser/demo.cljk's `init!`) -- each of which needs a REAL server on
 * the other end for the compiled demo bundle's own real, native
 * `js/fetch`/`js/WebSocket` calls to talk to. This script is that server:
 * it serves the SAME static `public/` files shadow-cljs's devtools server
 * does, PLUS three real endpoints:
 *
 *   GET  /worker.js       -- real JS source for `new Worker(...)` to
 *                            really fetch and really execute in a second
 *                            QuickJS context (mirrors
 *                            test-cljs/browser/compat/quickjs_worker_smoke_test.cljk's
 *                            worker-echo-server).
 *   GET  /api/fetch-data  -- a real plain-text body for `fetch(...)` to
 *                            really retrieve (mirrors
 *                            quickjs_fetch_smoke_test.cljs's
 *                            fetch-echo-server).
 *   WS   /ws-echo         -- a real, minimal, hand-rolled RFC6455 echo
 *                            server (real HTTP-Upgrade handshake incl. a
 *                            real Sec-WebSocket-Accept computation, real
 *                            frame parsing/framing, echoes back whatever
 *                            real text frame it receives) -- the same
 *                            algorithm
 *                            quickjs_websocket_smoke_test.cljs's
 *                            websocket-echo-server uses, ported to plain
 *                            Node (this file is NOT compiled by
 *                            shadow-cljs, so it is hand-written JS rather
 *                            than a require'd compiled artifact) and hung
 *                            off the SAME http.Server's 'upgrade' event so
 *                            one process / one port serves everything the
 *                            demo needs.
 *
 * No new dependency: only Node's own built-in `http`, `crypto`, `fs`,
 * `path` modules, exactly like the smoke tests this mirrors.
 *
 * Usage: node scripts/demo-server.js [port]   (default port 8703, chosen
 * to not collide with shadow-cljs's own devtools server on 8702).
 */

const http = require('http');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const PORT = Number(process.argv[2]) || Number(process.env.PORT) || 8703;
const PUBLIC_DIR = path.join(__dirname, '..', 'public');

const WORKER_SCRIPT_SOURCE =
  "self.onmessage = function(e) { self.postMessage(e.data * 2); };";

const FETCH_DATA_BODY =
  'hello real fetch, from the real kotoba-lang/browser demo server';

const CONTENT_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
};

function contentTypeFor(filePath) {
  return CONTENT_TYPES[path.extname(filePath)] || 'application/octet-stream';
}

function serveStatic(req, res) {
  const urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
  const relative = urlPath === '/' ? '/browser-demo.html' : urlPath;
  const filePath = path.join(PUBLIC_DIR, relative);
  // Guard against path traversal outside PUBLIC_DIR.
  if (!filePath.startsWith(PUBLIC_DIR)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not found: ' + relative);
      return;
    }
    res.writeHead(200, { 'Content-Type': contentTypeFor(filePath) });
    res.end(data);
  });
}

const server = http.createServer((req, res) => {
  const urlPath = (req.url || '/').split('?')[0];
  if (req.method === 'GET' && urlPath === '/worker.js') {
    res.writeHead(200, {
      'Content-Type': 'text/javascript; charset=utf-8',
      'Access-Control-Allow-Origin': '*',
    });
    res.end(WORKER_SCRIPT_SOURCE);
    return;
  }
  if (req.method === 'GET' && urlPath === '/api/fetch-data') {
    res.writeHead(200, {
      'Content-Type': 'text/plain; charset=utf-8',
      'Access-Control-Allow-Origin': '*',
    });
    res.end(FETCH_DATA_BODY);
    return;
  }
  serveStatic(req, res);
});

// ---------------------------------------------------------------------
// Real, minimal RFC6455 WebSocket echo server on /ws-echo, hand-rolled on
// Node's built-in `net` (via the raw socket the 'upgrade' event hands us)
// + `crypto` -- ports
// test-cljs/browser/compat/quickjs_websocket_smoke_test.cljk's
// websocket-echo-server algorithm (that file's own docstring explains why
// this is hand-rolled rather than a dependency: RFC6455 in ~80 lines is a
// small, well-understood surface, and this repo already avoids adding new
// runtime dependencies for its real I/O implementations -- e.g.
// browser.net.http/browser.net.websocket use only java.net.http / the
// host JS runtime's own globals).
// ---------------------------------------------------------------------

const WEBSOCKET_MAGIC = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11';

function acceptValue(key) {
  return crypto.createHash('sha1').update(key + WEBSOCKET_MAGIC).digest('base64');
}

function tryParseFrame(buf) {
  if (buf.length < 2) return null;
  const b0 = buf.readUInt8(0);
  const b1 = buf.readUInt8(1);
  const opcode = b0 & 0x0f;
  const masked = (b1 & 0x80) !== 0;
  const len0 = b1 & 0x7f;
  const headerExtra = len0 === 126 ? 2 : len0 === 127 ? 8 : 0;
  const maskLen = masked ? 4 : 0;
  if (buf.length < 2 + headerExtra + maskLen) return null;
  let payloadLen;
  if (len0 === 126) payloadLen = buf.readUInt16BE(2);
  else if (len0 === 127) payloadLen = Number(buf.readBigUInt64BE(2));
  else payloadLen = len0;
  const maskOffset = 2 + headerExtra;
  const payloadOffset = maskOffset + maskLen;
  const total = payloadOffset + payloadLen;
  if (buf.length < total) return null;
  let payload = buf.slice(payloadOffset, total);
  if (masked) {
    const maskKey = buf.slice(maskOffset, maskOffset + 4);
    const out = Buffer.alloc(payloadLen);
    for (let i = 0; i < payloadLen; i++) {
      out.writeUInt8(payload.readUInt8(i) ^ maskKey.readUInt8(i % 4), i);
    }
    payload = out;
  }
  return { opcode, payload, consumed: total };
}

function writeFrame(socket, opcode, payload) {
  const len = payload.length;
  let header;
  if (len < 126) {
    header = Buffer.from([0x80 | opcode, len]);
  } else if (len < 65536) {
    header = Buffer.alloc(4);
    header.writeUInt8(0x80 | opcode, 0);
    header.writeUInt8(126, 1);
    header.writeUInt16BE(len, 2);
  } else {
    header = Buffer.alloc(10);
    header.writeUInt8(0x80 | opcode, 0);
    header.writeUInt8(127, 1);
    header.writeBigUInt64BE(BigInt(len), 2);
  }
  socket.write(Buffer.concat([header, payload]));
}

function drainFrames(socket, state) {
  for (;;) {
    const frame = tryParseFrame(state.buffer);
    if (!frame) return;
    state.buffer = state.buffer.slice(frame.consumed);
    if (frame.opcode === 1) writeFrame(socket, 1, frame.payload);
    else if (frame.opcode === 8) writeFrame(socket, 8, Buffer.alloc(0));
    else if (frame.opcode === 9) writeFrame(socket, 0xa, frame.payload);
  }
}

server.on('upgrade', (req, socket, head) => {
  const urlPath = (req.url || '/').split('?')[0];
  if (urlPath !== '/ws-echo') {
    socket.destroy();
    return;
  }
  const acceptKey = req.headers['sec-websocket-key'];
  if (!acceptKey) {
    socket.destroy();
    return;
  }
  const accept = acceptValue(acceptKey);
  socket.write(
    'HTTP/1.1 101 Switching Protocols\r\n' +
    'Upgrade: websocket\r\n' +
    'Connection: Upgrade\r\n' +
    'Sec-WebSocket-Accept: ' + accept + '\r\n' +
    '\r\n'
  );
  const state = { buffer: head && head.length ? head : Buffer.alloc(0) };
  drainFrames(socket, state);
  socket.on('data', (chunk) => {
    state.buffer = Buffer.concat([state.buffer, chunk]);
    drainFrames(socket, state);
  });
  socket.on('error', () => {});
});

server.listen(PORT, '127.0.0.1', () => {
  /* eslint-disable no-console */
  console.log('kotoba-lang/browser demo server listening on http://127.0.0.1:' + PORT);
  console.log('  demo page:       http://127.0.0.1:' + PORT + '/browser-demo.html');
  console.log('  worker script:   http://127.0.0.1:' + PORT + '/worker.js');
  console.log('  fetch endpoint:  http://127.0.0.1:' + PORT + '/api/fetch-data');
  console.log('  websocket echo:  ws://127.0.0.1:' + PORT + '/ws-echo');
  /* eslint-enable no-console */
});
