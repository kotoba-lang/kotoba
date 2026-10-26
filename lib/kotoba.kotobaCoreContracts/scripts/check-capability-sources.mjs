import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {validateCatalog,sourcePaths} from './capability-sources.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const file=relative=>{
  const target=path.resolve(root,relative);
  assert(target.startsWith(root+path.sep)&&fs.lstatSync(target).isFile()&&!fs.lstatSync(target).isSymbolicLink());
  assert(fs.realpathSync(target).startsWith(fs.realpathSync(root)+path.sep));return target;
};
const read=relative=>JSON.parse(fs.readFileSync(file(relative),'utf8'));
const catalog=validateCatalog(read('capabilities/catalog.json'));
const imports=read('maintenance/capability-source-imports.json');
assert.equal(imports.schema,'kotoba.capability-source-imports.v1');
assert.equal(catalog.packages.length,61);assert.equal(imports.imports.length,61);
const seen=new Set(),changes=new Set();let files=0,historyOnly=0;
for(const origin of imports.imports){
  assert.match(origin.commit,/^[0-9a-f]{40}$/);assert.match(origin.tree,/^[0-9a-f]{40}$/);
  const row=catalog.packages.find(row=>row.id===origin.id);assert(row&&row.path===origin.path&&row['legacy-repository']===origin.repository);
  assert(origin.files.some(file=>file.source==='LICENSE'));sourcePaths(root,row);
  for(const source of origin.files){
    if(source['history-only-generated-metadata']){
      assert(source.source.startsWith('.cpcache/')&&!source.path);assert.match(source.sha256,/^[0-9a-f]{64}$/);historyOnly++;continue;
    }
    assert.equal(source.path,origin.path+'/'+source.source);assert(!seen.has(source.path));seen.add(source.path);
    const bytes=fs.readFileSync(file(source.path)),change=imports['local-changes'][source.path];
    const correction=imports['identity-corrections']?.find(row=>row.paths.includes(source.path));
    assert.match(source.sha256,/^[0-9a-f]{64}$/);
    if(change){
      changes.add(source.path);assert.equal(change['imported-sha256'],source.sha256);assert(change.reason?.trim());
      assert(!source.source.startsWith('src/')||correction,'production source must stay byte-identical');
      assert(source.source==='deps.edn'||source.source==='nbb.edn'||source.source==='LICENSE'||source.source.startsWith('test/')||correction,'unreviewed metadata mutation');
      if(correction){
        assert.equal(correction.id,origin.id);assert.equal(correction.repository,origin.repository);
        assert.equal(digest(Buffer.from(bytes.toString().replaceAll(correction['corrected-cid'],correction['old-declared-cid']))),source.sha256,'identity correction changed more than its one CID literal');
      }
      if(source.source==='LICENSE')assert.equal(digest(Buffer.concat([bytes,Buffer.from('\n')])),source.sha256,'license wording must remain unchanged');
    }
    assert.equal(digest(bytes),change?.sha256??source.sha256,'imported source drift');
    assert.equal(Boolean(fs.statSync(file(source.path)).mode&0o111),source.mode==='100755');
    if(source.source==='capability.edn'){
      assert(!change||correction,'manifest identity/admission fields must stay unchanged');
      assert(bytes.toString().includes(`:capability/definition-cid "${row['definition-cid']}"`));
      assert(bytes.toString().includes(`:capability/id "${row['capability-id']}"`));
    }
    if(source.source.startsWith('artifacts/'))assert(!change,'provider artifact bytes must stay unchanged');
    files++;
  }
}
assert.deepEqual([...changes].sort(),Object.keys(imports['local-changes']).sort());
for(const [relative,addition] of Object.entries(imports.additions??{})){
  assert(!seen.has(relative)&&relative.startsWith('capabilities/')&&relative.endsWith('/nbb.edn'));assert(addition.reason?.trim());
  assert.equal(digest(fs.readFileSync(file(relative))),addition.sha256);seen.add(relative);
}
// Detect extra source files while allowing the resolver's rebuildable caches.
function inventory(dir){return fs.readdirSync(path.join(root,dir),{withFileTypes:true}).flatMap(entry=>{
  if(['.cpcache','.nbb','target','.clj-kondo','node_modules'].includes(entry.name))return [];
  const relative=dir+'/'+entry.name;assert(!entry.isSymbolicLink());return entry.isDirectory()?inventory(relative):[relative];
});}
assert.deepEqual(inventory('capabilities').sort(),[...seen,'capabilities/catalog.json'].sort(),'unreviewed capability package file');
assert.equal(new Set(catalog.packages.map(row=>row['definition-cid'])).size,60,'retain semantic CID aliases; do not invent new CIDs');
console.log(`capability source: 61 packages, 60 semantic definitions, ${files} active imported files + ${historyOnly} historical cache records; provider bytes and authority fields retained; one explicit CID metadata correction`);
