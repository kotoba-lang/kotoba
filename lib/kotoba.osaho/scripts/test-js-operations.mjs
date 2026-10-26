// Node/nbb bootstrap tests; dependency classpath is authored separately.
import { existsSync, mkdtempSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { delimiter, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const [engineArgument, classpathFile] = process.argv.slice(2);
if (!engineArgument || !classpathFile) throw Error('usage: test-js-operations.mjs ENGINE_CLI CLASSPATH_FILE');
const engine = realpathSync(engineArgument);
const paths = [join(root, 'src'), join(root, 'test'), join(root, 'resources'),
  ...readFileSync(classpathFile, 'utf8').trim().split(delimiter)
    .map(path => resolve(root, path)).filter(path => existsSync(path) && statSync(path).isDirectory())];
const directory = mkdtempSync(join(tmpdir(), 'osaho-js-operations-'));
const marker = join(directory, 'jvm-invoked');
try {
  const config = join(directory, 'offline.edn');
  writeFileSync(config, `{:paths [${[...new Set(paths)].map(path => JSON.stringify(path)).join(' ')}]}\n`);
  for (const name of ['java', 'javac', 'clojure', 'clj']) {
    writeFileSync(join(directory, name), '#!/bin/sh\n: > "$KOTOBA_JVM_MARKER"\nexit 97\n', {mode: 0o755});
  }
  const result = spawnSync(process.execPath, [engine, '--config', config, 'run-tests.cljk'],
    {cwd: root, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024, timeout: 300000,
     env: {...process.env, KOTOBA_JVM_MARKER: marker, PATH: `${directory}:${process.env.PATH || ''}`}});
  process.stdout.write(result.stdout || ''); process.stderr.write(result.stderr || '');
  if (existsSync(marker)) throw Error('JVM executable invoked during bootstrap tests');
  if (result.error) throw result.error;
  if (result.status !== 0 || !/Ran 293 tests containing 2411 assertions\.\s+0 failures, 0 errors\./.test(result.stdout)) {
    throw Error(`bootstrap suite did not complete its declared checks: ${result.status ?? result.signal}`);
  }
} finally { rmSync(directory, {recursive: true, force: true}); }
