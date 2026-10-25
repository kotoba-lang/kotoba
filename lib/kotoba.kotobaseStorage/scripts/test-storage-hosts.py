"""Reproduce owner/provider host tests and source-origin checks without live services.

Requires Java, Clojure, Node and the pinned Kotoba CLI/SCI engine checkouts.
Install the IPFS and S3 npm locks with --ignore-scripts first. Compiled CLJS
uses byte-identical filename views; JVM, SCI, compiled CLJS and native gates
remain distinct. No deployment, live database, Kubo or Helia node is started.
"""
from pathlib import Path
import argparse, json, os, re, subprocess, tempfile

parser=argparse.ArgumentParser()
parser.add_argument('workspace',type=Path)
parser.add_argument('--kotoba',type=Path,required=True)
parser.add_argument('--engine',type=Path,required=True)
args=parser.parse_args()
owner=Path(__file__).resolve().parent.parent
workspace=args.workspace.resolve();kotoba=args.kotoba.resolve();engine=args.engine.resolve()
ci_temp=Path(os.environ['RUNNER_TEMP']).resolve() if os.environ.get('RUNNER_TEMP') else None
assert '/github/workspaces/' in str(workspace) or (
    os.environ.get('GITHUB_ACTIONS')=='true' and ci_temp and workspace.is_relative_to(ci_temp))
assert (kotoba/'bin/kbb').is_file() and engine.is_file()
workspace.mkdir(parents=True,exist_ok=True)
work=Path(tempfile.mkdtemp(prefix='storage-hosts-',dir=workspace))
env={**os.environ,'KBB_HOME':str(kotoba),'KBB_ENGINE':str(engine),
     'KBB_NO_STDLIB':'1','KBB_NO_NPM':'1','KOTOBA_TEST_WORKSPACE':str(workspace)}
results={'JVM':[],'SCI':[],'origins':[],'compiled':[]}
(work/'environment.json').write_text(json.dumps({'kotoba':str(kotoba),'engine':str(engine),'owner':str(owner)},indent=2)+'\n')

def run(command,label,project=owner,timeout=360):
    p=subprocess.run([str(c) for c in command],cwd=project,env=env,text=True,capture_output=True,timeout=timeout)
    (work/(label+'.log')).write_text(p.stdout+p.stderr)
    assert p.returncode==0,(label,p.returncode,p.stdout[-2500:],p.stderr[-2500:])
    return p.stdout

catalog=json.loads((owner/'providers/catalog.json').read_text())
for row in [{'id':'owner','path':'.'},*catalog['packages']]:
    project=owner/row['path'];name=row['id'];suites=[]
    origin=(project/'cljk-origin.edn').read_text() if (project/'cljk-origin.edn').is_file() else ''
    for file in sorted((project/'test').rglob('*_test.cljk')):
        extension=re.search(re.escape('"'+file.relative_to(project).as_posix()+'"')+r'\s+"([^\"]+)"',origin)
        if extension and extension[1]=='.cljs':continue
        ns=re.search(r'\(ns\s+([^\s()]+)',file.read_text());assert ns
        suites.append(ns[1])
    if not suites:continue
    cp=run(['clojure','-Srepro','-Spath','-M:test'],name+'-JVM-resolve',project).strip()
    runner=work/(name+'-JVM.clj')
    runner.write_text("(require '[clojure.test :as t] "+' '.join("'"+n for n in suites)+")\n(let [r (t/run-tests "+' '.join("'"+n for n in suites)+")] (System/exit (if (and (pos? (:test r)) (t/successful? r)) 0 1)))\n")
    output=run(['java','-Xmx768m','-cp',cp,'clojure.main','-i',kotoba/'tools/cljk_loader.cljk',runner],name+'-JVM',project)
    match=re.search(r'Ran (\d+) tests containing (\d+) assertions\.\s+0 failures, 0 errors\.',output);assert match and all('Testing '+n in output for n in suites)
    results['JVM'].append({'id':name,'tests':int(match[1]),'assertions':int(match[2]),'exit':0})
    if name!='owner':
        namespace='kotobase.storage.'+name.rsplit('.',1)[1]
        resource=namespace.replace('.','/').replace('-','_')+'.cljk'
        expression=f"(require '{namespace}) (let [u (str (clojure.java.io/resource {json.dumps(resource)})) expected (str (.toURL (.toURI (clojure.java.io/file {json.dumps(str(project/'src'/resource))}))))] (assert (= u expected)) (println u))"
        output=run(['java','-cp',cp,'clojure.main','-i',kotoba/'tools/cljk_loader.cljk','-e',expression],name+'-JVM-origin',project)
        results['origins'].append({'id':name,'host':'JVM','source':output.strip()})

requests=[('owner','.',':cljs-test',['test/run.cljk','test/object_run.cljk']),
 ('ipfs','providers/kotoba.kotobase.storage.ipfs',':cljs-test',['test/run.cljk','test/ipfs_kubo_test.cljk','test/ipfs_kotobase_test.cljk','test/ipfs_native_test.cljk','test/ipfs_helia_test.cljk']),
 ('s3','providers/kotoba.kotobase.storage.s3',':cljs-test',['test/run.cljk','test/object_run.cljk','test/r2.cljk','test/object_r2.cljk','test/r2_live_bench_driver.cljk','test/r2_live_worker_guards.cljk']),
 ('pack','providers/kotoba.kotobase.storage.pack',':test',['test/async_run.cljk'])]
for name,relative,alias,scripts in requests:
    project=owner/relative
    cp=run([kotoba/'bin/kbb','-Spath','-M'+alias],name+'-SCI-resolve',project).strip()
    cp=os.pathsep.join(str((project/p).resolve()) for p in cp.split(os.pathsep) if p)+os.pathsep+str(project/'test')
    for script in scripts:
        assert (project/script).is_file()
        run([kotoba/'bin/kbb','--backend','sci','--classpath',cp,script],name+'-SCI-'+Path(script).stem,project)
        results['SCI'].append({'id':name,'script':script,'exit':0})
    if name in {'ipfs','s3'}:
        namespace='kotobase.storage.'+name
        expected=str((project/'src').resolve())
        expression=f"(require '[{namespace} :as p]) (let [f (:file (meta #'p/open))] (assert (and (string? f) (.startsWith f {json.dumps(expected)}))) (println f))"
        output=run([kotoba/'bin/kbb','--backend','sci','--classpath',cp,'-e',expression],name+'-public-CLI-origin',project)
        results['origins'].append({'id':'kotoba.kotobase.storage.'+name,'host':'public Kotoba CLI / SCI','source':output.strip()})

assert len({r['id'] for r in results['origins']})==7
output=run(['python3','scripts/test-hosts.py',workspace],'kura-compiled',owner/'providers/kotoba.kotobase.storage.kura',timeout=600)
counts=re.findall(r'Ran (\d+) tests containing (\d+) assertions\.',output);assert len(counts)==2 and 'errors: 0, warnings: 0' in output
results['compiled'].append({'id':'kura','tests':int(counts[-1][0]),'assertions':int(counts[-1][1]),'exit':0})
run(['python3','scripts/test-compiled.py'],'s3-compiled',owner/'providers/kotoba.kotobase.storage.s3',timeout=600)
results['compiled'].append({'id':'s3','builds':['engine-r2','prolly-engine-r2','advanced-r2'],'exit':0})
(work/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2));print('Evidence:',work)
