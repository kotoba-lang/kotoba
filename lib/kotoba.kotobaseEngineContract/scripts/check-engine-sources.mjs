import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {validateCatalog,sourcePaths} from './engine-sources.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const safe=relative=>{const p=path.resolve(root,relative);assert(p.startsWith(root+path.sep)&&fs.lstatSync(p).isFile()&&!fs.lstatSync(p).isSymbolicLink());assert(fs.realpathSync(p).startsWith(fs.realpathSync(root)+path.sep));return p;};
const read=relative=>JSON.parse(fs.readFileSync(safe(relative),'utf8'));
const imports=read('maintenance/engine-source-imports.json'),catalog=validateCatalog(read('implementations/catalog.json'));
assert.equal(imports.schema,'kotoba.engine-source-imports.v1');assert.equal(imports.owner,catalog.owner);assert.equal(imports.imports.length,3);assert.equal(catalog.packages.length,3);assert.equal(imports['protected-original-pin-holds'],239);
const files=new Set(),changes=new Set();let count=0;
for(const origin of imports.imports){
  assert.match(origin.commit,/^[a-f0-9]{40}$/);assert.match(origin.tree,/^[a-f0-9]{40}$/);
  const row=catalog.packages.find(r=>r.id===origin.id);assert(row&&row.path===origin.path&&row['legacy-repository']===origin.repository);sourcePaths(root,row);
  assert(origin.files.some(f=>f.source==='LICENSE')&&origin.files.some(f=>f.source==='NOTICE'));
  for(const file of origin.files){
    assert.equal(file.path,origin.path+'/'+file.source);assert(!files.has(file.path));files.add(file.path);
    const change=imports['local-changes'][file.path];
    if(change){assert.equal(change['imported-sha256'],file.sha256);assert(change.reason?.trim());assert(['deps.edn','nbb.edn','package.json','package-lock.json','README.md'].includes(file.source)||file.source.startsWith('test/'),'production engine changes require separate implementation review');changes.add(file.path);}
    assert.equal(hash(fs.readFileSync(safe(file.path))),change?.sha256??file.sha256,'unreviewed drift: '+file.path);
    assert.equal(Boolean(fs.statSync(safe(file.path)).mode&0o111),file.mode==='100755');count++;
    if(['deps.edn','nbb.edn'].includes(file.source))assert.equal(hash(fs.readFileSync(safe('maintenance/original-configs/'+origin.id+'/'+file.source))),file.sha256);
  }
}
assert.deepEqual([...changes].sort(),Object.keys(imports['local-changes']).sort());assert.deepEqual(imports.additions,{});
function inventory(directory){return fs.readdirSync(path.join(root,directory),{withFileTypes:true}).flatMap(e=>{
  if(['node_modules','target','.cpcache','.nbb','.shadow-cljs','.cache'].includes(e.name))return [];
  const relative=directory+'/'+e.name;assert(!e.isSymbolicLink());return e.isDirectory()?inventory(relative):[relative];
});}
assert.deepEqual(inventory('implementations').sort(),[...files,'implementations/catalog.json'].sort());assert.equal(count,56);
const git=args=>{const p=spawnSync('git',['-C',root,...args],{maxBuffer:16*1024*1024});assert.equal(p.status,0,String(p.stderr));return p.stdout;};
const base=imports['owner-base'];assert.match(base,/^[a-f0-9]{40}$/);
const original=git(['ls-tree','-r','--name-only',base,'--','src']).toString().trim().split('\n');
assert.deepEqual(inventory('src').sort(),original.sort());
for(const file of [...original,'deps.edn','nbb.edn','docs/qualification-matrix.edn'])assert.equal(hash(fs.readFileSync(safe(file))),hash(git(['show',base+':'+file])),'neutral production/default graph changed: '+file);
for(const change of [...imports['owner-test-host-adjustments'],...imports['owner-config-adjustments']]){
  assert(change.path.startsWith('test/')||['package.json','package-lock.json'].includes(change.path));assert(change.reason?.trim());
  assert.equal(hash(git(['show',base+':'+change.path])),change['original-sha256']);assert.equal(hash(fs.readFileSync(safe(change.path))),change.sha256);
}
console.log('engine source: 3 opt-in projects / 56 original files; production engine bytes and neutral owner default graph unchanged; test/config adjustments bound');
