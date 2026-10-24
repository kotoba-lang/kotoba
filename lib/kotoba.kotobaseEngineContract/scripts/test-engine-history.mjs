import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const allowedWorkspace=p=>{const absolute=path.resolve(p),temp=process.env.RUNNER_TEMP&&path.resolve(process.env.RUNNER_TEMP);return absolute.includes('/github/workspaces/')||(process.env.GITHUB_ACTIONS==='true'&&temp&&(absolute===temp||absolute.startsWith(temp+path.sep)));};
const root=process.cwd(),base=process.argv[2];assert(base&&allowedWorkspace(base));fs.mkdirSync(base,{recursive:true});
const tmp=fs.mkdtempSync(path.join(base,'engine-history-negative-'));
try{
  fs.mkdirSync(path.join(tmp,'scripts'));fs.copyFileSync(path.join(root,'scripts/check-engine-history.mjs'),path.join(tmp,'scripts/check-engine-history.mjs'));
  fs.cpSync(path.join(root,'maintenance'),path.join(tmp,'maintenance'),{recursive:true});
  const relative='maintenance/engine-consolidation/2026-10-22/receipt.json',file=path.join(tmp,relative),original=fs.readFileSync(file),receipt=JSON.parse(original);
  const check=()=>spawnSync(process.execPath,[path.join(tmp,'scripts/check-engine-history.mjs')],{encoding:'utf8'}).status;assert.equal(check(),0);let refused=0;
  const mutation=fn=>{try{fn();assert.notEqual(check(),0);refused++;}finally{fs.writeFileSync(file,original);}};
  mutation(()=>{const m=JSON.parse(original);m.repositories[0]['preserved-refs'][0].object='0'.repeat(40);fs.writeFileSync(file,JSON.stringify(m));});
  mutation(()=>{const m=JSON.parse(original);m.repositories[0].archived=true;m.repositories[0]['archive-status']='archived-after-main-verification';delete m['main-verification'];fs.writeFileSync(file,JSON.stringify(m));});
  const bundle=path.join(tmp,receipt.repositories[0]['history-bundle']),bytes=fs.readFileSync(bundle);
  try{mutation(()=>{const corrupt=Buffer.from(bytes);corrupt[0]^=1;fs.writeFileSync(bundle,corrupt);});}finally{fs.writeFileSync(bundle,bytes);}
  const ip=path.join(tmp,'maintenance/engine-source-imports.json'),ib=fs.readFileSync(ip);
  try{mutation(()=>{const m=JSON.parse(ib);m['branch-reviews']=[];fs.writeFileSync(ip,JSON.stringify(m));});}finally{fs.writeFileSync(ip,ib);}
  mutation(()=>{const m=JSON.parse(original);const row=m.repositories.find(r=>r['linked-worktree-bundle-heads'].length);row['linked-worktree-bundle-heads'][0].object='0'.repeat(40);fs.writeFileSync(file,JSON.stringify(m));});
  const imported=JSON.parse(ib),review=imported['branch-reviews'].flatMap(r=>r['production-source-lineage']).find(r=>r['review-diff']);
  const df=path.join(tmp,review['review-diff']),db=fs.readFileSync(df);
  try{mutation(()=>{fs.writeFileSync(df,Buffer.concat([db,Buffer.from('unreviewed drift')]));});}finally{fs.writeFileSync(df,db);}
  assert.equal(check(),0);console.log(`engine recovery: baseline PASS; ${refused} ref/archive-proof/bundle/branch-review/linked-HEAD/review-diff mutations refused`);
}finally{fs.rmSync(tmp,{recursive:true,force:true});}
