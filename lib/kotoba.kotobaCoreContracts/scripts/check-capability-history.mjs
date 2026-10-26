import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const safe=relative=>{const p=path.resolve(root,relative);assert(p.startsWith(root+path.sep)&&fs.lstatSync(p).isFile()&&!fs.lstatSync(p).isSymbolicLink());assert(fs.realpathSync(p).startsWith(fs.realpathSync(root)+path.sep));return p;};
const json=p=>JSON.parse(fs.readFileSync(safe(p),'utf8'));
const hash=p=>createHash('sha256').update(fs.readFileSync(safe(p))).digest('hex');
const m=json('maintenance/capability-consolidation/2026-10-22/receipt.json');
const imports=json('maintenance/capability-source-imports.json');
assert.equal(m.schema,'kotoba.capability-source-consolidation.v1');assert.equal(m.owner,'kotoba-lang/kotoba-core-contracts');
assert.equal(m.repositories.length,61);assert.equal(m['protected-original-pin-holds'],239);assert.equal(m['repository-deletions'],0);
function git(cwd,args){const p=spawnSync('git',['-C',cwd,...args],{encoding:'utf8',maxBuffer:32*1024*1024});assert.equal(p.status,0,p.stderr);return p.stdout.trim();}
const workspace=process.argv[2];if(workspace){assert(path.resolve(workspace).includes('/github/workspaces/'));fs.mkdirSync(workspace,{recursive:true});}
const seen=new Set();let refs=0,pulls=0,historyFiles=0;
for(const r of m.repositories){
  assert(!seen.has(r.repository));seen.add(r.repository);assert(r['history-restored-and-fsck']);
  const origin=imports.imports.find(o=>o.repository===r.repository);assert(origin&&origin.commit===r.commit&&origin.tree===r.tree&&origin.id===r.id);
  assert.equal(hash(r['history-bundle']),r['bundle-sha256']);assert.equal(hash(r['github-snapshot']),r['github-sha256']);
  const g=json(r['github-snapshot']),before=g['repository-before-archive'];assert.equal(before.nameWithOwner,r.repository);assert(!before.isPrivate&&!before.isArchived);assert.equal(before.defaultBranchRef.target.oid,r.commit);
  assert.equal(g['closed-pulls'].length,before.allPRs.totalCount);pulls+=g['closed-pulls'].length;
  if(r.archived){
    assert.equal(r['archive-status'],'archived-after-main-verification');assert(g['archive-readback']?.archived&&g['archive-readback']['source-and-refs-unchanged']);assert.deepEqual(g['repository-after-archive'],{...before,isArchived:true});
    const v=m['main-verification'];assert.match(v?.commit??'',/^[a-f0-9]{40}$/);assert.equal(v['JVM-packages'].packages,61);assert.equal(v['JVM-packages'].failures,0);assert.equal(v['public-CLI'].namespaces,61);assert(v['all-definition-CIDs-recomputed']);
  }else assert.equal(r['archive-status'],'pending-main-verification');
  const bundle=safe(r['history-bundle']),heads=new Map(git(root,['bundle','list-heads',bundle]).split('\n').map(line=>{const [oid,ref]=line.split(' ');return [ref,oid];}));
  for(const ref of r['preserved-refs']){
    assert.equal(heads.get(ref.ref),ref.object);
    if(!ref['default-ancestor'])assert(imports['branch-reviews'].some(row=>row.repo===r.repository&&row.commit===ref['reviewed-nonancestor']&&row.decision==='superseded'));
  }
  if(workspace){
    const tmp=fs.mkdtempSync(path.join(path.resolve(workspace),'capability-restore-'));
    try{
      git(root,['clone','--mirror',bundle,tmp]);git(tmp,['fsck','--full']);assert.equal(git(tmp,['rev-parse',r.commit+'^{tree}']),r.tree);
      for(const ref of r['preserved-refs'])git(tmp,['merge-base','--is-ancestor',ref.commit,ref['default-ancestor']?r.commit:ref['reviewed-nonancestor']]);
      for(const file of origin.files){
        const p=spawnSync('git',['-C',tmp,'show',`${r.commit}:${file.source}`],{maxBuffer:8*1024*1024});assert.equal(p.status,0);assert.equal(createHash('sha256').update(p.stdout).digest('hex'),file.sha256);historyFiles++;
      }
      for(const review of imports['branch-reviews'].filter(row=>row.repo===r.repository)){
        if(review['merge-commit'])git(tmp,['merge-base','--is-ancestor',review['merge-commit'],r.commit]);
        for(const f of review['source-lineage']??[]){
          const a=spawnSync('git',['-C',tmp,'show',`${review.commit}:${f['original-source']}`]),b=spawnSync('git',['-C',tmp,'show',`${r.commit}:${f['default-source']}`]);assert.equal(a.status,0);assert.equal(b.status,0);
          assert.equal(createHash('sha256').update(a.stdout).digest('hex'),f['original-sha256']);assert.equal(createHash('sha256').update(b.stdout).digest('hex'),f['default-sha256']);
        }
      }
    }finally{fs.rmSync(tmp,{recursive:true,force:true});}
  }
  refs+=r['preserved-refs'].length;
}
assert.equal(seen.size,61);assert.equal(pulls,16);
console.log(`capability history: 61 repositories, ${refs} refs, ${pulls} historical PRs${workspace?`, all bundles restored/fsck and ${historyFiles} original file hashes checked`:''}`);
