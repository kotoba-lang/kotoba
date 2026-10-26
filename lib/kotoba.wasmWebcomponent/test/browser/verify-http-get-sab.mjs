import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { chromium } from 'playwright';

let browser;
let server;
try {
  server = spawn(process.execPath, ['test/browser/server.mjs'], {
    cwd: new URL('../..', import.meta.url),
    env: { ...process.env, PORT: '0' },
    stdio: ['ignore', 'pipe', 'inherit'],
  });
  const [chunk] = await once(server.stdout, 'data');
  const url = chunk.toString().trim();
  if (!url.startsWith('http://127.0.0.1:')) throw new Error(`unexpected server address: ${url}`);

  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto(url);
  await page.locator('#result[data-ok]').waitFor({ timeout: 10_000 });
  const result = await page.locator('#result').evaluate((element) => ({
    ok: element.dataset.ok,
    text: element.textContent,
  }));
  if (!await page.evaluate(() => crossOriginIsolated)) throw new Error('page is not cross-origin isolated');
  const expected = 'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok\nposted';
  if (result.ok !== 'true' || result.text !== expected) {
    throw new Error(`SAB HTTP bridge failed: ${JSON.stringify(result)}`);
  }
  console.log('browser SAB HTTP GET/POST bridge: ok');
} finally {
  if (browser) await browser.close();
  if (server && server.exitCode === null) {
    server.kill('SIGTERM');
    await once(server, 'exit');
  }
}
