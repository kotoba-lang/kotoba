import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const root=process.cwd(),base=process.argv[2];assert(base?.includes('/github/workspaces/'));fs.mkdirSync(base,{recursive:true});
const tmp=fs.mkdtempSync(path.join(base,'capability-provenance-'));
try{
  fs.mkdirSync(path.join(tmp,'scripts'));fs.mkdirSync(path.join(tmp,'maintenance'));
  for(const name of ['check-capability-sources.mjs','capability-sources.mjs'])fs.copyFileSync(path.join(root,'scripts',name),path.join(tmp,'scripts',name));
  fs.cpSync(path.join(root,'capabilities'),path.join(tmp,'capabilities'),{recursive:true,filter:file=>!file.split(path.sep).some(x=>['.cpcache','.nbb','target','.clj-kondo','node_modules'].includes(x))});
  const metadata='maintenance/capability-source-imports.json';fs.copyFileSync(path.join(root,metadata),path.join(tmp,metadata));
  const check=()=>spawnSync(process.execPath,[path.join(tmp,'scripts/check-capability-sources.mjs')],{encoding:'utf8'});
  assert.equal(check().status,0);let refused=0;
  const mutate=(relative,fn)=>{const file=path.join(tmp,relative),before=fs.readFileSync(file);try{fs.writeFileSync(file,fn(before));assert.notEqual(check().status,0);refused++;}finally{fs.writeFileSync(file,before);}};
  const m=JSON.parse(fs.readFileSync(path.join(tmp,metadata)));
  const artifact=m.imports.flatMap(r=>r.files).find(f=>f.path?.endsWith('.wasm'));
  mutate(artifact.path,bytes=>{const b=Buffer.from(bytes);b[b.length-1]^=1;return b;});
  const source=m.imports[0].files.find(f=>f.source.startsWith('src/'));
  mutate(source.path,bytes=>Buffer.concat([bytes,Buffer.from('\n; drift\n')]));
  const added='capabilities/'+m.imports[0].id+'/src/unreviewed.cljk';fs.writeFileSync(path.join(tmp,added),'(ns unreviewed)\n');try{assert.notEqual(check().status,0);refused++;}finally{fs.unlinkSync(path.join(tmp,added));}
  const corrected=m['identity-corrections'][0].paths.find(p=>p.endsWith('/capability.edn'));
  const file=path.join(tmp,corrected),oldFile=fs.readFileSync(file),oldMetadata=fs.readFileSync(path.join(tmp,metadata));
  try{
    const changed=oldFile.toString().replace(':approval-required',':autonomous');assert.notEqual(changed,oldFile.toString());fs.writeFileSync(file,changed);
    const receipt=JSON.parse(oldMetadata);receipt['local-changes'][corrected].sha256=createHash('sha256').update(changed).digest('hex');fs.writeFileSync(path.join(tmp,metadata),JSON.stringify(receipt));
    assert.notEqual(check().status,0,'a CID correction must not launder policy changes');refused++;
  }finally{fs.writeFileSync(file,oldFile);fs.writeFileSync(path.join(tmp,metadata),oldMetadata);}
  assert.equal(check().status,0);console.log(`capability provenance: baseline PASS; ${refused} artifact/source/unreviewed-file/CID-policy-laundering mutations refused`);
}finally{fs.rmSync(tmp,{recursive:true,force:true});}
