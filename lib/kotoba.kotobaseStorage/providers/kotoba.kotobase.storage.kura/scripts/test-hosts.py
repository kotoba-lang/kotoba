"""Run the actual JVM and compiled-CLJS suites from byte-identical source views.

The views adapt .cljk filenames for the compatibility compilers, not source
forms. Amu/native qualification is a separate gate. No live Kura service is used.
"""
from pathlib import Path
import hashlib, json, os, re, subprocess, sys, tempfile

project=Path(__file__).resolve().parent.parent
assert len(sys.argv)==2, 'usage: python3 scripts/test-hosts.py /absolute/github/workspaces/kura-tests'
workspace=Path(sys.argv[1]).resolve()
ci_temp=Path(os.environ['RUNNER_TEMP']).resolve() if os.environ.get('RUNNER_TEMP') else None
assert '/github/workspaces/' in str(workspace) or (
    os.environ.get('GITHUB_ACTIONS')=='true' and ci_temp and workspace.is_relative_to(ci_temp))
workspace.mkdir(parents=True,exist_ok=True)
work=Path(tempfile.mkdtemp(prefix='kura-host-tests-',dir=workspace))

def run(command,label,cwd=work):
    p=subprocess.run(command,cwd=cwd,text=True,capture_output=True,timeout=240)
    (work/(label+'.log')).write_text(p.stdout+p.stderr)
    assert p.returncode==0,(label,p.returncode,p.stderr[-3000:],p.stdout[-2000:])
    return p.stdout

cp=run(['clojure','-Srepro','-Spath','-M:cljs'],'resolve',project).strip().split(os.pathsep)
staged=[];mapping=[];project_views=[]
for index,name in enumerate(cp):
    source=(project/name).resolve()
    if source.is_file():
        staged.append(str(source));continue
    assert source.is_dir(),source
    destination=work/'sources'/str(index);destination.mkdir(parents=True)
    if source in {project/'src',project/'test'}:project_views.append(str(destination))
    for file in source.rglob('*'):
        relative=file.relative_to(source)
        if any(part in {'.git','node_modules','target','.cpcache','.shadow-cljs'} for part in relative.parts):continue
        if not file.is_file() or file.suffix not in {'.cljk','.cljs','.cljc','.clj','.edn','.json','.txt'}:continue
        name=relative.as_posix()
        if name.endswith('.cljk'):
            # This newly authored namespace is Worker/Node only. Its host view
            # is .cljs, while the older portable namespace stays .cljc.
            if file==project/'src/kotobase/storage/kura/async.cljk':name=name[:-5]+'.cljs'
            else:name=name[:-5] if name.endswith(('.clj.cljk','.cljs.cljk','.cljc.cljk')) else name[:-5]+'.cljc'
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
        data=file.read_bytes()
        assert not target.exists() or target.read_bytes()==data,('source-view collision',file,target)
        target.write_bytes(data)
        mapping.append({'source':str(file),'view':str(target.relative_to(work)),'sha256':hashlib.sha256(data).hexdigest()})
    staged.append(str(destination))
(work/'source-mapping.json').write_text(json.dumps(mapping,indent=2)+'\n')
classpath=os.pathsep.join(staged)
suites=[]
for file in sorted((project/'test').rglob('*_test.*')):
    if file.suffix not in {'.cljk','.cljs','.cljc','.clj'}:continue
    match=re.search(r'\(ns\s+([^\s()]+)',file.read_text());assert match
    suites.append((match[1],file.suffix))
assert suites
jvm=[name for name,extension in suites if extension!='.cljs']
runner=work/'jvm.clj'
runner.write_text("(require '[clojure.test :as t] "+' '.join("'"+n for n in jvm)+")\n(let [r (t/run-tests "+' '.join("'"+n for n in jvm)+")] (System/exit (if (and (pos? (:test r)) (t/successful? r)) 0 1)))\n")
result=run(['java','-Xmx768m','-cp',classpath,'clojure.main',str(runner)],'JVM')
assert all('Testing '+name in result for name in jvm)
print(result.strip(),flush=True)

build=work/'compiled';build.mkdir();(build/'package.json').write_text('{"type":"commonjs"}\n')
run(['java','-Xmx1200m','-cp',classpath,'clojure.main','-m','cljs.main','--target','node',
     '--output-dir','compiled/out','--output-to','compiled/tests.cjs','-c','kotobase.storage.cljs-runner'],'compile')
result=run(['node',str(build/'tests.cjs')],'compiled-CLJS')
assert all('Testing '+name in result for name,_ in suites),'a test namespace was required but never executed'
assert re.search(r'Ran [1-9]\d* tests containing [1-9]\d* assertions\.\s+0 failures, 0 errors\.',result)
print(result.strip(),flush=True)
print('Evidence:',work)
lint_cp=run(['clojure','-Srepro','-Spath','-M:lint'],'lint-resolve',project).strip()
result=run(['java','-cp',lint_cp,'clojure.main','-m','clj-kondo.main','--lint',*project_views,
            '--fail-level','error'],'lint',project)
print(result.strip(),flush=True)
