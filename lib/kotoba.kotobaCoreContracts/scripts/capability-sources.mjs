import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const home=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export function validateCatalog(catalog){
  const fail=problem=>{throw new Error(problem);};
  if(catalog?.schema!=='kotoba.capability-source-catalog.v1'||catalog.owner!=='kotoba-lang/kotoba-core-contracts'||catalog['source-only']!==true||!Array.isArray(catalog.packages)||!catalog.packages.length)fail('invalid-source-catalog');
  const names=new Set();
  for(const row of catalog.packages){
    if(!/^kotoba(?:\.[a-z][a-z0-9]*)+$/.test(row.id)||row.path!==`capabilities/${row.id}`||row.manifest!=='capability.edn'||JSON.stringify(row['source-paths'])!=='["src"]'||row.admission!=='requires-existing-runtime-admission')fail('invalid-source-path-or-id');
    if(!/^bafy[a-z2-7]+$/.test(row['definition-cid'])||!Array.isArray(row.aliases)||!row.aliases.length)fail('invalid-source-identity');
    if(!/^kotoba-lang\/capability-[a-z0-9]+(?:-[a-z0-9]+)*$/.test(row['legacy-repository'])||JSON.stringify(row.aliases)!==JSON.stringify([row['legacy-repository'],'io.github.'+row['legacy-repository']]))fail('invalid-legacy-source-aliases');
    for(const name of [row.id,...row.aliases]){if(typeof name!=='string'||!name||names.has(name))fail('duplicate-source-id-or-alias');names.add(name);}
  }
  return catalog;
}
export function resolveSource(catalog,name){
  validateCatalog(catalog);
  const matches=catalog.packages.filter(row=>row.id===name||row.aliases.includes(name)||row['definition-cid']===name);
  if(!matches.length)return {ok:false,problem:'unknown-source',requested:name};
  if(matches.length!==1)return {ok:false,problem:'ambiguous-source',requested:name,candidates:matches.map(row=>row.id).sort()};
  return {ok:true,package:matches[0],admission:'not-granted'};
}
export function sourcePaths(root,row){
  return row['source-paths'].map(relative=>{
    const packageRoot=path.resolve(root,row.path),target=path.resolve(packageRoot,relative),real=fs.realpathSync(target),base=fs.realpathSync(root);
    if(fs.lstatSync(packageRoot).isSymbolicLink()||fs.lstatSync(target).isSymbolicLink()||!target.startsWith(path.resolve(root)+path.sep)||!real.startsWith(base+path.sep)||!real.startsWith(fs.realpathSync(packageRoot)+path.sep)||!fs.statSync(real).isDirectory())throw new Error('source-path-unavailable');
    return real;
  });
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{
    const catalog=validateCatalog(JSON.parse(fs.readFileSync(path.join(home,'capabilities/catalog.json'),'utf8')));
    const [command,...names]=process.argv.slice(2);let result;
    if(command==='list'&&!names.length)result={ok:true,packages:catalog.packages,admission:'not-granted'};
    else if(command==='resolve'&&names.length===1){result=resolveSource(catalog,names[0]);if(result.ok)result.paths=sourcePaths(home,result.package);}
    else if(command==='classpath'&&names.length){
      const rows=names.map(name=>resolveSource(catalog,name)),bad=rows.find(row=>!row.ok);
      if(bad)result=bad;
      else {const packages=[...new Map(rows.map(row=>[row.package.id,row.package])).values()];result={ok:true,ids:packages.map(row=>row.id),paths:packages.flatMap(row=>sourcePaths(home,row)),admission:'not-granted'};}
    }else result={ok:false,problem:'usage',usage:'list | resolve ID/ALIAS/CID | classpath ID...'};
    console.log(JSON.stringify(result));if(!result.ok)process.exitCode=1;
  }catch(error){console.log(JSON.stringify({ok:false,problem:error.message}));process.exitCode=1;}
}
