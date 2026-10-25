import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const allowed=p=>{const a=path.resolve(p),t=process.env.RUNNER_TEMP&&path.resolve(process.env.RUNNER_TEMP);return a.includes('/github/workspaces/')||(process.env.GITHUB_ACTIONS==='true'&&t&&(a===t||a.startsWith(t+path.sep)));};
const safe=relative=>{const p=path.resolve(root,relative);assert(p.startsWith(root+path.sep)&&fs.lstatSync(p).isFile()&&!fs.lstatSync(p).isSymbolicLink());assert(fs.realpathSync(p).startsWith(fs.realpathSync(root)+path.sep));return p;};
const read=relative=>JSON.parse(fs.readFileSync(safe(relative),'utf8'));
const hash=data=>createHash('sha256').update(data).digest('hex');
const m=read('maintenance/engine-consolidation/2026-10-22/receipt.json'),imports=read('maintenance/engine-source-imports.json');
assert.equal(m.schema,'kotoba.engine-source-consolidation.v1');assert.equal(m.owner,'kotoba-lang/kotobase-engine-contract');assert.equal(m.repositories.length,3);assert.equal(m['protected-original-pin-holds'],239);assert.equal(m['repository-deletions'],0);
const git=(cwd,args)=>{const p=spawnSync('git',['-C',cwd,...args],{encoding:'utf8',maxBuffer:32*1024*1024});assert.equal(p.status,0,p.stderr);return p.stdout.trim();};
const blob=(cwd,sha,file)=>{const p=spawnSync('git',['-C',cwd,'show',sha+':'+file],{maxBuffer:16*1024*1024});assert.equal(p.status,0,String(p.stderr));return p.stdout;};
const workspace=process.argv[2];if(workspace){assert(allowed(workspace));fs.mkdirSync(workspace,{recursive:true});}
const seen=new Set();let count=0,pulls=0,files=0;
for(const row of m.repositories){
  assert(!seen.has(row.repository));seen.add(row.repository);assert(row['history-restored-and-fsck']);
  const origin=imports.imports.find(r=>r.repository===row.repository);assert(origin&&origin.commit===row.commit&&origin.tree===row.tree&&origin.id===row.id);
  assert.equal(hash(fs.readFileSync(safe(row['history-bundle']))),row['bundle-sha256']);assert.equal(hash(fs.readFileSync(safe(row['github-snapshot']))),row['github-sha256']);
  const snapshot=read(row['github-snapshot']),before=snapshot['repository-before-archive'];assert.equal(before.nameWithOwner,row.repository);assert(!before.isPrivate&&!before.isArchived);assert.equal(before.defaultBranchRef.target.oid,row.commit);assert.equal(snapshot['historical-pulls'].length,before.allPRs.totalCount);pulls+=snapshot['historical-pulls'].length;
  if(row.archived){
    assert.equal(row['archive-status'],'archived-after-main-verification');assert(snapshot['archive-readback']?.archived&&snapshot['archive-readback']['source-and-refs-unchanged']);assert.deepEqual(snapshot['repository-after-archive'],{...before,isArchived:true});
    const v=m['main-verification'];assert.match(v?.commit??'',/^[a-f0-9]{40}$/);assert.equal(v['JVM'].projects,4);assert.equal(v['JVM'].failures,0);assert.equal(v['JVM'].errors,0);assert.equal(v['compiled-CLJS'].projects,4);assert.equal(v['compiled-CLJS'].failures,0);assert.equal(v['source-origins'].length,3);assert.equal(v['public-source-CLI'].exactLookups,9);assert(v['source-preservation-rechecked']&&v['production-default-eligibility-unchanged']);
  }else assert.equal(row['archive-status'],'pending-main-verification');
  const heads=new Map(git(root,['bundle','list-heads',safe(row['history-bundle'])]).split('\n').map(line=>{const [oid,ref]=line.split(' ');return [ref,oid];}));
  assert.equal(heads.get('HEAD'),row['original-local-HEAD']);assert.equal(heads.size,row['preserved-refs'].length+1+row['linked-worktree-bundle-heads'].length);
  for(const h of row['linked-worktree-bundle-heads']){assert(h.ref.startsWith('worktrees/')&&h.ref.endsWith('/HEAD'));assert.equal(heads.get(h.ref),h.object);assert(row['original-working-trees'].some(w=>w.HEAD===h.object));}
  for(const ref of row['preserved-refs']){
    assert.equal(heads.get(ref.ref),ref.object);
    if(!ref['default-ancestor']){assert.equal(ref.commit,ref['reviewed-nonancestor']);const r=imports['branch-reviews'].find(r=>r.repository===row.repository&&r.commit===ref.commit);assert(r&&r.decision===ref.decision&&r.review?.trim());assert(['merged-squash-with-reviewed-successor','superseded-admin-tuple','preserved-rejected-noop-option','preserved-rejected-experimental-format'].includes(r.decision));}
  }
  for(const review of imports['branch-reviews'].filter(r=>r.repository===row.repository))for(const b of review['production-source-lineage'])if(b['review-diff'])assert.equal(hash(fs.readFileSync(safe(b['review-diff']))),b['review-diff-sha256']);
  if(workspace){
    const tmp=fs.mkdtempSync(path.join(path.resolve(workspace),'engine-restore-'));
    try{
      git(root,['clone','--mirror',safe(row['history-bundle']),tmp]);git(tmp,['fsck','--full']);assert(!fs.existsSync(path.join(tmp,'objects/info/alternates')));assert.equal(git(tmp,['rev-parse',row.commit+'^{tree}']),row.tree);
      for(const ref of row['preserved-refs'])assert.equal(git(tmp,['rev-parse',ref.ref]),ref.object);
      for(const file of origin.files){assert.equal(hash(blob(tmp,row.commit,file.source)),file.sha256);files++;}
      for(const p of snapshot['historical-pulls']){assert.equal(git(tmp,['rev-parse','refs/preservation/engine-monorepo-20261022/pull-'+p.number]),p.headRefOid);if(p.state==='MERGED')git(tmp,['merge-base','--is-ancestor',p.mergeCommit.oid,row.commit]);}
      for(const review of imports['branch-reviews'].filter(r=>r.repository===row.repository))for(const b of review['production-source-lineage']){assert.equal(hash(blob(tmp,review.commit,b.source)),b['source-sha256']);assert.equal(hash(blob(tmp,row.commit,b.successor)),b['successor-sha256']);}
    }finally{fs.rmSync(tmp,{recursive:true,force:true});}
  }
  count+=row['preserved-refs'].length;
}
assert.equal(count,83);assert.equal(pulls,24);
console.log(`engine history: 3 complete histories, ${count} refs, ${pulls} historical PRs${workspace?`, restored/fsck and ${files} original file hashes verified`:''}; rejected experiments retained without runtime admission`);
