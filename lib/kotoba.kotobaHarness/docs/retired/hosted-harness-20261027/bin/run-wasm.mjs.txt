// Instantiates a kotoba wasm32-browser module through amu's official host
// (KOTOBA_BROWSER_HOST) and prints {"main": "<i64>"}.
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const host = await import(pathToFileURL(process.env.KOTOBA_BROWSER_HOST).href);
try {
  const h = await host.instantiateKotoba(readFileSync(process.argv[2]));
  console.log(JSON.stringify({main: String(h.instance.exports.main()), sha256: h.sha256}));
} catch (e) { console.log(JSON.stringify({trap: String(e.message || e)})); process.exitCode = 2; }
