#!/usr/bin/env python3
"""Install only this forest MCP/skill using client CLIs and Hermes' native YAML writer.
Run with the installed Hermes Python environment; dry-run is the default.
Secrets and complete config backups never enter project reports.
"""
import argparse, copy, datetime, json, os, pathlib, shutil, subprocess, sys, tomllib

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--root',default='/Users/junkawasaki/github')
    parser.add_argument('--hermes-package',default=str((pathlib.Path.home()/'.hermes/hermes-agent').resolve()))
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    root=pathlib.Path(args.root).resolve(); owner=root/'com-junkawasaki/west-manifest'
    script=owner/'scripts/forest-maintenance.mjs'; skill=owner/'skills/github-forest-maintenance'
    if not script.is_file() or not (skill/'SKILL.md').is_file():raise RuntimeError('Canonical merged tools/skill must exist first')
    out=pathlib.Path(args.out).resolve()
    if not out.is_relative_to(root/'workspaces'):raise RuntimeError('Receipt must be in github/workspaces')
    if out.exists():raise RuntimeError('Receipt already exists')
    sys.path.insert(0,str(pathlib.Path(args.hermes_package).resolve()))
    import yaml
    from hermes_cli.config import atomic_config_write
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    home=pathlib.Path.home();name='github-forest';node=shutil.which('node')
    if not node:raise RuntimeError('Node missing')
    entry={'command':node,'args':[str(script),'mcp']};results=[]
    def save_receipt():
        out.parent.mkdir(parents=True,exist_ok=True)
        temp=out.with_suffix('.tmp');temp.write_text(json.dumps({'applied':args.apply,'results':results},indent=2)+'\n');temp.chmod(0o600);temp.replace(out)
    def backup(p,app):
        base=home/app/'backups'/('forest-maintenance-'+stamp)
        relative=p.relative_to(home/app) if p.is_relative_to(home/app) else pathlib.Path(p.name)
        dest=base/relative;dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(p.read_bytes())
        return str(dest)
    def command(argv):
        r=subprocess.run(argv,cwd=owner,capture_output=True,text=True,timeout=120)
        if r.returncode:raise RuntimeError('Client registration failed: '+r.stderr[:300])
    # Native client config writers preserve the rest of the settings.
    codex=home/'.codex/config.toml';claude=home/'.claude.json'
    for kind,p,settings,argv,app in [
        ('codex',codex,tomllib.loads(codex.read_text()).get('mcp_servers',{}),['codex','mcp','add',name,'--',node,str(script),'mcp'],'.codex'),
        ('claude',claude,json.loads(claude.read_text()).get('mcpServers',{}),['claude','mcp','add','--scope','user',name,'--',node,str(script),'mcp'],'.claude')]:
        old=settings.get(name);r={'client':kind,'path':str(p)}
        if old and (old.get('command')!=node or old.get('args')!=entry['args']):r['result']='held-existing-different-entry'
        elif old:r['result']='already-configured'
        elif args.apply:r['backup']=backup(p,app);command(argv);r['result']='configured'
        else:r['result']='would-configure'
        results.append(r);save_receipt()
    # Each bot profile owns its own raw config; do not serialize expanded credentials.
    hermes=home/'.hermes'
    configs=[hermes/'config.yaml',*sorted((hermes/'profiles').glob('*/config.yaml'))]
    lazy={**entry,'lazy':True}
    for p in configs:
        raw=yaml.safe_load(p.read_text()) or {};before=copy.deepcopy(raw);servers=raw.get('mcp_servers') or {}
        if not isinstance(servers,dict):results.append({'client':'hermes','path':str(p),'result':'held-invalid-mcp-map'});continue
        old=servers.get(name);r={'client':'hermes','path':str(p)}
        if old and old!=lazy:r['result']='held-existing-different-entry'
        elif old:r['result']='already-configured'
        elif args.apply:
            r['backup']=backup(p,'.hermes');servers[name]=lazy;raw['mcp_servers']=servers
            # The app's own comment-preserving atomic writer. Refuses corrupt config.
            atomic_config_write(p,raw)
            after=yaml.safe_load(p.read_text());assert after['mcp_servers'][name]==lazy
            after['mcp_servers'].pop(name)
            if not before.get('mcp_servers'):
                if 'mcp_servers' not in before:after.pop('mcp_servers')
                else:after['mcp_servers']=before['mcp_servers']
            assert after==before,'Unrelated Hermes raw settings changed'
            r['result']='configured'
        else:r['result']='would-configure'
        results.append(r)
    destinations=[home/'.codex/skills'/skill.name,home/'.claude/skills'/skill.name,hermes/'skills'/skill.name]
    destinations += [p.parent/'skills'/skill.name for p in configs if p.parent!=hermes]
    for p in destinations:
        r={'client':'skill','path':str(p)}
        if p.is_symlink() and p.resolve()==skill:r['result']='already-linked'
        elif p.exists() or p.is_symlink():r['result']='held-existing-skill'
        elif args.apply:p.parent.mkdir(parents=True,exist_ok=True,mode=0o700);p.symlink_to(skill,target_is_directory=True);r['result']='linked'
        else:r['result']='would-link'
        results.append(r)
    localbin=home/'.local/bin';cli=localbin/'forest-maintenance'
    if cli.is_symlink() and cli.resolve()==script:result='already-linked'
    elif cli.exists() or cli.is_symlink():result='held-existing-command'
    elif args.apply:localbin.mkdir(parents=True,exist_ok=True);cli.symlink_to(script);result='linked'
    else:result='would-link'
    results.append({'client':'command','path':str(cli),'result':result});save_receipt()
    from collections import Counter
    print(json.dumps({'applied':args.apply,'hermes_configs':len(configs),'results':dict(Counter(r['result'] for r in results)),'receipt':str(out)}))

if __name__=='__main__':main()
