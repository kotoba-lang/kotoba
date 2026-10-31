import { readFileSync, readdirSync, mkdirSync, copyFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';

// clj-kondo ignores canonical .cljk extensions; lint a disposable mirror.
const manifest = readFileSync('cljk-origin.edn', 'utf8');
const origins = new Map([...manifest.matchAll(/"([^"]+\.cljk)"\s+"(\.clj[cs]?)"/g)]
  .map(([, path, extension]) => [path, extension]));
rmSync('.ci-lint', { recursive: true, force: true });
let count = 0;
function mirror(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) mirror(path);
    else if (path.endsWith('.cljk')) {
      const extension = origins.get(path);
      if (!extension) throw new Error(`Missing CLJK origin: ${path}`);
      const target = join('.ci-lint', path.replace(/\.cljk$/, extension));
      mkdirSync(join('.ci-lint', dir), { recursive: true });
      copyFileSync(path, target);
      count++;
    }
  }
}
mirror('src');
mirror('test');
if (!count) throw new Error('No canonical source files found for lint');
console.log(`Lint mirror: ${count} canonical files`);
