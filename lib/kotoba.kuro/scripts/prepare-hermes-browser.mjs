// Stage an offline, hash-checked browser dependency closure. Never copy a native venv.
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const root = 'target/browser-tools';
const index = JSON.parse(await readFile('node_modules/pyodide/pyodide-lock.json'));
const seeds = ['pydantic', 'httpx', 'rich', 'requests', 'jinja2', 'ruamel-yaml', 'packaging', 'tiktoken', 'pyyaml', 'micropip', 'anyio', 'jiter', 'pytz', 'tqdm', 'wcwidth'];
const packages = new Set();
function visit(name) {name=name.replaceAll("_", "-"); if(packages.has(name)) return; const p=index.packages[name]; if(!p) throw Error(`missing Pyodide package ${name}`); packages.add(name); for(const d of p.depends) visit(d);}
seeds.forEach(visit);
const specs = {'openai':'2.24.0','python-dotenv':'1.2.2','truststore':'0.10.4','fire':'0.7.1','tenacity':'9.1.4','tomli-w':'1.2.0','prompt-toolkit':'3.0.52','croniter':'6.0.0','snowballstemmer':'3.1.1','Markdown':'3.10.2','PyJWT':'2.13.0','distro':'1.9.0','jiter':'0.13.0','sniffio':'1.3.1','termcolor':'3.3.0','python-dateutil':'2.9.0.post0','six':'1.17.0'};
// jiter is a native SDK dependency: use the Pyodide ABI build, not a macOS wheel.
if(index.packages.jiter) {visit('jiter'); delete specs.jiter;}
await mkdir(`${root}/wheels`, {recursive:true});
const manifest=[];
async function stage(p, directory) {
 const destination=`${root}/${directory}/${p.file_name}`;
 let data; try {data=await readFile(destination);} catch {const r=await fetch(p.url); if(!r.ok) throw Error(`${r.status}: ${p.url}`); data=Buffer.from(await r.arrayBuffer());}
 if(createHash('sha256').update(data).digest('hex')!==p.sha256) throw Error(`hash mismatch: ${p.name}`);
 await writeFile(destination,data); manifest.push({...p,path:`${directory}/${p.file_name}`});
}
let locked;
try {locked=JSON.parse(await readFile('docs/verification/hermes-browser-dependencies.json'));} catch {}
if(locked) {
 if(locked.pyodide!=='314.0.7') throw Error('dependency lock ABI mismatch');
 for(const p of locked.packages) await stage(p,p.path.split('/')[0]);
} else {
for(const name of packages) {const p=index.packages[name]; await stage({name,version:p.version,file_name:p.file_name,sha256:p.sha256,url:`https://cdn.jsdelivr.net/pyodide/v314.0.7/full/${p.file_name}`},'pyodide');}
for(const [name,version] of Object.entries(specs)) {
 const response=await fetch(`https://pypi.org/pypi/${name}/${version}/json`); if(!response.ok) throw Error(`PyPI ${name}: ${response.status}`);
 const info=await response.json(); const wheel=info.urls.find(w=>/-py3-none-any\.whl$/.test(w.filename)||/-py2.py3-none-any\.whl$/.test(w.filename));
 if(!wheel) throw Error(`no pure Python wheel: ${name}`);
 await stage({name,version,file_name:wheel.filename,sha256:wheel.digests.sha256,url:wheel.url},'wheels');
}
}
const source=process.argv[2];
if(source) {
 const revision=execFileSync('git',['-C',source,'rev-parse','HEAD'],{encoding:'utf8'}).trim();
 if(revision!=='4f649c65e35beed816f9a9ec5647d33133a25abf') throw Error('Hermes revision must be requalified before use');
 const paths=execFileSync('git',['-C',source,'ls-tree','-r','--name-only',revision],{encoding:'utf8'}).trim().split('\n').filter(p=>! /^(tests|evals|website|scripts|assets)\//.test(p) && (p.endsWith('.py')||['pyproject.toml','uv.lock','compat_manifest.json','LICENSE'].includes(p)));
 const archive=execFileSync('git',['-C',source,'archive','--format=tar.gz',revision,...paths],{maxBuffer:128*1024*1024});
 await writeFile(`${root}/hermes-probe-source.tar.gz`,archive);
 await writeFile(`${root}/hermes-source.json`,JSON.stringify({revision,sha256:createHash('sha256').update(archive).digest('hex'),files:paths.length},null,2));
}
await writeFile(`${root}/hermes-dependencies.json`,JSON.stringify({pyodide:'314.0.7',seeds,packages:manifest},null,2)+'\n');
await writeFile('docs/verification/hermes-browser-dependencies.json',JSON.stringify({pyodide:'314.0.7',seeds,packages:manifest},null,2)+'\n');
console.log(`Staged ${manifest.length} packages; browser runs require no external package requests.`);
