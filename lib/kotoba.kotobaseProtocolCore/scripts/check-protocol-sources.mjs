import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {validateCatalog, sourcePaths} from './protocol-sources.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const safe = relative => {
  const target = path.resolve(root, relative);
  assert(target.startsWith(root + path.sep) && fs.lstatSync(target).isFile() && !fs.lstatSync(target).isSymbolicLink());
  assert(fs.realpathSync(target).startsWith(fs.realpathSync(root) + path.sep));
  return target;
};
const read = relative => JSON.parse(fs.readFileSync(safe(relative), 'utf8'));
const imports = read('maintenance/protocol-source-imports.json'), catalog = validateCatalog(read('surfaces/catalog.json'));
assert.equal(imports.schema, 'kotoba.protocol-source-imports.v1');
assert.equal(imports.owner, catalog.owner); assert.equal(imports.imports.length, 3); assert.equal(imports['protected-original-pin-holds'], 239);
const files = new Set(), changes = new Set(); let count = 0;
for (const origin of imports.imports) {
  assert.match(origin.commit, /^[a-f0-9]{40}$/); assert.match(origin.tree, /^[a-f0-9]{40}$/);
  const row = catalog.packages.find(r => r.id === origin.id);
  assert(row && row.path === origin.path && row['legacy-repository'] === origin.repository && row['needs-owner'] === origin['needs-owner']);
  sourcePaths(root, row); assert(origin.files.some(f => f.source === 'LICENSE'));
  for (const file of origin.files) {
    assert.equal(file.path, origin.path + '/' + file.source); assert(!files.has(file.path)); files.add(file.path);
    const change = imports['local-changes'][file.path];
    if (change) {
      assert.equal(change['imported-sha256'], file.sha256); assert(change.reason?.trim());
      assert(['deps.edn', 'nbb.edn'].includes(file.source) || file.source.startsWith('test/'), 'production protocol change needs separate review');
      changes.add(file.path);
    }
    assert.equal(hash(fs.readFileSync(safe(file.path))), change?.sha256 ?? file.sha256, 'unreviewed drift: ' + file.path);
    assert.equal(Boolean(fs.statSync(safe(file.path)).mode & 0o111), file.mode === '100755'); count++;
    if (['deps.edn', 'nbb.edn'].includes(file.source)) assert.equal(hash(fs.readFileSync(safe('maintenance/original-configs/' + origin.id + '/' + file.source))), file.sha256);
  }
}
assert.deepEqual([...changes].sort(), Object.keys(imports['local-changes']).sort());
for (const [file, value] of Object.entries(imports.additions)) {
  assert(file.endsWith('/nbb.edn') && value.reason?.trim());
  assert.equal(hash(fs.readFileSync(safe(file))), value.sha256); files.add(file);
}
function inventory(directory) {
  return fs.readdirSync(path.join(root, directory), {withFileTypes: true}).flatMap(e => {
    if (['node_modules', 'target', '.cpcache', '.nbb', '.shadow-cljs', '.cache'].includes(e.name)) return [];
    const relative = directory + '/' + e.name; assert(!e.isSymbolicLink());
    return e.isDirectory() ? inventory(relative) : [relative];
  });
}
assert.deepEqual(inventory('surfaces').sort(), [...files, 'surfaces/catalog.json'].sort()); assert.equal(count, 37);
const git = args => {const p = spawnSync('git', ['-C', root, ...args], {maxBuffer: 16 * 1024 * 1024}); assert.equal(p.status, 0, String(p.stderr)); return p.stdout;};
const base = imports['owner-base']; assert.match(base, /^[a-f0-9]{40}$/);
const original = git(['ls-tree', '-r', '--name-only', base, '--', 'src']).toString().trim().split('\n');
assert.deepEqual(inventory('src').sort(), original.sort());
for (const file of [...original, 'deps.edn', 'nbb.edn']) assert.equal(hash(fs.readFileSync(safe(file))), hash(git(['show', base + ':' + file])), 'root production/default graph changed: ' + file);
const originalTests = git(['ls-tree', '-r', '--name-only', base, '--', 'test']).toString().trim().split('\n');
assert.deepEqual(inventory('test').sort(), originalTests.sort());
const adjustedTests = [];
for (const file of originalTests) {
  const before = hash(git(['show', base + ':' + file])), current = hash(fs.readFileSync(safe(file)));
  if (current === before) continue;
  const change = imports['owner-test-host-adjustments'][file];
  assert(change && change.reason?.trim(), 'unreviewed root test change: ' + file);
  assert.equal(before, change['original-sha256']); assert.equal(current, change.sha256); adjustedTests.push(file);
}
assert.deepEqual(adjustedTests.sort(), Object.keys(imports['owner-test-host-adjustments']).sort());
console.log('protocol source: 3 opt-in projects / 37 original files; production bytes and root default graph unchanged; test/config adjustments bound');
