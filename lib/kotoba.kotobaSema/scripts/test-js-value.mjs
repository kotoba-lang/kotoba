// Node/nbb bootstrap qualification. Dependency authoring occurs separately.
import { existsSync, mkdtempSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { delimiter, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const [engineArgument, classpathFile] = process.argv.slice(2);
if (!engineArgument || !classpathFile) throw Error('usage: test-js-value.mjs ENGINE_CLI CLASSPATH_FILE');
const engine = realpathSync(engineArgument);
const paths = [join(root, 'src'), join(root, 'test'), join(root, 'resources'),
  ...readFileSync(classpathFile, 'utf8').trim().split(delimiter)
    .map(path => resolve(root, path)).filter(path => existsSync(path) && statSync(path).isDirectory())];
const directory = mkdtempSync(join(tmpdir(), 'sema-js-value-'));
try {
  const config = join(directory, 'nbb.edn');
  // No :deps: tests cannot invoke nbb's JVM dependency resolver.
  writeFileSync(config, `{:paths [${[...new Set(paths)].map(path => JSON.stringify(path)).join(' ')}]}\n`);
  const expression = `(require '[cljs.test :as t] '[kotoba.compiler.js-value-type-test]
    '[kotoba.compiler.empty-library-test] '[kotoba.compiler.js-closure-test]
    '[kotoba.compiler.js-capture-test] '[kotoba.compiler.higher-order-closure-test] '[kotoba.compiler.guest-grammar-contract-test])
    (defmethod t/report [::t/default :end-run-tests] [m]
      (when (or (not= 41 (:test m)) (not= 221 (:pass m))
                (pos? (+ (:fail m) (:error m)))) (js/process.exit 1)))
    (t/run-tests 'kotoba.compiler.js-value-type-test 'kotoba.compiler.empty-library-test 'kotoba.compiler.js-closure-test 'kotoba.compiler.js-capture-test 'kotoba.compiler.higher-order-closure-test 'kotoba.compiler.guest-grammar-contract-test)`;
  const result = spawnSync(process.execPath, [engine, '--config', config, '-e', expression],
    { cwd: root, stdio: 'inherit', timeout: 120000 });
  if (result.error) throw result.error;
  if (result.status !== 0) throw Error(`bootstrap source qualification failed: ${result.status ?? result.signal}`);
} finally {
  rmSync(directory, { recursive: true, force: true });
}
