import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const safe=relative=>{
  const file=path.resolve(root,relative);
  assert(file.startsWith(root+path.sep) && fs.lstatSync(file).isFile() && !fs.lstatSync(file).isSymbolicLink());
  assert(fs.realpathSync(file).startsWith(fs.realpathSync(root)+path.sep));
  return file;
};
const json=file=>JSON.parse(fs.readFileSync(safe(file),'utf8'));
const sha=file=>createHash('sha256').update(fs.readFileSync(safe(file))).digest('hex');
const m=json('maintenance/tooling-consolidation/2026-10-22/receipt.json');
assert.equal(m.schema,'kotoba.tooling-consolidation.v1');
assert.equal(m.repositories.length,43);
assert.equal(m['licensed-source-origins'],31);
assert.equal(m['licensed-owner-derived-compatibility-modules'],12);
assert.equal(m['repository-deletions'],0);
const held=new Set(json('maintenance/retired-libraries/2026-10-22/manifest.json')['held-dependency-pin-repositories']);
assert.equal(held.size,239);
const ids=['kotoba.lsp','kotoba.lsp.rpc','kotoba.lint','kotoba.lint.kotoba'];
const imports=ids.flatMap(id=>json(`lib/${id}/imports.json`).imports.map(row=>({...row,id})));
const derived=json('lib/kotoba.lsp/derivations.json').derivations;
assert.equal(imports.length,31);assert.equal(derived.length,12);
const expected=new Set([...imports.map(r=>'kotoba-lang/'+r.repo),...derived.map(r=>r['reviewed-compatibility'].repository)]);
assert.equal(expected.size,43);
const names=new Set();let refs=0;
const base=process.argv[2];
if(base){assert(path.resolve(base).includes('/github/workspaces/'));fs.mkdirSync(base,{recursive:true});}
function git(cwd,args){const r=spawnSync('git',['-C',cwd,...args],{encoding:'utf8',maxBuffer:32*1024*1024});assert.equal(r.status,0,r.stderr);return r.stdout.trim();}
for(const r of m.repositories){
  assert(expected.has(r.repo) && !names.has(r.repo) && !held.has(r.repo));names.add(r.repo);
  assert.match(r.commit,/^[0-9a-f]{40}$/);assert.match(r.tree,/^[0-9a-f]{40}$/);
  assert(r['restored-and-fsck']);
  assert.equal(sha(r['history-bundle']),r['bundle-sha256']);
  assert.equal(sha(r['github-snapshot']),r['github-sha256']);
  const g=json(r['github-snapshot']);const before=g['repository-before-archive'];
  assert.equal(before.nameWithOwner,r.repo);assert.equal(before.isPrivate,false);
  assert.equal(before.defaultBranchRef.target.oid,r.commit);
  assert.equal(before.openPRs.totalCount,0);assert.equal(before.openIssues.totalCount,0);
  assert.equal(before.releases.totalCount,0);
  if(before.allPRs.totalCount)assert.equal(g.pulls.length,before.allPRs.totalCount);
  if(r.archived){
    assert.equal(r['archive-status'],'archived-after-main-verification');
    assert(g['archive-readback']?.archived && g['archive-readback']['source-and-refs-unchanged']);
    assert.deepEqual(g['repository-after-archive'],{...before,isArchived:true},'archived repository source or refs drifted');
    const v=m['main-verification'];assert.match(v?.commit??'',/^[0-9a-f]{40}$/);
    for(const host of ['portable','JVM'])assert(v[host].tests>0 && v[host].assertions>0 && v[host].failures===0 && v[host].errors===0);
    assert.equal(v['public-CLI'].namespaces,48);assert(v['public-CLI']['canonical-and-aliases']);
  }else assert.equal(r['archive-status'],'pending-main-verification');
  const origin=imports.find(i=>'kotoba-lang/'+i.repo===r.repo);
  const derivation=derived.find(d=>d['reviewed-compatibility'].repository===r.repo);
  assert(Boolean(origin)!==Boolean(derivation));
  if(origin){assert.equal(origin.commit,r.commit);assert.equal(origin.tree,r.tree);assert(origin.files.some(f=>f.source==='LICENSE'));}
  if(derivation){assert.equal(derivation['reviewed-compatibility'].commit,r.commit);assert.equal(derivation['reviewed-compatibility']['source-imported'],false);}
  const bundle=safe(r['history-bundle']);
  const heads=new Map(git(root,['bundle','list-heads',bundle]).split('\n').map(s=>{const [oid,ref]=s.split(' ');return [ref,oid];}));
  for(const ref of r['preserved-refs'])assert.equal(heads.get(ref.ref),ref.object);
  if(base){
    const tmp=fs.mkdtempSync(path.join(path.resolve(base),'tooling-restore-'));
    try{
      git(root,['clone','--mirror',bundle,tmp]);git(tmp,['fsck','--full']);
      assert.equal(git(tmp,['rev-parse',r.commit+'^{tree}']),r.tree);
      for(const ref of r['preserved-refs'])git(tmp,['merge-base','--is-ancestor',ref.commit,r.commit]);
      if(origin)for(const file of origin.files){
        const b=spawnSync('git',['-C',tmp,'show',`${r.commit}:${file.source}`],{maxBuffer:8*1024*1024});assert.equal(b.status,0);
        assert.equal(createHash('sha256').update(b.stdout).digest('hex'),file.sha256,'origin bytes differ from preserved immutable commit');
      }
      if(derivation){
        const c=derivation['reviewed-compatibility'];const b=spawnSync('git',['-C',tmp,'show',`${r.commit}:${c.source}`]);assert.equal(b.status,0);
        assert.equal(createHash('sha256').update(b.stdout).digest('hex'),c['source-sha256']);
        assert.equal(spawnSync('git',['-C',tmp,'cat-file','-e',`${r.commit}:LICENSE`]).status,128,'compatibility-only child unexpectedly labeled license-less');
      }
    }finally{fs.rmSync(tmp,{recursive:true,force:true});}
  }
  refs+=r['preserved-refs'].length;
}
assert.equal(names.size,43);
console.log(`tooling consolidation: 31 licensed origins, 12 owner-derived compatibility modules, 43 histories, ${refs} refs, 239 protected holds${base?'; all bundles restored/fsck and original source hashes verified':''}`);
