"""Compile byte-identical .cljk views and run local Miniflare R2 fixtures.

Requires npm ci --ignore-scripts, Java, Clojure and Node. Set
KOTOBA_TEST_WORKSPACE to an absolute github/workspaces directory locally,
or use RUNNER_TEMP in CI. This does not compile Amu/Wasm or use live R2.
"""
from pathlib import Path
import hashlib, json, os, re, subprocess, sys, tempfile

project=Path(__file__).resolve().parent.parent
workspace=Path(os.environ.get('KOTOBA_TEST_WORKSPACE',os.environ.get('RUNNER_TEMP',''))).resolve()
ci_temp=Path(os.environ['RUNNER_TEMP']).resolve() if os.environ.get('RUNNER_TEMP') else None
assert '/github/workspaces/' in str(workspace) or (
    os.environ.get('GITHUB_ACTIONS')=='true' and ci_temp and workspace.is_relative_to(ci_temp)), 'set KOTOBA_TEST_WORKSPACE'
workspace.mkdir(parents=True,exist_ok=True)
work=Path(tempfile.mkdtemp(prefix='s3-compiled-',dir=workspace))
builds=sys.argv[1:] or ['engine-r2','prolly-engine-r2','advanced-r2']
assert builds and len(set(builds))==len(builds) and set(builds)<= {'engine-r2','prolly-engine-r2','advanced-r2'}

def run(command,label,cwd=work,timeout=360):
    p=subprocess.run(command,cwd=cwd,text=True,capture_output=True,timeout=timeout)
    (work/(label+'.log')).write_text(p.stdout+p.stderr)
    assert p.returncode==0,(label,p.returncode,p.stdout[-2000:],p.stderr[-3000:])
    return p.stdout

cp=run(['clojure','-Srepro','-Spath','-M:engine-test:prolly-engine-test'],'resolve',project).strip().split(os.pathsep)
views=[];jars=[];mapping=[]
for index,name in enumerate(cp):
    source=(project/name).resolve()
    if source.is_file():jars.append(str(source));continue
    assert source.is_dir(),source
    root=next((p for p in [source,*list(source.parents)[:4]] if (p/'cljk-origin.edn').is_file()),None)
    origins=dict(re.findall(r'"([^\"]+\.cljk)"\s+"(\.clj[sc]?)"',(root/'cljk-origin.edn').read_text())) if root else {}
    destination=work/'sources'/str(index);destination.mkdir(parents=True)
    for file in source.rglob('*'):
        relative=file.relative_to(source)
        if any(v in {'.git','node_modules','target','.cpcache','.shadow-cljs','.cache'} for v in relative.parts):continue
        if not file.is_file():continue
        name=relative.as_posix()
        if name.endswith('.cljk'):
            extension=origins.get(file.relative_to(root).as_posix(),'.cljc') if root and file.is_relative_to(root) else '.cljc'
            name=name[:-5] if name.endswith(('.clj.cljk','.cljs.cljk','.cljc.cljk')) else name[:-5]+extension
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);data=file.read_bytes()
        assert not target.exists() or target.read_bytes()==data,('source view collision',target)
        target.write_bytes(data);mapping.append({'source':str(file),'view':str(target.relative_to(work)),'sha256':hashlib.sha256(data).hexdigest()})
    views.append(str(destination))
(work/'source-mapping.json').write_text(json.dumps(mapping,indent=2)+'\n')
assert (project/'node_modules').is_dir(),'run npm ci --ignore-scripts first'
(work/'node_modules').symlink_to(project/'node_modules',target_is_directory=True)
(work/'package.json').write_text('{"private":true,"type":"commonjs"}\n')
configuration=(project/'shadow-cljs.edn').read_text()
old='{:deps {:aliases [:engine-test :prolly-engine-test]}'
assert configuration.count(old)==1
(work/'shadow-cljs.edn').write_text(configuration.replace(old,'{:deps false :source-paths '+json.dumps(views)))
run(['java','-Xmx1600m','-cp',os.pathsep.join([*views,*jars]),'clojure.main','-m','shadow.cljs.devtools.cli','compile',*builds],'compile')
results=[]
for build in builds:
    output=run(['node','out/'+build+'.js'],build,timeout=180)
    assert 'all green' in output and 'FAIL' not in output,(build,'runner did not verify completion')
    print(output.strip(),flush=True);results.append({'build':build,'exit':0})
(work/'results.json').write_text(json.dumps({'host':'compiled-CLJS-Node','fixture':'local Miniflare R2','results':results},indent=2)+'\n')
print('Evidence:',work)
