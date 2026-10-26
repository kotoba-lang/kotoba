import {build} from 'esbuild';
import {mkdir, copyFile, readdir} from 'node:fs/promises';
const outdir = 'target/browser-tools';
await mkdir(`${outdir}/pyodide`, {recursive: true});
await mkdir(`${outdir}/licenses`, {recursive: true});
await build({entryPoints: {
  client: 'src/kuro/host/tools/client.js', worker: 'src/kuro/host/tools/worker.js',
  hermes: 'src/kuro/host/hermes/client.js', 'hermes-worker': 'src/kuro/host/hermes/worker.js', sessions:'src/kuro/host/hermes/sessions.js'
}, outdir, bundle: true, format: 'esm', platform: 'browser', target: 'es2022',
  loader: {'.wasm': 'file'}, plugins: [{name: 'pyodide-browser-assets', setup(b) {
    b.onResolve({filter: /^pyodide$/}, () => ({path: './pyodide/pyodide.mjs', external: true}));
  }}]});
for (const name of await readdir('node_modules/pyodide')) {
  if (/\.(mjs|wasm|zip|json)$/.test(name))
    await copyFile(`node_modules/pyodide/${name}`, `${outdir}/pyodide/${name}`);
}
await copyFile('examples/browser-tools/index.html', `${outdir}/index.html`);
await copyFile('examples/browser-tools/hermes.html', `${outdir}/hermes.html`);
await copyFile('node_modules/@jitl/quickjs-wasmfile-release-sync/dist/emscripten-module.wasm', `${outdir}/emscripten-module.wasm`);
await copyFile('node_modules/@jitl/quickjs-wasmfile-release-sync/LICENSE', `${outdir}/licenses/quickjs.txt`);
await copyFile('examples/browser-tools/THIRD_PARTY.md', `${outdir}/licenses/THIRD_PARTY.md`);

await copyFile('src/kuro/host/hermes/adapter.py', `${outdir}/hermes-adapter.py`);
