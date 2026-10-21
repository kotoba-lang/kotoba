import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const option = key => args[args.indexOf(key) + 1];
const relative = args.includes('--manifest') ? option('--manifest') : 'maintenance/retired-libraries/2026-10-22/manifest.json';
const inside = (base, p) => p.startsWith(base + path.sep);
const file = rel => {
  const p = path.resolve(root, rel);
  assert(inside(root, p) && fs.lstatSync(p).isFile() && !fs.lstatSync(p).isSymbolicLink(), rel);
  return p;
};
const json = rel => JSON.parse(fs.readFileSync(file(rel), 'utf8'));
const digest = rel => crypto.createHash('sha256').update(fs.readFileSync(file(rel))).digest('hex');
function git(cwd, argv, input) {
  const r = spawnSync('git', ['-C', cwd, ...argv], {encoding: 'utf8', input, maxBuffer: 32 * 1024 * 1024});
  assert.equal(r.status, 0, r.stderr);
  return r.stdout.trim();
}
const m = json(relative);
assert.equal(m.schema, 'kotoba.library-retirement-preservation.v1');
assert.equal(m.repositories.length, 125);
assert.equal(m['held-dependency-pin-repositories'].length, 239);
const names = new Set(m.repositories.map(r => r.repo));
const held = new Set(m['held-dependency-pin-repositories']);
assert.equal(names.size, 125);
assert.equal(held.size, 239);
assert([...names].every(n => /^kotoba-lang\/[a-z0-9-]+$/.test(n) && !held.has(n)));
const migrations = json('lib/repository-migrations.json').repositories;
const reviews = json('lib/branch-reviews.json').reviews;
const restoreBase = args.includes('--restore-workspace') ? path.resolve(option('--restore-workspace')) : null;
if (restoreBase) { assert(restoreBase.includes('/github/workspaces/')); fs.mkdirSync(restoreBase, {recursive: true}); }
let total = 0, refs = 0;
for (const r of m.repositories) {
  const migration = migrations.find(x => x.repo === r.repo);
  assert(migration && migration.holds.length === 0);
  assert.equal(r['default-commit'], migration['reviewed-default-commit']);
  assert.equal(r.destination, migration.destination);
  assert.equal(r.decision, 'eligible');
  assert(r['restored-and-fsck'] && r['local-state'].clean && r['local-state'].stashes === 0 && r['local-state'].worktrees === 1);
  assert.equal(digest(r['history-bundle']), r['bundle-sha256'], 'bundle digest mismatch');
  assert.equal(fs.statSync(file(r['history-bundle'])).size, r['bundle-bytes']);
  assert.equal(digest(r['github-snapshot']), r['github-sha256'], 'GitHub snapshot digest mismatch');
  const g = json(r['github-snapshot']);
  assert.equal(g.repository.nameWithOwner, r.repo);
  assert.equal(g.repository.isArchived, true);
  assert.equal(g.repository.isPrivate, false);
  assert.equal(g.repository.openIssues.totalCount + g.repository.openPRs.totalCount + g.repository.releases.totalCount, 0);
  assert.equal(g.repository.defaultBranchRef.target.oid, r['default-commit']);
  const bundle = file(r['history-bundle']);
  const bundled = new Map(git(root, ['bundle', 'list-heads', bundle]).split('\n').map(s => {const [sha, ref] = s.split(' '); return [ref, sha];}));
  for (const kind of ['heads', 'tags']) {
    assert.deepEqual(r['remote-refs'][kind], g.repository[kind].nodes);
    assert.equal(g.repository[kind].totalCount, r['remote-refs'][kind].length);
    for (const ref of r['remote-refs'][kind]) assert.equal(bundled.get(`refs/archive/jun269-20261022/${kind}/${ref.name}`), ref.target.oid, 'remote ref not preserved');
  }
  for (const p of g.pulls) assert.equal(bundled.get(`refs/archive/jun269-20261022/pulls/${p.pull.number}`), p.pull.head.sha, 'PR tip not preserved');
  const restored = restoreBase ? fs.mkdtempSync(path.join(restoreBase, r.repo.split('/')[1] + '-')) : null;
  try {
    if (restored) {
      git(root, ['clone', '--mirror', bundle, restored]);
      git(restored, ['fsck', '--full']);
      assert.equal(git(restored, ['rev-parse', r['origin-commit'] + '^{tree}']), r['origin-tree']);
      for (const ref of r['reviewed-refs']) {
        if (ref.decision === 'default-history') git(restored, ['merge-base', '--is-ancestor', ref.commit, r['default-commit']]);
        else if (ref.decision === 'landed-identical-postimages') {
          assert(ref.proof.length > 0);
          for (const p of ref.proof) {
            git(restored, ['merge-base', '--is-ancestor', p.landed, r['default-commit']]);
            const paths = git(restored, ['diff-tree', '--root', '--no-commit-id', '--name-only', '-r', p.original]).split('\n').filter(Boolean);
            assert.deepEqual(paths.sort(), [...p['identical-postimage-paths']].sort());
            for (const f of paths) assert.equal(git(restored, ['ls-tree', p.original, '--', f]), git(restored, ['ls-tree', p.landed, '--', f]));
            for (const c of [p.original, p.landed]) {
              const diff = git(restored, ['show', '--pretty=medium', c]);
              assert.equal(git(restored, ['patch-id', '--stable'], diff).split(' ')[0], p['patch-id']);
            }
          }
        } else assert(reviews.some(x => x.repo === r.repo && x.commit === ref.commit && x.decision === ref.decision), 'missing integration review');
      }
    }
  } finally { if (restored) fs.rmSync(restored, {recursive: true, force: true}); }
  total += r['bundle-bytes']; refs += r['reviewed-refs'].length;
}
console.log(`retirement preservation: ${names.size} repositories, ${refs} reviewed refs, ${total} bundle bytes; ${held.size} pin holds retained${restoreBase ? '; all mirrors restored and fsck verified' : ''}`);
