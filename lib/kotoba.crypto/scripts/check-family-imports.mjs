// SPDX-License-Identifier: Apache-2.0
// Source co-location provenance gate; not package admission or runtime qualification.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root = process.argv[2] ? path.resolve(process.argv[2]) : path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'family-imports.json'), 'utf8'));
assert.equal(manifest.schema, 'kotoba.family-source-consolidation.v1');
assert.match(manifest.owner, /^kotoba-lang\/[a-z][a-z0-9-]*$/);
const family = manifest.owner.split('/')[1];
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
function file(relative) {
  assert.equal(typeof relative, 'string');
  const result = path.resolve(root, relative);
  assert(result.startsWith(root + path.sep), 'path escapes owner repository');
  assert(fs.lstatSync(result).isFile() && !fs.lstatSync(result).isSymbolicLink(), 'expected a regular file');
  assert(fs.realpathSync(result).startsWith(fs.realpathSync(root) + path.sep), 'symlinked parent escapes owner repository');
  return result;
}
function check(row) {
  assert.match(row.sha256, /^[0-9a-f]{64}$/);
  const target = file(row.path);
  const change = manifest['local-changes']?.[row.path];
  if (change) {
    assert.equal(change['original-sha256'], row.sha256);
    assert(change.reason?.trim());
    assert.match(change.sha256, /^[0-9a-f]{64}$/);
  }
  assert.equal(sha(fs.readFileSync(target)), change?.sha256 ?? row.sha256, 'unreviewed source/configuration drift');
  if (row.mode) {
    assert(['100644', '100755'].includes(row.mode));
    assert.equal(Boolean(fs.statSync(target).mode & 0o111), row.mode === '100755', 'executable mode drift');
  }
}
assert.equal(sha(fs.readFileSync(fileURLToPath(import.meta.url))), manifest['verifier-sha256'], 'unreviewed verifier drift');
assert.match(manifest['reviewed-owner-commit'], /^[0-9a-f]{40}$/);
assert.match(manifest['reviewed-owner-tree'], /^[0-9a-f]{40}$/);
const repositories = new Set(), paths = new Set();
for (const row of manifest['base-source-files']) {
  assert(row.path.startsWith('src/') || row.path.startsWith('test/'));
  assert(!paths.has(row.path)); paths.add(row.path); check(row);
}
assert(manifest.imports.length > 0);
let importedFiles = 0;
for (const origin of manifest.imports) {
  assert(origin.repository.startsWith(manifest.owner + '-'), 'source belongs to a different family');
  assert(!repositories.has(origin.repository)); repositories.add(origin.repository);
  assert.match(origin.commit, /^[0-9a-f]{40}$/);
  assert.match(origin.tree, /^[0-9a-f]{40}$/);
  assert(origin.files.some(row => row.source === 'LICENSE'), 'missing original license');
  assert(origin.files.some(row => row.source.startsWith('src/')), 'missing implementation');
  for (const row of origin.files) {
    assert(!paths.has(row.path), 'colliding source owners'); paths.add(row.path); check(row); importedFiles++;
  }
}
for (const [name, row] of Object.entries(manifest['configuration-before'])) {
  assert(['deps.edn', 'nbb.edn'].includes(name)); check(row);
}
for (const [name, digest] of Object.entries(manifest['configuration-after'])) check({path:name, sha256:digest});
assert.equal(manifest['external-dependencies-unchanged'], true, 'missing authoritative EDN comparison');
for (const coordinate of manifest['removed-internal-git-dependencies']) {
  assert(coordinate.startsWith('io.github.' + manifest.owner + '-'));
  assert(repositories.has(coordinate.slice('io.github.'.length)));
}
for (const key of Object.keys(manifest['local-changes'] ?? {})) assert(paths.has(key), 'unknown local change');
const visit = relative => {
  if (!fs.existsSync(path.join(root, relative))) return;
  for (const entry of fs.readdirSync(path.join(root, relative), {withFileTypes:true})) {
    const next = relative + '/' + entry.name;
    if (entry.isDirectory()) visit(next);
    else assert(paths.has(next), 'source has no owner/provenance: ' + next);
  }
};
visit('src'); visit('test');
console.log(`${manifest.owner}: ${repositories.size} same-family repositories, ${importedFiles} imported files; source provenance and reviewed external dependency configuration verified`);
