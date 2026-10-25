#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
function files(dir) {
  return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>{
    const p=path.join(dir,e.name);
    if(e.isSymbolicLink()) throw Error(`Registry symlink refused: ${p}`);
    return e.isDirectory()?files(p):[p];
  }).sort();
}
function checksum(dir) {
  const h=crypto.createHash('sha256');
  for(const f of files(dir)) {
    h.update(path.relative(dir,f).split(path.sep).join('/')); h.update('\0');
    h.update(fs.readFileSync(f)); h.update('\0');
  }
  return 'sha256:'+h.digest('hex');
}
const entries=[];
const source=JSON.parse(fs.readFileSync(path.join(root,'provenance.json')));
for(const f of files(path.join(root,'skills')).filter(f=>path.basename(f)==='SKILL.md')) {
  const body=fs.readFileSync(f,'utf8');
  if(!body.startsWith('---\n')) throw Error(`Skill frontmatter missing: ${f}`);
  const header=body.slice(4,body.indexOf('\n---',4));
  const value=name=>header.match(new RegExp(`^${name}:\\s*(.+)$`,'m'))?.[1]?.trim();
  const id=value('name'),description=value('description');
  if(!id||!description) throw Error(`Skill identity missing: ${f}`);
  const meta=JSON.parse(value('metadata')||'{}').hermes;
  if(!meta?.version||!meta?.author||!meta?.source) throw Error(`Skill metadata.hermes missing: ${f}`);
  const dir=path.dirname(f),relative=path.relative(root,dir).split(path.sep).join('/');
  if(relative.split('/').length!==3||path.basename(dir)!==id) throw Error(`Skill path differs from id: ${f}`);
  entries.push({id,type:'skill',category:relative.split('/')[1],name:id,version:meta.version,description,author:meta.author,source:meta.source,path:relative,checksum:checksum(dir),compatibility:meta.compatibility});
}
for(const f of files(path.join(root,'mcp')).filter(f=>path.basename(f)==='manifest.json'&&!f.includes('/server/'))) {
  const m=JSON.parse(fs.readFileSync(f));
  for(const k of ['id','name','version','description']) if(typeof m[k]!=='string'||!m[k]) throw Error(`MCP ${k} missing: ${f}`);
  if(m.schemaVersion!=='1'||m.type!=='mcp'||!['stdio','http'].includes(m.transport)) throw Error(`MCP schema mismatch: ${f}`);
  if(!m.compatibility?.hermes||!m.compatibility?.desktop) throw Error(`MCP compatibility missing: ${f}`);
  if(m.transport==='stdio'&&(!m.command||!Array.isArray(m.args))) throw Error(`MCP command missing: ${f}`);
  if(m.transport==='http'&&!m.url) throw Error(`MCP URL missing: ${f}`);
  const dir=path.dirname(f),relative=path.relative(root,dir).split(path.sep).join('/');
  if(relative!==`mcp/${m.id}`) throw Error(`MCP path differs from id: ${f}`);
  entries.push({id:m.id,type:m.type,name:m.name,version:m.version,description:m.description,author:m.author,source:m.source,path:relative,checksum:checksum(dir),compatibility:m.compatibility});
}
entries.sort((a,b)=>`${a.type}/${a.id}`.localeCompare(`${b.type}/${b.id}`));
if(new Set(entries.map(e=>`${e.type}/${e.id}`)).size!==entries.length) throw Error('Duplicate registry identity');
for(const f of source.sourceFiles) {
  const bytes=fs.readFileSync(path.join(root,'mcp/github-forest/server',f.path));
  if(bytes.length!==f.bytes||crypto.createHash('sha256').update(bytes).digest('hex')!==f.sha256) throw Error(`Source snapshot changed: ${f.path}`);
}
const target=path.join(root,'index.json');
const prior=fs.existsSync(target)?JSON.parse(fs.readFileSync(target)):null;
if(process.argv.includes('--check')) {
  if(prior?.schemaVersion!=='1'||prior.count!==entries.length||JSON.stringify(prior.entries)!==JSON.stringify(entries)) throw Error('Registry index is stale; run node scripts/build-index.mjs');
  console.log(`Verified ${entries.length} entries and ${source.sourceFiles.length} source snapshots`);
} else {
  const unchanged=JSON.stringify(prior?.entries)===JSON.stringify(entries);
  fs.writeFileSync(target,JSON.stringify({schemaVersion:'1',generated:unchanged?prior.generated:new Date().toISOString(),count:entries.length,entries},null,2)+'\n');
  console.log(`Indexed ${entries.length} entries`);
}
