import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const allowed = p => {const a = path.resolve(p), t = process.env.RUNNER_TEMP && path.resolve(process.env.RUNNER_TEMP); return a.includes('/github/workspaces/') || (process.env.GITHUB_ACTIONS === 'true' && t && (a === t || a.startsWith(t + path.sep)));};
const safe = relative => {const p = path.resolve(root, relative); assert(p.startsWith(root + path.sep) && fs.lstatSync(p).isFile() && !fs.lstatSync(p).isSymbolicLink()); assert(fs.realpathSync(p).startsWith(fs.realpathSync(root) + path.sep)); return p;};
const read = relative => JSON.parse(fs.readFileSync(safe(relative), 'utf8'));
const hash = data => createHash('sha256').update(data).digest('hex');
const git = (cwd, args) => {const p = spawnSync('git', ['-C', cwd, ...args], {encoding: 'utf8', maxBuffer: 32 * 1024 * 1024}); assert.equal(p.status, 0, p.stderr); return p.stdout.trim();};
const blob = (cwd, sha, file) => {const p = spawnSync('git', ['-C', cwd, 'show', sha + ':' + file], {maxBuffer: 16 * 1024 * 1024}); assert.equal(p.status, 0, String(p.stderr)); return p.stdout;};
const receipt = read('maintenance/protocol-consolidation/2026-10-22/receipt.json'), imports = read('maintenance/protocol-source-imports.json');
assert.equal(receipt.schema, 'kotoba.protocol-source-consolidation.v1'); assert.equal(receipt.owner, 'kotoba-lang/kotobase-protocol-core'); assert.equal(receipt.repositories.length, 3); assert.equal(receipt['protected-original-pin-holds'], 239); assert.equal(receipt['repository-deletions'], 0);
const workspace = process.argv[2]; if (workspace) {assert(allowed(workspace)); fs.mkdirSync(workspace, {recursive: true});}
const seen = new Set(); let refs = 0, pulls = 0, files = 0;
for (const row of receipt.repositories) {
  assert(!seen.has(row.repository)); seen.add(row.repository); assert(row['history-restored-and-fsck']);
  const origin = imports.imports.find(r => r.repository === row.repository);
  assert(origin && origin.commit === row.commit && origin.tree === row.tree && origin.id === row.id);
  assert.equal(hash(fs.readFileSync(safe(row['history-bundle']))), row['bundle-sha256']);
  assert.equal(hash(fs.readFileSync(safe(row['github-snapshot']))), row['github-sha256']);
  const snapshot = read(row['github-snapshot']), before = snapshot['repository-before-archive'];
  assert.equal(before.nameWithOwner, row.repository); assert(!before.isPrivate && !before.isArchived); assert.equal(before.defaultBranchRef.target.oid, row.commit);
  assert.equal(snapshot['historical-pulls'].length, before.allPRs.totalCount); pulls += snapshot['historical-pulls'].length;
  if (row.archived) {
    assert.equal(row['archive-status'], 'archived-after-main-verification');
    assert(snapshot['archive-readback']?.archived && snapshot['archive-readback']['source-and-refs-unchanged']);
    assert.deepEqual(snapshot['repository-after-archive'], {...before, isArchived: true});
    const v = receipt['main-verification']; assert.match(v?.commit ?? '', /^[a-f0-9]{40}$/);
    assert.equal(v.JVM.projects, 3); assert.equal(v.JVM.failures, 0); assert.equal(v.JVM.errors, 0);
    assert.equal(v['compiled-CLJS'].projects, 4); assert.equal(v['compiled-CLJS'].failures, 0);
    assert.equal(v['source-origins'].length, 3); assert.equal(v['public-source-CLI'].exactLookups, 9);
    assert(v['source-preservation-rechecked'] && v['root-default-graph-unchanged']);
  } else assert.equal(row['archive-status'], 'pending-main-verification');
  const heads = new Map(git(root, ['bundle', 'list-heads', safe(row['history-bundle'])]).split('\n').map(line => {const [oid, ref] = line.split(' '); return [ref, oid];}));
  assert.equal(heads.get('HEAD'), row['original-local-HEAD']); assert.equal(heads.size, row['preserved-refs'].length + 1);
  for (const ref of row['preserved-refs']) {
    assert.equal(heads.get(ref.ref), ref.object);
    if (!ref['default-ancestor']) {
      assert.equal(ref.commit, ref['reviewed-nonancestor']);
      const review = imports['branch-reviews'].find(r => r.repository === row.repository && r.commit === ref.commit);
      assert(review && review.decision === ref.decision && review.review?.trim());
      assert(['integrated-with-reviewed-successor', 'archived-wip-exactly-in-default', 'merged-squash-tree-identical'].includes(review.decision));
    }
  }
  for (const review of imports['branch-reviews'].filter(r => r.repository === row.repository)) {
    assert(review['production-source-lineage'].length > 0);
    assert.equal(hash(fs.readFileSync(safe(review['review-diff']))), review['review-diff-sha256']);
  }
  if (workspace) {
    const tmp = fs.mkdtempSync(path.join(path.resolve(workspace), 'protocol-restore-'));
    try {
      git(root, ['clone', '--mirror', safe(row['history-bundle']), tmp]); git(tmp, ['fsck', '--full']);
      assert(!fs.existsSync(path.join(tmp, 'objects/info/alternates'))); assert.equal(git(tmp, ['rev-parse', row.commit + '^{tree}']), row.tree);
      for (const ref of row['preserved-refs']) assert.equal(git(tmp, ['rev-parse', ref.ref]), ref.object);
      for (const file of origin.files) {assert.equal(hash(blob(tmp, row.commit, file.source)), file.sha256); files++;}
      for (const pull of snapshot['historical-pulls']) {
        assert.equal(git(tmp, ['rev-parse', 'refs/preservation/protocol-monorepo-20261022/pull-' + pull.number]), pull.headRefOid);
        if (pull.state === 'MERGED') git(tmp, ['merge-base', '--is-ancestor', pull.mergeCommit.oid, row.commit]);
      }
      for (const review of imports['branch-reviews'].filter(r => r.repository === row.repository)) {
        for (const line of review['production-source-lineage']) {
          assert.equal(hash(blob(tmp, review.commit, line.source)), line['source-sha256']);
          assert.equal(hash(blob(tmp, row.commit, line.successor)), line['successor-sha256']);
          if (review.decision !== 'integrated-with-reviewed-successor') assert.equal(line['source-sha256'], line['successor-sha256']);
        }
        if (review.decision === 'merged-squash-tree-identical') assert.equal(git(tmp, ['rev-parse', review.commit + '^{tree}']), row.tree);
        if (review.decision === 'archived-wip-exactly-in-default') assert.equal(git(tmp, ['ls-tree', '-r', '--name-only', review.commit + '^3']), '');
      }
    } finally {fs.rmSync(tmp, {recursive: true, force: true});}
  }
  refs += row['preserved-refs'].length;
}
for (const review of imports['dependency-compatibility-overrides']) assert.equal(hash(fs.readFileSync(safe(review['review-diff']))), review['review-diff-sha256']);
assert.equal(refs, 30); assert.equal(pulls, 2); if (workspace) assert.equal(files, 37);
console.log(`protocol history: 3 complete histories / ${refs} refs / ${pulls} historical PRs${workspace ? ` / ${files} original hashes restored/fsck` : ''}; archived WIP and squash head preserved`);
