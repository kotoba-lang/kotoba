import {getQuickJS} from 'quickjs-emscripten';
import {loadPyodide} from 'pyodide';
import {filePath} from './client.js';

let outputBytes = 0, outputLimit, outputOverflow = false;
function output(stream, text) {
  text = String(text);
  outputBytes += new TextEncoder().encode(text).length;
  if (outputBytes > outputLimit) {outputOverflow = true; throw new Error('output exceeds byte limit');}
  self.postMessage({kind: 'output', stream, text});
}
async function javascript(args, maxMemoryBytes) {
  const engine = await getQuickJS();
  const runtime = engine.newRuntime();
  runtime.setMemoryLimit(maxMemoryBytes);
  runtime.setMaxStackSize(1024 * 1024);
  const vm = runtime.newContext();
  try {
    const print = vm.newFunction('__output', (stream, text) => output(vm.dump(stream), vm.dump(text)));
    vm.setProp(vm.global, '__output', print); print.dispose();
    const bootstrap = vm.evalCode(`
      globalThis.inputs = JSON.parse(${JSON.stringify(JSON.stringify(args.inputs || {}))});
      const workspace = JSON.parse(${JSON.stringify(JSON.stringify(args.files || {}))});
      const valid = p => typeof p === 'string' && p && !p.startsWith('/') && !p.includes('\\\\') && !p.includes('\\0') && !p.split('/').some(x => !x || x === '.' || x === '..');
      globalThis.fs = Object.freeze({readFile(p) {if (!valid(p) || !Object.hasOwn(workspace, p)) throw Error('file not found'); return workspace[p];},
        writeFile(p, text) {if (!valid(p) || typeof text !== 'string') throw Error('invalid file'); Object.defineProperty(workspace,p,{value:text,writable:true,enumerable:true,configurable:true});}});
      globalThis.console = Object.freeze({log: (...xs) => __output('stdout', xs.map(x => typeof x === 'string' ? x : JSON.stringify(x)).join(' ') + '\\n'),
        error: (...xs) => __output('stderr', xs.map(String).join(' ') + '\\n')});
      globalThis.__exportFiles = () => Object.fromEntries(${JSON.stringify(args.exportFiles || [])}.map(p => [p, fs.readFile(p)]));
    `);
    vm.unwrapResult(bootstrap).dispose();
    const evaluated = vm.evalCode(args.code, 'tool.js');
    if (evaluated.error) {
      const error = vm.dump(evaluated.error); evaluated.error.dispose();
      throw new Error(error?.message || JSON.stringify(error));
    }
    let value = evaluated.value;
    let result;
    try {
      while (runtime.hasPendingJob()) {
        const jobs = runtime.executePendingJobs(100);
        if (jobs.error) {
          const error = vm.dump(jobs.error); jobs.error.dispose();
          throw new Error(error?.message || 'JavaScript async job failed');
        }
      }
      const state = vm.getPromiseState(value);
      if (state.type === 'pending') throw new Error('Promise has no pending jobs; external async APIs are not provided');
      if (state.type === 'rejected') {
        const error = vm.dump(state.error); state.error.dispose();
        throw new Error(error?.message || String(error));
      }
      if (!state.notAPromise) {value.dispose(); value = state.value;}
      result = vm.dump(value);
    } finally {value.dispose();}
    const exported = vm.unwrapResult(vm.evalCode('__exportFiles()'));
    let files; try {files = vm.dump(exported);} finally {exported.dispose();}
    return {result: result ?? null, files};
  } finally {vm.dispose(); runtime.dispose();}
}
async function python(args) {
  const py = await loadPyodide({indexURL: new URL('./pyodide/', self.location.href).href});
  py.setStdout({batched: text => output('stdout', text + '\n')});
  py.setStderr({batched: text => output('stderr', text + '\n')});
  py.FS.mkdirTree('/workspace');
  py.FS.chdir('/workspace');
  for (const [path, text] of Object.entries(args.files || {})) {
    filePath(path);
    const target = '/workspace/' + path;
    py.FS.mkdirTree(target.slice(0, target.lastIndexOf('/')));
    py.FS.writeFile(target, text);
  }
  const globals = py.toPy({inputs: args.inputs || {}});
  try {
    const value = await py.runPythonAsync(args.code, {globals});
    globals.set('__tool_result', value ?? null);
    const json = py.runPython('import json\njson.dumps(__tool_result, ensure_ascii=False, allow_nan=False)', {globals});
    value?.destroy?.();
    const files = {};
    for (const path of args.exportFiles || []) {
      Object.defineProperty(files, path, {value: py.FS.readFile('/workspace/' + filePath(path), {encoding: 'utf8'}), enumerable: true});
    }
    return {result: JSON.parse(json), files};
  } finally {globals.destroy();}
}
self.onmessage = async ({data}) => {
  outputLimit = data.maxOutputBytes;
  try {
    const result = data.name === 'js' ? await javascript(data.args, data.maxMemoryBytes) : await python(data.args);
    if (outputOverflow) throw new Error('output exceeds byte limit');
    const encoded = JSON.stringify(result);
    if (new TextEncoder().encode(encoded).length > outputLimit) {outputOverflow = true; throw new Error('result exceeds byte limit');}
    self.postMessage({kind: 'done', ...JSON.parse(encoded)});
  } catch (err) {
    self.postMessage({kind: 'done', error: String(err?.message || err).slice(0, 4096), outputOverflow});
  }
};
