import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {validateCatalog,resolveSource,sourcePaths} from './protocol-sources.mjs';
const allowedWorkspace=p=>{const absolute=path.resolve(p),temp=process.env.RUNNER_TEMP&&path.resolve(process.env.RUNNER_TEMP);return absolute.includes('/github/workspaces/')||(process.env.GITHUB_ACTIONS==='true'&&temp&&(absolute===temp||absolute.startsWith(temp+path.sep)));};
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const catalog=JSON.parse(fs.readFileSync(path.join(root,'surfaces/catalog.json')));
validateCatalog(catalog);let checked=0;
for(const row of catalog.packages)for(const name of [row.id,...row.aliases]){
  const result=resolveSource(catalog,name);assert(result.ok);assert.equal(result.package.id,row.id);assert.equal(result.admission,'not-granted');sourcePaths(root,row);checked++;
}
for(const name of ['KOTOBA.kotobase.protocol.ipq','kotoba-kotobase-protocol-ipq','git','kotoba.kotobase.protocol.*',' kotoba.kotobase.protocol.ipq'])assert.equal(resolveSource(catalog,name).problem,'unknown-source');
for(const mutate of [
  c=>c.packages[0].aliases.push(c.packages[1].id),
  c=>c.packages[0].aliases.push(c.packages[1].aliases[0]),
  c=>c.packages[0].path='../escape',
  c=>c.packages[0].id='app.kotoba.protocol.ipq',
  c=>c.packages[0].admission='granted',
  c=>c.packages[0]['needs-owner']=false]){
  const c=structuredClone(catalog);mutate(c);assert.throws(()=>validateCatalog(c));
}
assert.equal(sourcePaths(root,catalog.packages.find(r=>r.id==='kotoba.kotobase.protocol.lfs')).length,1,'LFS does not acquire an unrelated protocol-core dependency');
const base=process.argv[2];assert(base&&allowedWorkspace(base),'provide a task workspace');fs.mkdirSync(base,{recursive:true});
const tmp=fs.mkdtempSync(path.join(base,'protocol-source-confinement-'));
try{
  const selected=catalog.packages[0],packageRoot=path.join(tmp,selected.path);fs.mkdirSync(packageRoot,{recursive:true});
  fs.symlinkSync(root,path.join(packageRoot,'src'));assert.throws(()=>sourcePaths(tmp,selected),/source-path-unavailable/);
}finally{fs.rmSync(tmp,{recursive:true,force:true});}
const cli=spawnSync(process.execPath,[path.join(root,'scripts/protocol-sources.mjs'),'classpath',catalog.packages[0].id,...catalog.packages[0].aliases],{cwd:base,encoding:'utf8'});
assert.equal(cli.status,0,cli.stderr);const result=JSON.parse(cli.stdout);assert.deepEqual(result.ids,[catalog.packages[0].id]);assert.equal(result.paths.length,2);assert(result.paths[0].startsWith(root+path.sep));
console.log(`protocol source resolution: ${checked} exact ID/alias lookups, six catalog mutations and symlink escape refusal, external-CWD CLI PASS`);
