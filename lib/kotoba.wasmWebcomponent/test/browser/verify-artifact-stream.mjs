// Qualifies host-stream artifacts in the canonical broker with a real headless Chromium.
// usage: CHROME=/path/to/chrome-headless-shell node test/browser/verify-artifact-stream.mjs
// Serves this library on 127.0.0.1, fakes https://artifacts.invalid and its CDN with the DevTools Fetch
// domain, and answers the canonical consent dialog with trusted input (Allow only after it has armed).
import { spawn } from 'node:child_process'; import { createServer } from 'node:http'; import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto'; import { join, normalize, extname } from 'node:path'; import { mkdtempSync, rmSync } from 'node:fs'; import { tmpdir } from 'node:os';
const chrome = process.env.CHROME; if (!chrome) { console.error('set CHROME to a Chromium/headless-shell binary'); process.exit(2); }
const root = normalize(new URL('../../', import.meta.url).pathname);
const size = 3 * 1024 * 1024 + 17;
const fixture = Buffer.alloc(size); for (let i = 0; i < size; i++) fixture[i] = (i * 31 + (i >> 9)) & 255;
const corrupt = Buffer.from(fixture); corrupt[size >> 1] ^= 1;
const sha256 = createHash('sha256').update(fixture).digest('hex');
const server = createServer(async (req, res) => {
  try { const file = normalize(join(root, req.url.split('?')[0].split('#')[0]));
        if (!file.startsWith(root)) throw 0;
        const bytes = await readFile(file); // read first: a missing file (favicon) must not follow a 200 header
        res.writeHead(200, { 'content-type': { '.html': 'text/html', '.js': 'text/javascript' }[extname(file)] ?? 'application/octet-stream', 'cache-control': 'no-store' });
        res.end(bytes); } catch { if (!res.headersSent) res.writeHead(404); res.end(); }
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const profile = mkdtempSync(join(tmpdir(), 'kotoba-artifact-'));
const browser = spawn(chrome, ['--headless', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run', 'about:blank'], { stdio: ['ignore', 'ignore', 'pipe'] });
const wsUrl = await new Promise((resolve, reject) => { let buf = ''; browser.stderr.on('data', (d) => { buf += d; const m = /ws:\/\/[^\s]+/.exec(buf); if (m) resolve(m[0]); }); setTimeout(() => reject(Error('chromium did not start')), 15000); });
const ws = new WebSocket(wsUrl); await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map(); const listeners = [];
ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } else listeners.forEach((l) => l(m)); };
const send = (method, params = {}, sessionId) => new Promise((r) => { const n = ++id; pending.set(n, r); ws.send(JSON.stringify({ id: n, method, params, sessionId })); });
const { result: { targetId } } = await send('Target.createTarget', { url: 'about:blank' });
const { result: { sessionId } } = await send('Target.attachToTarget', { targetId, flatten: true });
const s = (method, params) => send(method, params, sessionId);
const requests = [];
const cors = [{ name: 'access-control-allow-origin', value: '*' }];
const b64 = (buf) => buf.toString('base64');
listeners.push(async (m) => {
  if (m.method !== 'Fetch.requestPaused' || m.sessionId !== sessionId) return;
  const url = m.params.request.url; requests.push(url); const rid = m.params.requestId;
  const redirect = (to) => s('Fetch.fulfillRequest', { requestId: rid, responseCode: 302, responseHeaders: [...cors, { name: 'location', value: to }] });
  const body = (buf) => s('Fetch.fulfillRequest', { requestId: rid, responseCode: 200, responseHeaders: [...cors, { name: 'content-type', value: 'application/octet-stream' }], body: b64(buf) });
  if (url === 'https://artifacts.invalid/model' || url === 'https://artifacts.invalid/model-big') return redirect('https://eu.cdn.invalid/blob?sig=fixture');
  if (url === 'https://artifacts.invalid/model-bad') return redirect('https://eu.cdn.invalid/bad?sig=fixture');
  if (url === 'https://artifacts.invalid/model-elsewhere') return redirect('https://other.invalid/blob');
  if (url === 'https://eu.cdn.invalid/blob?sig=fixture' || url === 'https://other.invalid/blob') return body(fixture);
  if (url === 'https://eu.cdn.invalid/bad?sig=fixture') return body(corrupt);
  return s('Fetch.continueRequest', { requestId: rid });
});
await s('Fetch.enable', { patterns: [{ urlPattern: 'https://*' }] });
await s('Page.enable'); await s('Runtime.enable');
const page = `http://127.0.0.1:${server.address().port}/test/browser/client-runtime-artifact-stream.html#${encodeURIComponent(JSON.stringify({ sha256, size }))}`;
await s('Page.navigate', { url: page });
const evaluate = async (expression) => (await s('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result?.result?.value;
for (let i = 0; i < 50 && !(await evaluate('window.ready === true')); i++) await new Promise((r) => setTimeout(r, 100));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function dialogState() { return evaluate(`(()=>{const d=document.querySelector('dialog.kotoba-client-consent');return d&&d.open?{scope:d.querySelector('pre').textContent}:null})()`); }
async function press(label) {
  const rect = await evaluate(`(()=>{const b=[...document.querySelectorAll('dialog.kotoba-client-consent button')].find(b=>b.textContent===${JSON.stringify(label)});const r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
  for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) await s('Input.dispatchMouseEvent', { type, x: rect.x, y: rect.y, button: 'left', clickCount: 1 });
}
async function invoke(name, answer) {
  await evaluate(`void (window.__case = window.run(${JSON.stringify(name)}))`);
  let scope = null;
  for (let i = 0; i < 30 && !scope; i++) { await sleep(100); scope = (await dialogState())?.scope ?? null; }
  if (scope && answer) { await sleep(800); await press(answer); }
  const out = await evaluate('window.__case'); return { ...out, scope };
}
const results = []; const check = (name, ok, detail) => { results.push({ name, ok: !!ok }); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${ok ? '' : '  ' + JSON.stringify(detail)}`); };
const d = await evaluate('window.declarations()');
check('a host-stream artifact may declare a 2 GiB budget', d.streamedLarge === 0, d);
check('an in-memory artifact above 512 MiB is still refused', d.inMemoryLarge > 0, d);
check('an unknown delivery is refused', d.unknownDelivery > 0, d);
check('a host-stream budget above 64 GiB is refused', d.overStreamCap > 0, d);
check('in-memory verification refuses a host-stream declaration', d.refusedInMemory, d);
let n = requests.length; let r = await invoke('nosink', '続ける');
check('no host sink: refused before consent and before any request', !r.ok && /not host-supported/.test(r.error) && r.scope === null && requests.length === n, r);
n = requests.length; r = await invoke('good', '閉じる');
check('denied: nothing is requested and no sink is opened', !r.ok && requests.length === n && r.log.created === 0, r);
check('the consent dialog shows the artifact digest and budget', r.scope?.includes(sha256) && r.scope?.includes(`${size} bytes`), r.scope);
n = requests.length; r = await invoke('good', '続ける');
check('allowed: the artifact streams through the declared CDN redirect into the sink', r.ok && r.result.verified && r.result.bytes === size && r.result.sha256 === sha256 && r.log.written === size && r.log.closes.length === 1 && r.log.aborts.length === 0 && r.log.writes >= 1, r);
check('the sink result is returned as plain data', r.result?.sink?.stored === 'fixture.bin', r.result);
check('exactly the declared host and its redirect were requested', JSON.stringify(requests.slice(n)) === JSON.stringify(['https://artifacts.invalid/model', 'https://eu.cdn.invalid/blob?sig=fixture']), requests.slice(n));
r = await invoke('bad', '続ける');
check('a digest mismatch aborts the sink and never closes it', !r.ok && /digest mismatch/.test(r.error) && r.log.aborts[0] === 'digest-mismatch' && r.log.closes.length === 0, r);
r = await invoke('big', '続ける');
check('a body above the byte budget aborts the sink', !r.ok && /byte budget/.test(r.error) && r.log.aborts[0] === 'byte-budget' && r.log.closes.length === 0, r);
r = await invoke('elsewhere', '続ける');
check('an undeclared redirect origin is refused before any sink opens', !r.ok && /not declared/.test(r.error) && r.log.created === 0, r);
ws.close(); const exited = new Promise((r) => browser.once('exit', r)); browser.kill(); await exited; server.close(); rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
const passed = results.filter((x) => x.ok).length; console.log(`${passed} of ${results.length} checks`); process.exit(passed === results.length ? 0 : 1);
