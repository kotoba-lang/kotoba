import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
const root = process.cwd(), workspace = process.argv[2];
assert(workspace?.includes('/github/workspaces/'), 'provide a task workspace');
fs.mkdirSync(workspace,{recursive:true});
const tmp = fs.mkdtempSync(path.join(workspace,'family-preservation-negative-'));
try {
  fs.mkdirSync(path.join(tmp,'scripts'));
  fs.copyFileSync(path.join(root,'scripts/check-family-consolidations.mjs'),path.join(tmp,'scripts/check-family-consolidations.mjs'));
  fs.cpSync(path.join(root,'maintenance/family-consolidations'),path.join(tmp,'maintenance/family-consolidations'),{recursive:true});
  const held = 'maintenance/retired-libraries/2026-10-22/manifest.json';
  fs.mkdirSync(path.dirname(path.join(tmp,held)),{recursive:true}); fs.copyFileSync(path.join(root,held),path.join(tmp,held));
  const mp = path.join(tmp,'maintenance/family-consolidations/2026-10-22/receipt.json'), original=fs.readFileSync(mp), receipt=JSON.parse(original);
  const check=()=>spawnSync(process.execPath,[path.join(tmp,'scripts/check-family-consolidations.mjs')],{encoding:'utf8'}).status;
  assert.equal(check(),0);
  let refused=0;
  const mutation=fn=>{try{fn();assert.notEqual(check(),0);refused++;}finally{fs.writeFileSync(mp,original);}};
  const bundle=path.join(tmp,receipt.families[0].children[0]['history-bundle']), bytes=fs.readFileSync(bundle);
  try {mutation(()=>{const bad=Buffer.from(bytes);bad[0]^=1;fs.writeFileSync(bundle,bad);});} finally {fs.writeFileSync(bundle,bytes);}
  mutation(()=>{const r=JSON.parse(original);r.families[0].children[0].repo=JSON.parse(fs.readFileSync(path.join(tmp,held)))['held-dependency-pin-repositories'][0];fs.writeFileSync(mp,JSON.stringify(r));});
  mutation(()=>{const r=JSON.parse(original);r.families[0].children[0]['preserved-refs'][0].object='0'.repeat(40);fs.writeFileSync(mp,JSON.stringify(r));});
  const ip=path.join(tmp,receipt.families[0]['import-manifest']), source=fs.readFileSync(ip);
  try {mutation(()=>{const m=JSON.parse(source),r=JSON.parse(original);m['external-dependencies-unchanged']=false;fs.writeFileSync(ip,JSON.stringify(m));r.families[0]['import-manifest-sha256']=crypto.createHash('sha256').update(fs.readFileSync(ip)).digest('hex');fs.writeFileSync(mp,JSON.stringify(r));});} finally {fs.writeFileSync(ip,source);}
  assert.equal(check(),0);
  console.log(`family recovery archive: baseline PASS; ${refused} independent corruption/pin-scope/ref/dependency-proof mutations refused`);
} finally {fs.rmSync(tmp,{recursive:true,force:true});}
