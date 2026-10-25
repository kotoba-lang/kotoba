import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const allowedWorkspace=p=>{const absolute=path.resolve(p),temp=process.env.RUNNER_TEMP&&path.resolve(process.env.RUNNER_TEMP);return absolute.includes('/github/workspaces/')||(process.env.GITHUB_ACTIONS==='true'&&temp&&(absolute===temp||absolute.startsWith(temp+path.sep)));};
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const safe=relative=>{const p=path.resolve(root,relative);assert(p.startsWith(root+path.sep)&&fs.lstatSync(p).isFile()&&!fs.lstatSync(p).isSymbolicLink());assert(fs.realpathSync(p).startsWith(fs.realpathSync(root)+path.sep));return p;};
const json=p=>JSON.parse(fs.readFileSync(safe(p),'utf8'));
const hash=p=>createHash('sha256').update(fs.readFileSync(safe(p))).digest('hex');
const m=json('maintenance/storage-consolidation/2026-10-22/receipt.json');
const imports=json('maintenance/storage-source-imports.json');
assert.equal(m.schema,'kotoba.storage-source-consolidation.v1');assert.equal(m.owner,'kotoba-lang/kotobase-storage');
assert.equal(m.repositories.length,7);assert.equal(m['protected-original-pin-holds'],239);assert.equal(m['repository-deletions'],0);
function git(cwd,args){const p=spawnSync('git',['-C',cwd,...args],{encoding:'utf8',maxBuffer:32*1024*1024});assert.equal(p.status,0,p.stderr);return p.stdout.trim();}
const workspace=process.argv[2];if(workspace){assert(allowedWorkspace(workspace));fs.mkdirSync(workspace,{recursive:true});}
const seen=new Set();let refs=0,pulls=0,historyFiles=0;
for(const r of m.repositories){
  assert(!seen.has(r.repository));seen.add(r.repository);assert(r['history-restored-and-fsck']);
  const origin=imports.imports.find(o=>o.repository===r.repository);assert(origin&&origin.commit===r.commit&&origin.tree===r.tree&&origin.id===r.id);
  assert.equal(hash(r['history-bundle']),r['bundle-sha256']);assert.equal(hash(r['github-snapshot']),r['github-sha256']);
  const g=json(r['github-snapshot']),before=g['repository-before-archive'];assert.equal(before.nameWithOwner,r.repository);assert(!before.isPrivate&&!before.isArchived);assert.equal(before.defaultBranchRef.target.oid,r.commit);
  assert.equal(g['closed-pulls'].length,before.allPRs.totalCount);pulls+=g['closed-pulls'].length;
  if(r.archived){
    assert.equal(r['archive-status'],'archived-after-main-verification');assert(g['archive-readback']?.archived&&g['archive-readback']['source-and-refs-unchanged']);assert.deepEqual(g['repository-after-archive'],{...before,isArchived:true});
    const v=m['main-verification'];assert.match(v?.commit??'',/^[a-f0-9]{40}$/);assert.equal(v['JVM-packages'].packages,5);assert.equal(v['JVM-packages'].failures,0);assert.equal(v['public-CLI'].packages,7);assert(v['all-provider-source-origins-verified']);assert.equal(v['JVM-packages'].errors,0);assert.equal(v['source-origins'].length,7);assert.equal(new Set(v['source-origins'].map(r=>r.id)).size,7);assert.equal(v['S3-R2-binding'].scripts,2);assert.equal(v['S3-R2-binding'].failures,0);assert.deepEqual(v['S3-compiled'].builds,['engine-r2','prolly-engine-r2','advanced-r2']);assert.equal(v['S3-compiled'].failures,0);assert(v['source-preservation-rechecked']);
  }else assert.equal(r['archive-status'],'pending-main-verification');
  if(r['working-tree-change']){
    const w=r['working-tree-change'];assert(w['restore-apply-status-verified']);assert.equal(hash(w.patch),w.sha256);
    assert.equal(createHash('sha256').update(gunzipSync(fs.readFileSync(safe(w.patch)))).digest('hex'),w['uncompressed-sha256']);
    assert.match(w.base,/^[a-f0-9]{40}$/);assert(w.status.trim());
  }
  const bundle=safe(r['history-bundle']),heads=new Map(git(root,['bundle','list-heads',bundle]).split('\n').map(line=>{const [oid,ref]=line.split(' ');return [ref,oid];}));
  for(const ref of r['preserved-refs']){
    assert.equal(heads.get(ref.ref),ref.object);
    if(!ref['default-ancestor'])assert(imports['branch-reviews'].some(row=>row.repository===r.repository&&row.commit===ref['reviewed-nonancestor']&&row.decision==='superseded'));
  }
  if(workspace){
    const tmp=fs.mkdtempSync(path.join(path.resolve(workspace),'storage-restore-'));
    try{
      git(root,['clone','--mirror',bundle,tmp]);git(tmp,['fsck','--full']);assert.equal(git(tmp,['rev-parse',r.commit+'^{tree}']),r.tree);
      for(const ref of r['preserved-refs'])git(tmp,['merge-base','--is-ancestor',ref.commit,ref['default-ancestor']?r.commit:ref['reviewed-nonancestor']]);
      for(const file of origin.files){
        const p=spawnSync('git',['-C',tmp,'show',`${r.commit}:${file.source}`],{maxBuffer:8*1024*1024});assert.equal(p.status,0);assert.equal(createHash('sha256').update(p.stdout).digest('hex'),file.sha256);historyFiles++;
      }
      if(r['working-tree-change']){
        const w=r['working-tree-change'];assert(w['restore-apply-status-verified']);assert.equal(hash(w.patch),w.sha256);
        const patch=gunzipSync(fs.readFileSync(safe(w.patch)));assert.equal(createHash('sha256').update(patch).digest('hex'),w['uncompressed-sha256']);
        const checkout=fs.mkdtempSync(path.join(path.resolve(workspace),'storage-wip-restore-'));
        try{git(root,['clone',bundle,checkout]);git(checkout,['checkout','--detach',w.base]);
          for(const args of [['apply','--check','-'],['apply','-']]){const p=spawnSync('git',['-C',checkout,...args],{input:patch,encoding:'utf8'});assert.equal(p.status,0,p.stderr);}
          assert.equal(git(checkout,['status','--porcelain=v1','--untracked-files=all']),w.status);
        }finally{fs.rmSync(checkout,{recursive:true,force:true});}
      }
      for(const review of imports['branch-reviews'].filter(row=>row.repository===r.repository)){
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
assert.equal(seen.size,7);assert.equal(pulls,11);
console.log(`storage history: 7 repositories, ${refs} refs, ${pulls} historical PRs${workspace?`, all bundles restored/fsck and ${historyFiles} original file hashes checked`:''}`);
