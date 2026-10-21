import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const root=process.cwd(),base=process.argv[2];assert(base?.includes('/github/workspaces/'));
fs.mkdirSync(base,{recursive:true});const tmp=fs.mkdtempSync(path.join(base,'tooling-negative-'));
try{
 fs.mkdirSync(path.join(tmp,'scripts'));fs.copyFileSync(path.join(root,'scripts/check-tooling-consolidation.mjs'),path.join(tmp,'scripts/check-tooling-consolidation.mjs'));
 fs.cpSync(path.join(root,'lib'),path.join(tmp,'lib'),{recursive:true});
 for(const dir of ['maintenance/tooling-consolidation','maintenance/retired-libraries'])fs.cpSync(path.join(root,dir),path.join(tmp,dir),{recursive:true});
 const file=path.join(tmp,'maintenance/tooling-consolidation/2026-10-22/receipt.json'),original=fs.readFileSync(file),manifest=JSON.parse(original);
 const check=()=>spawnSync(process.execPath,[path.join(tmp,'scripts/check-tooling-consolidation.mjs')],{encoding:'utf8'});
 assert.equal(check().status,0);let refused=0;
 const mutation=fn=>{try{fn();assert.notEqual(check().status,0);refused++;}finally{fs.writeFileSync(file,original);}};
 mutation(()=>{const m=JSON.parse(original);m.repositories.pop();fs.writeFileSync(file,JSON.stringify(m));});
 mutation(()=>{const m=JSON.parse(original);m.repositories[0]['preserved-refs'][0].object='0'.repeat(40);fs.writeFileSync(file,JSON.stringify(m));});
 mutation(()=>{const m=JSON.parse(original);m.repositories[0].archived=true;m.repositories[0]['archive-status']='archived-after-main-verification';fs.writeFileSync(file,JSON.stringify(m));});
 const bundle=path.join(tmp,manifest.repositories[0]['history-bundle']),bytes=fs.readFileSync(bundle);
 try{mutation(()=>{const bad=Buffer.from(bytes);bad[0]^=1;fs.writeFileSync(bundle,bad);});}finally{fs.writeFileSync(bundle,bytes);}
 assert.equal(check().status,0);console.log(`tooling recovery: baseline PASS; ${refused} missing-repo/ref/archive-proof/bundle mutations refused`);
}finally{fs.rmSync(tmp,{recursive:true,force:true});}
