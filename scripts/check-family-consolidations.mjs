import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const receipt = 'maintenance/family-consolidations/2026-10-22/receipt.json';
const safe = relative => {
  const file = path.resolve(root, relative);
  assert(file.startsWith(root + path.sep) && fs.lstatSync(file).isFile() && !fs.lstatSync(file).isSymbolicLink());
  assert(fs.realpathSync(file).startsWith(fs.realpathSync(root) + path.sep));
  return file;
};
const json = relative => JSON.parse(fs.readFileSync(safe(relative), 'utf8'));
const digest = relative => crypto.createHash('sha256').update(fs.readFileSync(safe(relative))).digest('hex');
const m = json(receipt);
assert.equal(m.schema, 'kotoba.family-consolidation-receipt.v1');
assert.equal(m.families.length, 5);
assert.equal(m['child-repositories-archived'], 61);
assert.equal(m['repository-deletions'], 0);
const held = new Set(json('maintenance/retired-libraries/2026-10-22/manifest.json')['held-dependency-pin-repositories']);
assert.equal(held.size, 239);
assert.deepEqual(m.families.map(f => f.family).sort(), ['crypto','device','http','netcap','wit']);
const restoredBase = process.argv[2];
if (restoredBase) {assert(path.resolve(restoredBase).includes('/github/workspaces/')); fs.mkdirSync(restoredBase, {recursive:true});}
function git(cwd, args) {
  const r = spawnSync('git', ['-C', cwd, ...args], {encoding:'utf8', maxBuffer:32*1024*1024});
  assert.equal(r.status, 0, r.stderr);
  return r.stdout.trim();
}
const seen = new Set(); let refs = 0;
for (const f of m.families) {
  assert.equal(f.owner, 'kotoba-lang/' + f.family);
  assert.match(f['owner-main'], /^[a-f0-9]{40}$/);
  assert.equal(digest(f['import-manifest']), f['import-manifest-sha256']);
  const inventory = json(f['import-manifest']);
  assert.equal(inventory.owner, f.owner);
  assert.equal(inventory['external-dependencies-unchanged'], true);
  assert.equal(f.children.length, inventory.imports.length);
  assert(f['public-CLI']['public-CLI']);
  for (const host of ['portable','JVM']) assert(f[host].tests > 0 && f[host].assertions > 0 && f[host].failures === 0 && f[host].errors === 0);
  for (const c of f.children) {
    assert(c.repo.startsWith(f.owner + '-') && !seen.has(c.repo) && !held.has(c.repo)); seen.add(c.repo);
    const origin = inventory.imports.find(r => r.repository === c.repo);
    assert(origin && origin.commit === c.commit && origin.tree === c.tree);
    assert(origin.files.some(r => r.source === 'LICENSE'));
    assert(c.archived && c['source-and-refs-unchanged-after-archive'] && c['history-restored-and-fsck']);
    assert.equal(digest(c['history-bundle']), c['bundle-sha256']);
    assert.equal(digest(c['github-snapshot']), c['github-sha256']);
    const g = json(c['github-snapshot']);
    assert.equal(g['repository-before-archive'].nameWithOwner, c.repo);
    assert.equal(g['repository-before-archive'].isPrivate, false);
    assert(g['archive-readback'].archived && g['archive-readback']['source-and-refs-unchanged']);
    const bundle = safe(c['history-bundle']);
    const heads = new Map(git(root, ['bundle','list-heads',bundle]).split('\n').map(s => {const [oid,ref]=s.split(' '); return [ref,oid];}));
    for (const ref of c['preserved-refs']) assert.equal(heads.get(ref.ref), ref.object);
    const tmp = restoredBase ? fs.mkdtempSync(path.join(path.resolve(restoredBase), f.family + '-')) : null;
    try {
      if (tmp) {
        git(root, ['clone','--mirror',bundle,tmp]); git(tmp,['fsck','--full']);
        assert.equal(git(tmp,['rev-parse',c.commit+'^{tree}']),c.tree);
        for (const ref of c['preserved-refs']) git(tmp,['merge-base','--is-ancestor',ref.commit,c.commit]);
      }
    } finally {if(tmp) fs.rmSync(tmp,{recursive:true,force:true});}
    refs += c['preserved-refs'].length;
  }
}
assert.equal(seen.size, 61);
console.log(`family consolidation: 5 owners, ${seen.size} archived children, ${refs} preserved refs; 239 original pin holds protected${restoredBase ? '; all histories restored/fsck verified' : ''}`);
