import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {validateCatalog,sourcePaths} from './storage-sources.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const safe=relative=>{const target=path.resolve(root,relative);assert(target.startsWith(root+path.sep)&&fs.lstatSync(target).isFile()&&!fs.lstatSync(target).isSymbolicLink());assert(fs.realpathSync(target).startsWith(fs.realpathSync(root)+path.sep));return target;};
const read=relative=>JSON.parse(fs.readFileSync(safe(relative),'utf8'));
const catalog=validateCatalog(read('providers/catalog.json')),imports=read('maintenance/storage-source-imports.json');
assert.equal(imports.schema,'kotoba.storage-source-imports.v1');assert.equal(imports.owner,catalog.owner);
assert.equal(imports.imports.length,7);assert.equal(catalog.packages.length,7);assert.equal(imports['protected-original-pin-holds'],239);
const files=new Set(),usedChanges=new Set();let active=0,historical=0;
for(const origin of imports.imports){
  assert.match(origin.commit,/^[a-f0-9]{40}$/);assert.match(origin.tree,/^[a-f0-9]{40}$/);
  const row=catalog.packages.find(r=>r.id===origin.id);assert(row&&row.path===origin.path&&row['legacy-repository']===origin.repository);sourcePaths(root,row);
  assert(origin.files.some(f=>f.source==='LICENSE'));
  for(const file of origin.files){
    assert.match(file.sha256,/^[a-f0-9]{64}$/);
    if(file['history-only-generated-metadata']){assert(file.source.startsWith('target/')&&!file.path);historical++;continue;}
    assert.equal(file.path,origin.path+'/'+file.source);assert(!files.has(file.path));files.add(file.path);
    const bytes=fs.readFileSync(safe(file.path)),change=imports['local-changes'][file.path];
    if(change){
      usedChanges.add(file.path);assert.equal(change['imported-sha256'],file.sha256);assert(change.reason?.trim());
      assert(['deps.edn','nbb.edn','package.json','package-lock.json','README.md','LICENSE'].includes(file.source)||file.source.startsWith('test/'),'production provider changes require separate implementation review');
    }
    assert.equal(hash(bytes),change?.sha256??file.sha256,'unreviewed source drift: '+file.path);
    assert.equal(Boolean(fs.statSync(safe(file.path)).mode&0o111),file.mode==='100755');active++;
  }
}
assert.deepEqual([...usedChanges].sort(),Object.keys(imports['local-changes']).sort());
for(const [relative,addition] of Object.entries(imports.additions)){
  assert(relative.startsWith('providers/')&&!files.has(relative));assert(addition.reason?.trim());
  assert(relative.endsWith('/nbb.edn')||relative.endsWith('/package-lock.json')||relative==='providers/kotoba.kotobase.storage.s3/scripts/test-compiled.py');assert.equal(hash(fs.readFileSync(safe(relative))),addition.sha256);files.add(relative);
}
function inventory(directory){return fs.readdirSync(path.join(root,directory),{withFileTypes:true}).flatMap(entry=>{
  if(['node_modules','target','.cpcache','.nbb','.shadow-cljs','.cache'].includes(entry.name))return [];
  const relative=directory+'/'+entry.name;assert(!entry.isSymbolicLink());return entry.isDirectory()?inventory(relative):[relative];
});}
assert.deepEqual(inventory('providers').sort(),[...files,'providers/catalog.json'].sort());
assert.equal(historical,17);console.log(`storage source: 7 independent provider projects, ${active} original active files, 17 history-only generated files; provider implementation bytes unchanged`);
