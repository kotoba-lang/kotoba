// shadow-cljs still discovers .cljc/.cljs. Generate byte-identical .cljc views
// of the resolved, pinned .cljk classpath; never rename authoritative sources.
import {execFileSync} from 'node:child_process';
import {readdir,readFile,writeFile,mkdir,rm,stat} from 'node:fs/promises';
import {resolve,join,delimiter,dirname} from 'node:path';
const output=resolve('target/shadow-cljk');
await rm(output,{recursive:true,force:true});await mkdir(output,{recursive:true});
const roots=execFileSync('clojure',['-Spath'],{encoding:'utf8'}).trim().split(delimiter);
const seen=new Map();let count=0;
async function stage(root,relative='') {
 for(const item of await readdir(join(root,relative),{withFileTypes:true})) {
  const path=join(relative,item.name);if(item.isDirectory())await stage(root,path);
  else if(item.isFile() && /\.(cljk|cljc|cljs)$/.test(item.name)) {
   const content=await readFile(join(root,path));const target=path.replace(/\.cljk$/,'.cljc');
   if(seen.has(target)){if(!seen.get(target).equals(content))throw Error('conflicting classpath source: '+target);continue;}
   seen.set(target,content);await mkdir(dirname(join(output,target)),{recursive:true});await writeFile(join(output,target),content);count++;
  }
 }
}
for(const root of roots) {
 const info=await stat(root).catch(error=>{if(error.code==='ENOENT')return null;throw error;});
 if(resolve(root)!==output && info?.isDirectory())await stage(root);
}
console.log('Staged '+count+' resolved sources; .cljk views generated for shadow-cljs/nbb');
