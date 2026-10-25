#!/usr/bin/env node
// Local Git forest operations. No shell interpolation, SDK, daemon or credentials.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync,spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import readline from 'node:readline';

export const DEFAULT_ROOT = '/Users/junkawasaki/github';
const here = path.dirname(fileURLToPath(import.meta.url));
const version = 1;
const fail = message => { throw new Error(message); };
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const exists = p => { try { fs.lstatSync(p); return true; } catch { return false; } };
const real = p => fs.realpathSync(p);
const inside = (p, root) => p === root || p.startsWith(root + path.sep);
const segment = s => typeof s === 'string' && /^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(s) && s !== '..';
const slugOK = s => typeof s === 'string' && s.split('/').length === 2 && s.split('/').every(segment);
function run(cmd, args, cwd, allowFailure = false, input) {
  const r = spawnSync(cmd, args, {cwd, input, encoding:'utf8', timeout:120000,
    maxBuffer:64*1024*1024, env:{...process.env, GIT_TERMINAL_PROMPT:'0'}});
  if ((r.error || r.status !== 0) && !allowFailure)
    fail(`${cmd} failed: ${(r.error?.message || r.stderr || r.stdout).slice(0,1500)}`);
  return {code:r.error ? 99 : r.status, out:r.stdout || '', err:r.stderr || ''};
}
const git = (p, args, optional=false, input) => run('git', ['-c','core.fsmonitor=false','-C',p,...args], p, optional, input);
function forest(root=DEFAULT_ROOT) {
  root = real(path.resolve(root));
  if (!exists(path.join(root,'.west','config'))) fail('Forest needs its own .west/config');
  return root;
}
function repoPath(root,p) {
  if (typeof p !== 'string' || !p || p.includes('\0')) fail('Repository path required');
  const absolute = path.resolve(root,p);
  if (!inside(absolute,root)) fail('Repository path escapes forest');
  const resolved = real(absolute);
  if (!inside(resolved,root)) fail('Repository symlink escapes forest');
  return resolved;
}
function writeJSON(file, data) {
  fs.mkdirSync(path.dirname(file), {recursive:true});
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp,JSON.stringify(data,null,2)+'\n',{mode:0o600}); fs.renameSync(tmp,file);
}
function reportPath(root,p) {
  const base = path.join(root,'workspaces');
  const dest=path.resolve(p);
  if (!inside(dest,base)) fail('Reports and plans belong under github/workspaces');
  // Reject a symlink ancestor, including a report directory already redirected elsewhere.
  let ancestor=dest; while (!exists(ancestor)) ancestor=path.dirname(ancestor);
  if (!inside(real(ancestor),base)) fail('Report symlink escapes workspaces');
  return dest;
}
function status(p) {
  const raw=git(p,['status','--porcelain=v1','-z','--untracked-files=normal']).out;
  const parts=raw.split('\0'); const files=[];
  for (let i=0;i<parts.length;i++) {
    const s=parts[i]; if(!s) continue;
    const f={status:s.slice(0,2),path:s.slice(3)};
    if (/[RC]/.test(f.status)) f.old_path=parts[++i];
    files.push(f);
  }
  return {raw,files};
}
function remoteSlug(url) {
  // A URL with a password/token is never included in reports.
  const m=url.match(/^(?:git@github\.com:|ssh:\/\/git@github\.com\/|https:\/\/github\.com\/)([^/\s]+\/[^/\s]+?)(?:\.git)?$/i);
  return m && slugOK(m[1]) ? m[1] : null;
}
function snapshot(p) {
  const head=git(p,['rev-parse','HEAD']).out.trim();
  const s=status(p);
  const common=git(p,['rev-parse','--path-format=absolute','--git-common-dir']).out.trim();
  const stash=git(p,['stash','list','--format=%H']).out.trim().split('\n').filter(Boolean);
  const branch=git(p,['symbolic-ref','-q','--short','HEAD'],true).out.trim();
  const worktrees=git(p,['worktree','list','--porcelain']).out;
  const content=s.files.map(f=>({path:f.path,...blob(p,f.path)}));
  const fingerprint=hash(JSON.stringify({head,status:s.raw,content,
    index:hash(git(p,['diff','--cached','--binary']).out),stash,branch,worktrees}));
  return {head,branch,common,stash,files:s.files,fingerprint,worktrees};
}
function projects(root) {
  // Ask west to parse imports/groups/YAML instead of maintaining another YAML parser.
  const list=run('west',['list','--all','-f','{name}\t{path}\t{revision}\t{groups}'],root).out;
  const result=[];
  for (const line of list.trim().split('\n')) {
    const [name,p,revision,groups='']=line.split('\t');
    if (slugOK(p) && /^[0-9a-f]{40}$/.test(revision || ''))
      result.push({name,path:p,revision,groups});
  }
  return result;
}
function discover(root) {
  const found=new Set(); const ignored=new Set(['.git','node_modules','.venv','venv','__pycache__','.cpcache','.cache','target','build']);
  function walk(dir,depth) {
    if (exists(path.join(dir,'.git'))) { found.add(dir); return; }
    if (!depth) return;
    for (const e of fs.readdirSync(dir,{withFileTypes:true}))
      if (e.isDirectory() && !ignored.has(e.name) && !e.name.startsWith('.')) walk(path.join(dir,e.name),depth-1);
  }
  for(const e of fs.readdirSync(root,{withFileTypes:true})) {
    if (!e.isDirectory() || e.name.startsWith('.')) continue;
    walk(path.join(root,e.name), ['wt','workspaces'].includes(e.name) ? 5 : 2);
  }
  return [...found].sort();
}
function metadata(p,remote) {
  const url=git(p,['config','--get',`remote.${remote}.url`]).out.trim();
  const slug=remoteSlug(url); if(!slug) fail('Primary remote is not a plain GitHub URL');
  const m=JSON.parse(run('gh',['api',`repos/${slug}`],p).out);
  if(!slugOK(m.full_name) || !segment(m.default_branch)) fail('GitHub identity/default branch unresolved');
  return {slug:m.full_name,default_branch:m.default_branch,archived:m.archived,private:m.private,remote};
}
function primaryRemote(p) {
  const names=git(p,['remote']).out.trim().split('\n').filter(Boolean);
  const name=names.includes('origin') ? 'origin' : names[0];
  if(!name) fail('Repository has no primary remote');
  return name;
}
function branchReview(p,tip,checked,prs) {
  return git(p,['for-each-ref','--format=%(refname:short)\t%(objectname)\t%(committerdate:unix)','refs/heads']).out.trim().split('\n').filter(Boolean).map(line=>{
    const [name,sha,timestamp]=line.split('\t');
    return {name,sha,timestamp:Number(timestamp),checked_out:checked.has(name),
      open_pr:prs.some(pr=>pr.headRefName===name),
      classification:tip ? (git(p,['merge-base','--is-ancestor',sha,tip],true).code===0 ? 'integrated' : 'unintegrated') : 'unverified'};
  });
}
export function audit(args={}) {
  const root=forest(args.root); const registered=projects(root);
  const selected=args.paths?.length ? args.paths.map(p=>repoPath(root,p)) : discover(root);
  const upstreamCache=new Map(); const rows=[];
  for(const p of [...new Set(selected)]) {
    try {
      const s=snapshot(p); const registeredAt=registered.find(x=>x.path===path.relative(root,p));
      const row={path:path.relative(root,p),...s,project:registeredAt || null};
      row.shallow=git(p,['rev-parse','--is-shallow-repository']).out.trim()==='true';
      const remotes=git(p,['remote']).out.trim().split('\n').filter(Boolean);
      const remote=remotes.includes('origin') ? 'origin' : remotes[0];
      row.slug=remote ? remoteSlug(git(p,['config','--get',`remote.${remote}.url`]).out.trim()) : null;
      let upstream=null;
      if (args.fetch && remote) {
        if (!upstreamCache.has(s.common)) {
          try {
            const m=metadata(p,remote);
            const ref='refs/audit/forest-maintenance/default';
            git(p,['fetch','--no-tags',remote,`refs/heads/${m.default_branch}:${ref}`]);
            const tip=git(p,['rev-parse',ref]).out.trim();
            const prs=JSON.parse(run('gh',['pr','list','--repo',m.slug,'--state','open','--limit','10000','--json','number,headRefName,isDraft,url'],p).out);
            upstreamCache.set(s.common,{...m,tip,prs,verified_at:new Date().toISOString()});
          } catch(e) { upstreamCache.set(s.common,{error:e.message}); }
        }
        upstream=upstreamCache.get(s.common);
      }
      row.upstream=upstream; if(upstream?.slug) row.slug=upstream.slug;
      const checked=new Set(s.worktrees.split('\n').filter(l=>l.startsWith('branch refs/heads/')).map(l=>l.slice(18)));
      row.branches=branchReview(p,upstream?.tip,checked,upstream?.prs || []);
      // Shallow ancestry absence is not proof of being unlanded or safe to delete.
      if(row.shallow) row.branches=row.branches.map(b=>({...b,classification:'shallow-unverified'}));
      rows.push(row);
    } catch(e) { rows.push({path:path.relative(root,p),error:e.message,preserved:true}); }
  }
  return {schema:version,root,at:new Date().toISOString(),fetch:!!args.fetch,
    manifest_hash:hash(fs.readFileSync(path.join(root,'com-junkawasaki/west-manifest/manifest/west.yml'))),
    summary:{checkouts:rows.length,common_dirs:new Set(rows.filter(r=>r.common).map(r=>r.common)).size,
      dirty:rows.filter(r=>r.files?.length).length,errors:rows.filter(r=>r.error||r.upstream?.error).length},rows};
}
function tree(p,pin) {
  return new Map(git(p,['ls-tree','-r','-z',pin]).out.split('\0').filter(Boolean).map(s=>{
    const [meta,name]=s.split('\t'); const [mode,kind,sha]=meta.split(' ');return [name,{mode,kind,sha}];
  }));
}
function blob(p,f) {
  const q=path.join(p,f); if(!exists(q)) return null;
  const st=fs.lstatSync(q);
  if(st.isSymbolicLink()) return {mode:'120000',sha:git(p,['hash-object','--stdin'],false,fs.readlinkSync(q)).out.trim()};
  if(!st.isFile()) return {directory:true};
  return {mode:st.mode&0o111 ? '100755' : '100644',sha:git(p,['hash-object','--',f]).out.trim()};
}
function syncReason(p,row,project) {
  if(!project) return 'not registered at canonical path';
  if(/datalad|archived/.test(project.groups) || row.upstream?.archived) return 'dataset or archived';
  if(row.shallow) return 'shallow history: explicitly unshallow and re-audit first';
  if(!row.upstream?.tip || row.upstream.error) return 'fresh GitHub/default/PR verification required';
  if(row.stash.length) return 'existing stashes preserved';
  if(git(p,['merge-base','--is-ancestor',row.head,project.revision],true).code) return 'HEAD not ancestor of manifest pin';
  if(git(p,['merge-base','--is-ancestor',project.revision,row.upstream.tip],true).code) return 'pin not on verified default history';
  const target=tree(p,project.revision),old=tree(p,row.head);
  for(const f of row.files) {
    if (/[U]/.test(f.status) || ['AA','DD'].includes(f.status)) return 'unresolved conflict';
    const actual=blob(p,f.path), wanted=target.get(f.path);
    if(actual?.directory) return `directory needs content review: ${f.path}`;
    if(actual ? actual.sha!==wanted?.sha || actual.mode!==wanted?.mode : !!wanted) return `novel WIP: ${f.path}`;
    if(f.old_path && target.has(f.old_path)) return `rename-source deletion not at pin: ${f.old_path}`;
  }
  // Guard ignored files AND ignored descendants before a checkout can replace a directory.
  const statusPaths=new Set(row.files.map(f=>f.path));
  for(const [f,wanted] of target) {
    const actual=blob(p,f);
    if(actual?.directory) return `incoming leaf replaces local directory: ${f}`;
    if(!old.has(f) && !statusPaths.has(f) && actual && (actual.sha!==wanted.sha||actual.mode!==wanted.mode)) return `ignored content collision: ${f}`;
  }
  return null;
}
function activeCwds(root) {
  const r=run('lsof',['-d','cwd','-Fn'],root,true);
  if(r.code !== 0) fail('Cannot verify active process working directories');
  return r.out.split('\n').filter(s=>s.startsWith('n/')).map(s=>{try{return real(s.slice(1));}catch{return s.slice(1);}});
}
const activeAt = (p,active) => active.some(c=>inside(c,p));
export function plan(args) {
  const root=forest(args.root); const source=reportPath(root,args.audit);
  const report=JSON.parse(fs.readFileSync(source));
  if(report.root!==root || report.schema!==version) fail('Audit schema/root mismatch');
  const age=Date.now()-Date.parse(report.at);
  if(!Number.isFinite(age) || age<0 || age>24*60*60*1000) fail('Audit is older than 24 hours; audit again');
  const manifest=projects(root), active=activeCwds(root); const actions=[],held=[];
  for(const row of report.rows) {
    if(row.error){held.push({path:row.path,reason:row.error});continue;}
    const p=repoPath(root,row.path), s=snapshot(p);
    if(s.fingerprint!==row.fingerprint){held.push({path:row.path,reason:'changed since audit'});continue;}
    if(activeAt(p,active)){held.push({path:row.path,reason:'active cwd'});continue;}
    if(!row.slug){held.push({path:row.path,reason:'unknown GitHub identity'});continue;}
    const canonical=path.join(root,row.slug);
    // Rehome only an idle standalone repo. Linked checkout moves need an explicit worktree operation.
    if(p!==canonical && !inside(p,path.join(root,'wt')) && !inside(p,path.join(root,'workspaces'))) {
      const dest=exists(canonical) ? path.join(root,'wt','legacy-'+row.path.split('/')[0],row.path.replaceAll('/','-')) : canonical;
      if(!row.upstream?.slug || row.upstream.error) held.push({path:row.path,reason:'move requires verified current GitHub identity'});
      else if(!fs.lstatSync(path.join(p,'.git')).isDirectory()) held.push({path:row.path,reason:'linked worktree needs Git-native move review'});
      else if(row.worktrees.split('\n').filter(l=>l.startsWith('worktree ')).length>1) held.push({path:row.path,reason:'standalone repo has linked worktrees; repair/dependency review required'});
      else if(exists(dest)) held.push({path:row.path,reason:'move destination occupied'});
      else actions.push({kind:'move',path:row.path,to:path.relative(root,dest),fingerprint:s.fingerprint,slug:row.slug});
      continue;
    }
    const project=manifest.find(x=>x.path===row.path);
    const reason=syncReason(p,row,project);
    if(reason) held.push({path:row.path,kind:'sync',reason});
    else if(row.head!==project.revision || row.files.length) actions.push({kind:'sync',path:row.path,project:project.name,pin:project.revision,fingerprint:s.fingerprint});
    for(const b of row.branches) {
      if(b.classification==='integrated' && !b.checked_out && !b.open_pr &&
          !['main','master','git-annex',row.upstream?.default_branch].includes(b.name) &&
          b.timestamp*1000 < Date.now()-24*60*60*1000)
        actions.push({kind:'retire-branch',path:row.path,branch:b.name,sha:b.sha,tip:row.upstream.tip,fingerprint:s.fingerprint});
    }
  }
  const data={schema:version,root,at:new Date().toISOString(),audit:source,
    audit_hash:hash(fs.readFileSync(source)),manifest_hash:report.manifest_hash,actions,held};
  return {...data,digest:hash(JSON.stringify(data))};
}
function lock(root, fn) {
  const dir=path.join(root,'workspaces','forest-maintenance');fs.mkdirSync(dir,{recursive:true});
  const p=path.join(dir,'apply.lock'); let fd;
  try {fd=fs.openSync(p,'wx',0o600);} catch {fail(`Maintenance lock exists: ${p}; inspect owner, never remove blindly`);}
  fs.writeFileSync(fd,JSON.stringify({pid:process.pid,at:new Date().toISOString()}));
  try{return fn();}finally{fs.closeSync(fd);fs.unlinkSync(p);}
}
export function apply(args) {
  const root=forest(args.root), file=reportPath(root,args.plan);
  const saved=JSON.parse(fs.readFileSync(file)), {digest,...data}=saved;
  if(saved.root!==root||saved.schema!==version||digest!==hash(JSON.stringify(data))) fail('Plan integrity mismatch');
  reportPath(root,saved.audit);
  if(hash(fs.readFileSync(saved.audit))!==saved.audit_hash) fail('Audit changed');
  if(hash(fs.readFileSync(path.join(root,'com-junkawasaki/west-manifest/manifest/west.yml')))!==saved.manifest_hash) fail('Manifest changed; re-audit/re-plan');
  if(Date.now()-Date.parse(saved.at)>24*60*60*1000) fail('Plan expired');
  if(!Array.isArray(args.paths)||!args.paths.length) fail('Apply requires explicit --path selectors');
  const output=reportPath(root,args.out);if(exists(output)) fail('Result path already exists; use a new run path');
  const selected=saved.actions.filter(a=>args.paths.includes(a.path));
  if(!selected.length) fail('No planned actions match selected paths');
  const report=JSON.parse(fs.readFileSync(saved.audit));
  return lock(root,()=>{
    const results=[];const approved=new Map();const manifest=projects(root);
    const runid=crypto.randomUUID();
    for(const a of selected) {
      let r={...a,result:'held'};
      try {
        const p=repoPath(root,a.path);const s=snapshot(p);
        if(activeAt(p,activeCwds(root))) fail('active process cwd');
        if(!approved.has(p)) {
          if(s.fingerprint!==a.fingerprint) fail('HEAD/status/stash/worktrees changed since plan');
          approved.set(p,s.fingerprint);
        } else if(approved.get(p)!==s.fingerprint) fail('concurrent state change');
        const row=report.rows.find(x=>x.path===a.path);
        if(a.kind==='sync') {
          const m=metadata(p,row.upstream.remote);
          if(m.slug!==row.slug || m.archived) fail('GitHub identity/archived status changed');
          git(p,['fetch','--no-tags',m.remote,`refs/heads/${m.default_branch}:refs/audit/forest-maintenance/default`]);
          const tip=git(p,['rev-parse','refs/audit/forest-maintenance/default']).out.trim();
          const project=manifest.find(x=>x.name===a.project&&x.path===a.path&&x.revision===a.pin);
          const shallow=git(p,['rev-parse','--is-shallow-repository']).out.trim()==='true';
          const reason=syncReason(p,{...row,...s,shallow,upstream:{...m,tip}},project); if(reason) fail(reason);
          // All local differing bytes were proved identical to the target above.
          // A new archival ref is created with compare-and-swap before dropping a task stash.
          const ref=`refs/archive/forest-maintenance/${runid}/wip`;
          if(s.files.length) {
            const archive=path.join(s.common,'forest-maintenance',runid);fs.mkdirSync(archive,{recursive:true});
            fs.writeFileSync(path.join(archive,'working.patch'),git(p,['diff','--binary']).out,{mode:0o600});
            fs.writeFileSync(path.join(archive,'index.patch'),git(p,['diff','--cached','--binary']).out,{mode:0o600});
            git(p,['stash','push','--include-untracked','-m',`forest-maintenance ${runid}: already at pin`]);
            const sha=git(p,['rev-parse','refs/stash']).out.trim();r.archive_ref=ref;r.archive_sha=sha;
            git(p,['update-ref',ref,sha,'0'.repeat(40)]);
            writeJSON(output,{runid,results:[...results,{...r,result:'archived-before-update'}]});
          }
          run('west',['update','--fetch','smart',a.project],root);
          if(git(p,['rev-parse','HEAD']).out.trim()!==a.pin||status(p).files.length) fail('Post-update HEAD/status verification failed; archive/task stash preserved');
          if(r.archive_sha && git(p,['rev-parse','refs/stash']).out.trim()===r.archive_sha && git(p,['rev-parse',ref]).out.trim()===r.archive_sha) git(p,['stash','drop','stash@{0}']);
          r.result='synced';
        } else if(a.kind==='retire-branch') {
          // Refresh open PRs at execution; a newly opened PR prevents retirement.
          const m=metadata(p,row.upstream.remote);
          git(p,['fetch','--no-tags',m.remote,`refs/heads/${m.default_branch}:refs/audit/forest-maintenance/default`]);
          const defaultTip=git(p,['rev-parse','refs/audit/forest-maintenance/default']).out.trim();
          const prs=JSON.parse(run('gh',['pr','list','--repo',m.slug,'--state','open','--head',a.branch,'--limit','10000','--json','number'],p).out);
          if(prs.length||a.branch===m.default_branch||s.worktrees.includes(`branch refs/heads/${a.branch}\n`)) fail('Branch checked out/default/open PR');
          if(git(p,['rev-parse',`refs/heads/${a.branch}`]).out.trim()!==a.sha || git(p,['merge-base','--is-ancestor',a.sha,defaultTip],true).code) fail('Branch/ancestry changed');
          const ref=`refs/archive/forest-maintenance/${runid}/heads/${a.branch}`;
          git(p,['update-ref',ref,a.sha,'0'.repeat(40)]);r.archive_ref=ref;
          git(p,['branch','-d','--',a.branch]);r.result='retired';
        } else if(a.kind==='move') {
          const m=metadata(p,row.upstream.remote);if(m.slug!==a.slug) fail('GitHub owner changed');
          const dest=path.resolve(root,a.to);
          if(!inside(dest,root)||exists(dest)) fail('Destination escapes forest or occupied');
          fs.mkdirSync(path.dirname(dest),{recursive:true});
          if(!inside(real(path.dirname(dest)),root)) fail('Destination parent symlink escapes forest');
          fs.renameSync(p,dest);fs.symlinkSync(path.relative(path.dirname(p),dest),p,'dir');
          git(dest,['worktree','repair',dest]);
          const core=git(dest,['config','--get','core.worktree'],true).out.trim();if(core===p) git(dest,['config','core.worktree',dest]);
          const after=snapshot(dest);
          if(after.head!==s.head||JSON.stringify(after.files)!==JSON.stringify(s.files)||JSON.stringify(after.stash)!==JSON.stringify(s.stash)) fail('Move post-verification failed; retained at destination');
          r.result='moved';
        } else fail('Unsupported plan action');
        approved.set(p,snapshot(p).fingerprint);
      } catch(e) {r.reason=e.message;}
      results.push(r);writeJSON(output,{runid,results});
    }
    return {runid,results};
  });
}
export function verify(args={}) {
  const root=forest(args.root);run('west',['manifest','--validate'],root);
  const all=projects(root);const rows=(args.paths?.length ? args.paths : all.map(p=>p.path)).map(p=>{
    try{const location=repoPath(root,p),s=snapshot(location),project=all.find(r=>r.path===p);
      return {path:p,physical:path.relative(root,location),head:s.head,pin:project?.revision,
        at_pin:!!project&&s.head===project.revision,dirty:s.files.length,stashes:s.stash.length};
    }catch(e){return {path:p,error:e.message,preserved:true};}
  });return {root,rows};
}
export function workspace(args) {
  const root=forest(args.root);
  if(!segment(args.agent)||!segment(args.task)) fail('Agent and task must be single safe path segments');
  if(!['scratch','worktree','west'].includes(args.kind)) fail('kind must be scratch, worktree or west');
  const dest=path.join(root,args.kind==='worktree'?'wt':'workspaces',args.kind==='west'?'west':args.agent,args.task);
  if(exists(dest)) fail('Task destination already exists');
  fs.mkdirSync(path.dirname(dest),{recursive:true});
  if(!inside(real(path.dirname(dest)),root)) fail('Task parent escapes forest');
  if(args.kind==='worktree') {
    if(!slugOK(args.repo)||!segment(args.branch)) fail('Canonical repo and safe branch required');
    const repo=repoPath(root,args.repo);const remote=primaryRemote(repo);const m=metadata(repo,remote);
    const ref='refs/audit/forest-maintenance/task-'+crypto.randomUUID();
    git(repo,['fetch','--no-tags',remote,`refs/heads/${m.default_branch}:${ref}`]);
    git(repo,['worktree','add','-b',args.branch,dest,ref]);
  } else {fs.mkdirSync(dest);if(args.kind==='west') {
    fs.mkdirSync(path.join(dest,'.west'));
    fs.writeFileSync(path.join(dest,'.west','config'),'[manifest]\npath = '+path.join(root,'com-junkawasaki/west-manifest')+'\nfile = manifest/west.yml\n');
  }}
  return {path:dest,kind:args.kind};
}
export function pin(args) {
  const root=forest(args.root);if(!segment(args.entry)||!(args.sha==='HEAD'||/^[a-f0-9]{40}$/.test(args.sha))) fail('Entry/SHA invalid');
  const owner=repoPath(root,'com-junkawasaki/west-manifest');
  const argv=['--backend','sci','--classpath','.:scripts:scripts/nbb_compat','scripts/west-pin-put.cljk',args.entry,args.sha];
  if(!args.apply) argv.push('--dry-run');
  return {applied:!!args.apply,log:run('kbb',argv,owner).out};
}
export function register(args) {
  const root=forest(args.root);
  if(!slugOK(args.repo)||!segment(args.entry)) fail('Canonical GitHub repo and entry required');
  const wt=repoPath(root,args.worktree);
  if(!inside(wt,path.join(root,'wt'))) fail('Manifest registration requires a focused task worktree');
  const owner=repoPath(root,'com-junkawasaki/west-manifest');const state=snapshot(wt);
  if(real(state.common)!==real(snapshot(owner).common)||!state.branch||['main','master'].includes(state.branch)) fail('Worktree does not belong to manifest task branch');
  if(state.files.length) fail('Commit existing task changes before registration');
  const workspaceRoot=args.workspace ? repoPath(root,args.workspace) : root;
  if(workspaceRoot!==root && (!inside(workspaceRoot,path.join(root,'workspaces/west')) || !exists(path.join(workspaceRoot,'.west/config')))) fail('Separate west workspace needs its own .west/config');
  const source=path.join(workspaceRoot,args.repo);
  const m=metadata(source,primaryRemote(source));if(m.slug!==args.repo || m.archived) fail('Repository identity/archived status prevents registration');
  const sha=git(source,['rev-parse','HEAD']).out.trim();
  const current=JSON.parse(run('gh',['api',`repos/${m.slug}/compare/${m.default_branch}...${sha}`],wt).out);
  if(!['identical','behind'].includes(current.status)) fail('Checkout HEAD is not on upstream default branch');
  const archive=reportPath(root,args.out);if(exists(archive)) fail('Registration evidence path occupied');
  writeJSON(archive,{repo:args.repo,entry:args.entry,sha,worktree:wt,
    before_repos:fs.readFileSync(path.join(wt,'manifest/repos.edn'),'utf8'),
    before_west:fs.readFileSync(path.join(wt,'manifest/west.yml'),'utf8')});
  const helper=path.join(here,'register-forest-project.cljk');
  run('kbb',['--backend','sci',helper,args.repo],wt);
  // Environment is passed as a child setting; no global state or parent config changes.
  const previous=process.env.WEST_WORKSPACE_ROOT;process.env.WEST_WORKSPACE_ROOT=workspaceRoot;
  try {
    const argv=['--backend','sci','--classpath','.:scripts:scripts/nbb_compat','scripts/gen-west-manifest.cljk'];
    const generated=run('kbb',[...argv,'--entry',args.entry],wt).out;
    const text=fs.readFileSync(path.join(wt,'manifest/west.yml'),'utf8');
    const block=text.split('    - name: '+args.entry+'\n')[1]?.split('\n\n')[0];
    if(!block?.includes('      path: '+args.repo+'\n') || !block?.includes('      revision: '+sha)) fail('Generated entry does not match requested repository/SHA; evidence retained');
    run('kbb',[...argv,'--check'],wt);
    return {repo:args.repo,sha,worktree:wt,evidence:archive,log:generated,requires_commit_pr:true};
  } finally {if(previous===undefined) delete process.env.WEST_WORKSPACE_ROOT;else process.env.WEST_WORKSPACE_ROOT=previous;}
}
const methods={audit,plan,apply,verify,workspace,pin,register};
export function start(args) {
  const root=forest(args.root);
  if(!Object.hasOwn(methods,args.operation)||['start','job_status'].includes(args.operation)) fail('Unsupported job operation');
  const options={...args.options,root};validateArgs(args.operation,options);
  if(!options.out) fail('Background jobs require an explicit result path');
  const output=reportPath(root,options.out);if(exists(output)) fail('Background result path occupied');
  const dir=path.join(root,'workspaces','forest-maintenance','jobs',crypto.randomUUID());fs.mkdirSync(dir,{recursive:true});
  const job=path.join(dir,'job.json'), log=path.join(dir,'stderr.log');
  writeJSON(job,{schema:version,root,operation:args.operation,options,state:'starting',at:new Date().toISOString()});
  const fd=fs.openSync(log,'w',0o600);
  const child=spawn(process.execPath,[fileURLToPath(import.meta.url),'run-job','--root',root,'--job',job],{cwd:root,detached:true,stdio:['ignore','ignore',fd],env:process.env});
  fs.closeSync(fd);child.unref();
  return {job,pid:child.pid,result:output};
}
export function job_status(args) {
  const root=forest(args.root);const file=reportPath(root,args.job),data=JSON.parse(fs.readFileSync(file));
  if(data.root!==root||data.schema!==version) fail('Job root/schema mismatch');
  let alive=false;if(data.pid) {try{process.kill(data.pid,0);alive=true;}catch{}}
  return {job:file,state:data.state,pid:data.pid,alive,operation:data.operation,result:data.options.out,error:data.error,
    interrupted:data.state==='running'&&!alive};
}
Object.assign(methods,{start,job_status});
export function dispatch(method,args={}) {
  if(!Object.hasOwn(methods,method)) fail('Unknown forest operation');
  return methods[method](args);
}
const toolSchemas={
  audit:{paths:{type:'array',items:{type:'string'}},fetch:{type:'boolean'}},
  plan:{audit:{type:'string'}},
  apply:{plan:{type:'string'},paths:{type:'array',items:{type:'string'},minItems:1},out:{type:'string'}},
  verify:{paths:{type:'array',items:{type:'string'}}},
  workspace:{agent:{type:'string'},task:{type:'string'},kind:{enum:['scratch','worktree','west']},repo:{type:'string'},branch:{type:'string'}},
  pin:{entry:{type:'string'},sha:{type:'string'},apply:{type:'boolean'}},
  register:{repo:{type:'string'},entry:{type:'string'},worktree:{type:'string'},workspace:{type:'string'},out:{type:'string'}},
  start:{operation:{enum:['audit','plan','apply','verify','workspace','pin','register']},options:{type:'object'}},
  job_status:{job:{type:'string'}}
};
const required={plan:['audit'],apply:['plan','paths','out'],workspace:['agent','task','kind'],pin:['entry','sha'],register:['repo','entry','worktree','out'],start:['operation','options'],job_status:['job']};
function validateArgs(name,args) {
  if(!args || Array.isArray(args) || typeof args!=='object') fail('Arguments must be an object');
  const schemas={root:{type:'string'},out:{type:'string'},...toolSchemas[name]};
  for(const [key,value] of Object.entries(args)) {
    const schema=schemas[key];if(!schema) fail('Unknown argument: '+key);
    if(schema.type==='array') {if(!Array.isArray(value)||value.some(v=>typeof v!=='string')) fail('Expected string array: '+key);}
    else if(schema.type && (typeof value!==schema.type || (schema.type==='object'&&(!value||Array.isArray(value))))) fail('Wrong argument type: '+key);
    if(schema.enum&&!schema.enum.includes(value)) fail('Invalid value: '+key);
  }
  for(const key of required[name]||[]) if(args[key]===undefined) fail('Missing argument: '+key);
}
const descriptions={audit:'Inventory valid and broken checkouts, WIP, stashes, all branches. fetch=true verifies current GitHub ownership/default/PRs.',
  plan:'Produce a digest-protected maintenance plan and explicit hold reasons from an audit JSON file.',
  apply:'Apply selected repository paths only; recheck state, preserve WIP in archival refs, journal results. Requires authorization for selected mutations.',
  verify:'Validate west and report actual HEAD, pin, dirtiness and missing paths without changing checkouts.',
  workspace:'Create a correctly placed task scratch/worktree/separate west workspace.',
  pin:'Verify a single server-side manifest pin advance. Dry run unless apply=true; does not update local checkouts.',
  register:'Register an existing owning repository on a clean focused manifest branch; preserve before files, verify pin on GitHub default, generate named entry. Does not merge or update canonical owner checkout.',
  start:'Run an authorized forest operation as a persisted background job; use for large fleet audits/selected updates exceeding client timeouts. Requires operation-specific arguments and result path.',
  job_status:'Read persisted job state/result/error. An interrupted job is not success; inspect journal and re-audit before resuming mutations.'};
