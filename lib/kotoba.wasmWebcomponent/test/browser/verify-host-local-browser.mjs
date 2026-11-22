// KOTOBA-968: host-local storage and device.save in a real headless Chromium (synthetic probe, no network operation).
// usage: CHROME=/path/to/chromium node test/browser/verify-host-local-browser.mjs
// Serves this library on 127.0.0.1; the page mounts a sandboxed srcdoc guest that calls storage.* and device.save
// through the real channel, with the real IndexedDB backend. Checks: the guest has no IndexedDB/localStorage of its
// own; values persist across a reload; nothing is stored in plaintext and the app key is non-extractable; the
// conformance helper passes; device.save downloads nothing until a trusted click on 保存する, and the file name is
// reduced to its last segment.
import { spawn } from 'node:child_process'; import { createServer } from 'node:http'; import { readFile } from 'node:fs/promises';
import { join, normalize, extname } from 'node:path'; import { mkdtempSync, rmSync, readdirSync } from 'node:fs'; import { tmpdir } from 'node:os';
import assert from 'node:assert/strict';
const chrome = process.env.CHROME; if (!chrome) { console.error('set CHROME to a Chromium binary'); process.exit(2); }
const root = normalize(new URL('../../', import.meta.url).pathname);
const server = createServer(async (req, res) => {
  try { const file = normalize(join(root, req.url.split('?')[0].split('#')[0]));
        if (!file.startsWith(root)) throw 0;
        const bytes = await readFile(file);
        res.writeHead(200, { 'content-type': { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css' }[extname(file)] ?? 'application/octet-stream', 'cache-control': 'no-store' });
        res.end(bytes); } catch { if (!res.headersSent) res.writeHead(404); res.end(); }
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const profile = mkdtempSync(join(tmpdir(), 'kotoba-host-local-'));
const downloads = mkdtempSync(join(tmpdir(), 'kotoba-host-local-dl-'));
const browser = spawn(chrome, ['--headless', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run', 'about:blank'], { stdio: ['ignore', 'ignore', 'pipe'] });
const wsUrl = await new Promise((resolve, reject) => { let buf = ''; browser.stderr.on('data', (d) => { buf += d; const m = /ws:\/\/[^\s]+/.exec(buf); if (m) resolve(m[0]); }); setTimeout(() => reject(Error('chromium did not start')), 15000); });
const ws = new WebSocket(wsUrl); await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map(); const events = [];
ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } else events.push(m); };
const send = (method, params = {}, sessionId) => new Promise((r) => { const n = ++id; pending.set(n, r); ws.send(JSON.stringify({ id: n, method, params, sessionId })); });
const { result: { targetId } } = await send('Target.createTarget', { url: 'about:blank' });
const { result: { sessionId } } = await send('Target.attachToTarget', { targetId, flatten: true });
const s = (method, params) => send(method, params, sessionId);
await send('Browser.setDownloadBehavior', { behavior: 'allowAndName', downloadPath: downloads, eventsEnabled: true });
await s('Page.enable'); await s('Runtime.enable');
const evaluate = async (expression) => (await s('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result?.result?.value;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const until = async (expression, ms = 8000) => { for (let i = 0; i < ms / 50; i++) { const v = await evaluate(expression); if (v) return v; await sleep(50); } throw new Error(`timed out: ${expression}`); };
const page = `http://127.0.0.1:${server.address().port}/test/browser/client-runtime-host-local.html`;
async function press(label) {
  const rect = await evaluate(`(()=>{const b=[...document.querySelectorAll('dialog.kotoba-client-consent button')].find(b=>b.textContent===${JSON.stringify(label)});const r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
  for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) await s('Input.dispatchMouseEvent', { type, x: rect.x, y: rect.y, button: 'left', clickCount: 1 });
}
const step = (name) => `(window.log.find(([s]) => s === ${JSON.stringify(name)}) ?? [])[1]`;
const results = [];
try {
  for (const round of ['one', 'two']) {
    await s('Page.navigate', { url: page }); await until('window.ready === true');
    await evaluate(`window.run(${JSON.stringify(round)})`);
    await until(`window.log.some(([s]) => s === 'save-asked')`);
    assert.equal(await evaluate(step('guest-indexeddb')), 'SecurityError', 'the guest has no IndexedDB of its own');
    assert.equal(await evaluate(step('guest-localstorage')), 'SecurityError', 'the guest has no localStorage of its own');
    assert.equal(await evaluate(step('before')), round === 'one' ? null : 'MARKER-browser-plaintext-5e2c one', 'a value persists across a reload');
    assert.equal(await evaluate(step('get')), `MARKER-browser-plaintext-5e2c ${round}`);
    assert.equal(await evaluate(step('bad-key')), 'invalid-key');
    assert.equal((await evaluate('window.conformance')).conformant, true, 'conformance helper passes on the browser backend');
    const raw = await evaluate('window.rawContainsMarker()');
    assert.equal(raw.plaintext, false, 'no plaintext value or name in IndexedDB'); assert.deepEqual(raw.keys, [{ extractable: false, algorithm: 'AES-GCM' }, { extractable: false, algorithm: 'HMAC' }]);
    await until(`document.querySelector('dialog.kotoba-client-consent')?.open === true`);
    const dialog = await evaluate(`document.querySelector('dialog.kotoba-client-consent ul').textContent`);
    assert.ok(dialog.includes('probe.json'), dialog);
    await sleep(100);
    assert.equal(readdirSync(downloads).length, round === 'one' ? 0 : 1, 'nothing is saved before the click');
    await sleep(700); await press('保存する');
    await until(step('save'));
    assert.deepEqual(await evaluate(step('save')), { saved: true, name: 'probe.json' });
    await until(`true`); for (let i = 0; i < 60 && !events.some((e) => e.method === 'Browser.downloadProgress' && e.params.state === 'completed' && !e.seen); i++) await sleep(50);
    const done = events.find((e) => e.method === 'Browser.downloadProgress' && e.params.state === 'completed' && !e.seen);
    assert.ok(done, 'the approved save downloads a file'); done.seen = true;
    const begin = events.filter((e) => e.method === 'Browser.downloadWillBegin').at(-1);
    assert.equal(begin.params.suggestedFilename, 'probe.json');
    results.push(`${round}: ok`);
  }
  console.log(`PASS: KOTOBA-968 host-local in Chromium (${results.join(', ')}): guest has no own storage, values persist via the host, encrypted at rest with a non-extractable key, conformance helper passes, save only after a trusted click with a sanitized name`);
} finally {
  ws.close(); server.close();
  const exited = new Promise((r) => browser.once('exit', r)); browser.kill(); await Promise.race([exited, sleep(5000)]);
  for (const dir of [profile, downloads]) { try { rmSync(dir, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch { /* temporary directory */ } }
}
