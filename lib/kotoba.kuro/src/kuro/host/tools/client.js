// Browser host boundary. Each call gets a fresh Worker/runtime and filesystem.
export const toolDefinitions = ['js', 'python'].map(name => ({
  type: 'function', function: {name, description: `Execute ${name} in a browser Worker.`,
    parameters: {type: 'object', additionalProperties: false, required: ['code'], properties: {
      code: {type: 'string'}, inputs: {type: 'object'}, files: {type: 'object', additionalProperties: {type: 'string'}},
      exportFiles: {type: 'array', items: {type: 'string'}}
    }}}
}));
const encoder = new TextEncoder();
const bytes = x => encoder.encode(x).length;
export function toToolMessage(response) {
  if (typeof response.id !== 'string' || !response.id) throw new Error('tool response requires a call id');
  return {role: 'tool', tool_call_id: response.id,
    content: JSON.stringify({result: response.result, files: response.files, receipt: response.receipt})};
}
export function filePath(path) {
  if (typeof path !== 'string' || !path || path.startsWith('/') || path.includes('\\') ||
      path.includes('\0') || path.split('/').some(p => !p || p === '.' || p === '..'))
    throw new Error('invalid workspace-relative file path');
  return path;
}
export function createToolHost({capabilities = [], workerUrl = new URL('./worker.js', import.meta.url),
  timeoutMs = 30000, maxInputBytes = 1048576, maxOutputBytes = 1048576,
  maxMemoryBytes = 67108864, makeWorker = url => new Worker(url, {type: 'module'})} = {}) {
  for (const value of [timeoutMs, maxInputBytes, maxOutputBytes, maxMemoryBytes])
    if (!Number.isSafeInteger(value) || value <= 0) throw new Error('limits must be positive safe integers');
  if (timeoutMs > 2147483647) throw new Error('deadline exceeds browser timer range');
  const grants = new Set(capabilities);
  return {async call(toolCall, {signal} = {}) {
    const start = Date.now();
    const name = toolCall?.function?.name;
    const runtimeIsolation = name === 'js' ? 'quickjs-wasm-worker' : 'pyodide-worker-js-bridge';
    let isolation = 'none';
    const base = {'kuro/type': 'kuro/receipt', 'kuro/isolation': isolation,
      'kuro/argv': ['browser-tool', String(name)], 'kuro/started-at': start};
    const finish = ({result = null, files = {}, stdout = '', stderr = '', exitCode = 0, error,
      timedOut = false, truncated = false} = {}) => ({id: toolCall?.id, result, files, receipt: {
        ...base, 'kuro/isolation': isolation, 'kuro/stdout': stdout, 'kuro/stderr': stderr, 'kuro/exit-code': exitCode,
        'kuro/error': error, 'kuro/timed-out?': timedOut, 'kuro/truncated?': truncated,
        'kuro/stdout-bytes': bytes(stdout), 'kuro/stderr-bytes': bytes(stderr),
        'kuro/finished-at': Date.now(), 'kuro/duration-ms': Date.now() - start}});
    let args;
    try {
      if (!['js', 'python'].includes(name)) throw new Error('unknown tool');
      args = typeof toolCall.function.arguments === 'string' ? JSON.parse(toolCall.function.arguments) : toolCall.function.arguments;
      if (!args || typeof args.code !== 'string' || Object.keys(args).some(k => !['code', 'inputs', 'files', 'exportFiles'].includes(k)))
        throw new Error('invalid tool arguments');
      if (args.inputs != null && (typeof args.inputs !== 'object' || Array.isArray(args.inputs))) throw new Error('inputs must be an object');
      if (args.files != null && (typeof args.files !== 'object' || Array.isArray(args.files))) throw new Error('files must be an object');
      if (args.exportFiles != null && !Array.isArray(args.exportFiles)) throw new Error('exportFiles must be an array');
      for (const [path, text] of Object.entries(args.files || {})) {
        filePath(path); if (typeof text !== 'string') throw new Error('files must contain UTF-8 text');
      }
      for (const path of args.exportFiles || []) filePath(path);
      // Clone through JSON before the Worker boundary: no host objects/functions.
      const encoded = JSON.stringify(args);
      if (bytes(encoded) > maxInputBytes) throw new Error('input exceeds byte limit');
      args = JSON.parse(encoded);
      const required = [`tool/${name}`];
      // Pyodide's Python->JS bridge is ambient browser authority, not QuickJS confinement.
      if (name === 'python') required.push('tool/python-js-bridge');
      if (Object.keys(args.files || {}).length) required.push('fs/read');
      if (args.exportFiles?.length) required.push('fs/write');
      const missing = required.filter(cap => !grants.has(cap));
      if (missing.length) return finish({exitCode: 126, error: `missing-capabilities: ${missing.join(', ')}`});
    } catch (err) { return finish({exitCode: 126, error: err.message}); }
    if (signal?.aborted) return finish({exitCode: 130, error: 'cancelled'});
    return new Promise(resolve => {
      let worker, timer, done = false;
      let stdout = '', stderr = '', total = 0;
      const end = data => {
        if (done) return;
        done = true; clearTimeout(timer); signal?.removeEventListener('abort', abort);
        worker?.terminate(); resolve(finish({stdout, stderr, ...data}));
      };
      const abort = () => end({exitCode: 130, error: 'cancelled'});
      signal?.addEventListener('abort', abort, {once: true});
      timer = setTimeout(() => end({exitCode: 124, timedOut: true, error: 'deadline exceeded'}), timeoutMs);
      try {
        worker = makeWorker(workerUrl);
        isolation = runtimeIsolation;
        worker.onerror = event => {event.preventDefault?.(); end({exitCode: 1, error: event.message || 'worker failed'});};
        worker.onmessageerror = () => end({exitCode: 1, error: 'worker message could not be decoded'});
        worker.onmessage = ({data}) => {
          try {
            if (data.kind === 'output') {
              const text = String(data.text);
              total += bytes(text);
              if (total > maxOutputBytes) return end({exitCode: 125, truncated: true, error: 'output exceeds byte limit'});
              if (data.stream === 'stderr') stderr += text; else stdout += text;
            } else if (data.kind === 'done') {
              if (data.outputOverflow) return end({exitCode: 125, truncated: true, error: 'output exceeds byte limit'});
              if (total + bytes(JSON.stringify(data)) > maxOutputBytes)
                return end({exitCode: 125, truncated: true, error: 'result exceeds byte limit'});
              const files = data.files || {};
              if (Object.keys(files).some(path => !args.exportFiles?.includes(path)))
                return end({exitCode: 1, error: 'unexpected exported file'});
              end({result: data.result ?? null, files, exitCode: data.error ? 1 : 0, error: data.error});
            }
          } catch (err) {end({exitCode: 1, error: err.message});}
        };
        worker.postMessage({name, args, maxMemoryBytes, maxOutputBytes});
      } catch (err) {end({exitCode: 1, error: err.message});}
    });
  }};
}