export async function serve() {
  const input=readline.createInterface({input:process.stdin,crlfDelay:Infinity});let initialized=false;
  for await(const line of input) {
    let msg;
    try{msg=JSON.parse(line);}catch{process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:null,error:{code:-32700,message:'Parse error'}})+'\n');continue;}
    if(msg.id===undefined) continue;
    let reply;
    try {
      if(msg.method==='initialize') { initialized=true;reply={protocolVersion:['2025-11-25','2025-06-18','2025-03-26','2024-11-05'].includes(msg.params?.protocolVersion)?msg.params.protocolVersion:'2025-11-25',capabilities:{tools:{}},serverInfo:{name:'github-forest-maintenance',version:'1.0.0'}}; }
      else if(msg.method==='ping') reply={};
      else if(!initialized) throw Object.assign(new Error('Initialize first'),{rpcCode:-32002});
      else if(msg.method==='tools/list') reply={tools:Object.keys(methods).map(name=>({name:'forest_'+name,description:descriptions[name],inputSchema:{type:'object',properties:{root:{type:'string'},out:{type:'string'},...toolSchemas[name]},required:required[name]||[],additionalProperties:false},annotations:{readOnlyHint:['verify','plan','job_status'].includes(name),destructiveHint:false,openWorldHint:['audit','pin','workspace'].includes(name)}}))};
      else if(msg.method==='tools/call') {
        const name=msg.params?.name?.replace(/^forest_/,''); const args=msg.params?.arguments||{};
        try {
          if(!Object.hasOwn(toolSchemas,name)) fail('Unknown tool');
          validateArgs(name,args);
          const data=dispatch(name,args);
          if(args.out && !['apply','register'].includes(name)) writeJSON(reportPath(forest(args.root),args.out),data);
          reply={content:[{type:'text',text:JSON.stringify(args.out?{report:args.out,summary:data.summary||{actions:data.actions?.length,held:data.held?.length}}:data)}],isError:false};
        }catch(e){reply={content:[{type:'text',text:e.message}],isError:true};}
      } else throw Object.assign(new Error('Method not found'),{rpcCode:-32601});
      process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:msg.id,result:reply})+'\n');
    }catch(e){process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:msg.id,error:{code:e.rpcCode||-32603,message:e.message}})+'\n');}
  }
}
function main() {
  const [command,...argv]=process.argv.slice(2);
  if(command==='mcp') return serve();
  if(command==='run-job') {
    const root=forest(argv[1]);const file=reportPath(root,argv[3]);const data=JSON.parse(fs.readFileSync(file));
    if(argv[0]!=='--root'||argv[2]!=='--job'||data.root!==root||data.state!=='starting') fail('Invalid job invocation');
    writeJSON(file,{...data,state:'running',pid:process.pid});
    try{const result=dispatch(data.operation,data.options);
      if(!['apply','register'].includes(data.operation)) writeJSON(reportPath(root,data.options.out),result);
      writeJSON(file,{...data,state:'complete',pid:process.pid,finished:new Date().toISOString()});
    }catch(e){writeJSON(file,{...data,state:'failed',pid:process.pid,error:e.message,finished:new Date().toISOString()});process.exitCode=1;}
    return;
  }
  if(!command||command==='--help') {
    console.log('forest-maintenance audit|plan|apply|verify|workspace|pin|register|start|job_status|mcp\nOptions: --root PATH --path ORG/REPO (repeat) --out workspaces/...json\naudit --fetch; plan --audit FILE; apply --plan FILE --path ORG/REPO --out FILE\nworkspace --kind scratch|worktree|west --agent AGENT --task TASK [--repo ORG/REPO --branch NAME]\npin --entry NAME --sha HEAD|SHA [--apply]\nregister --repo ORG/REPO --entry NAME --worktree wt/AGENT/TASK --out FILE [--workspace workspaces/west/TASK]\nstart --operation NAME --options JSON_FILE; job_status --job JOB_FILE');return;
  }
  const args={};const flags=new Set(['fetch','apply']);const keys=new Set(['root','path','out','audit','plan','kind','agent','task','repo','branch','entry','sha','worktree','workspace','job','operation','options']);
  for(let i=0;i<argv.length;i++) {
    const k=argv[i].replace(/^--/,'');if(argv[i]===k||(!flags.has(k)&&!keys.has(k))) fail('Unknown option '+argv[i]);
    if(flags.has(k)) {args[k]=true;continue;}
    const value=argv[++i];if(!value||value.startsWith('--')) fail('Missing option value');
    if(k==='path') (args.paths??=[]).push(value);else args[k]=value;
  }
  if(command==='start' && typeof args.options==='string') args.options=JSON.parse(fs.readFileSync(reportPath(forest(args.root),args.options)));
  const result=dispatch(command,args);
  if(args.out&&!['apply','register'].includes(command)) writeJSON(reportPath(forest(args.root),args.out),result);
  console.log(JSON.stringify(args.out?{report:args.out,summary:result.summary||{actions:result.actions?.length,held:result.held?.length}}:result,null,2));
}
if(process.argv[1]&&real(process.argv[1])===fileURLToPath(import.meta.url)) Promise.resolve().then(main).catch(e=>{console.error(e.message);process.exitCode=1;});
