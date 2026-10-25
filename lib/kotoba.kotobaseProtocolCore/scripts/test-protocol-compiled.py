"""Run real compiled Node tests from source-byte-identical extension views.

The optional planted failure proves reporter/exit behavior using a recorded
view overlay only; production sources and checked-in tests remain untouched.
No native or live-service qualification is implied.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,tempfile

owner=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser()
parser.add_argument('workspace',type=Path)
parser.add_argument('--project',choices=['owner','ipq','query-surfaces','lfs'],required=True)
parser.add_argument('--plant-failure',action='store_true')
args=parser.parse_args();out=args.workspace.resolve()
ci_temp=Path(os.environ['RUNNER_TEMP']).resolve() if os.environ.get('RUNNER_TEMP') else None
assert '/github/workspaces/' in str(out) or (os.environ.get('GITHUB_ACTIONS')=='true' and ci_temp and out.is_relative_to(ci_temp))
out.mkdir(parents=True,exist_ok=True)
matrix=json.loads((owner/'maintenance/protocol-test-hosts.json').read_text())['projects']
name=args.project
relative={'.':'owner',**{r['path']:r['path'].rsplit('.',1)[-1] for r in matrix if r['path']!='.'}}
row=next(r for r in matrix if relative[r['path']]==name)
project=(owner/row['path']).resolve()
work=Path(tempfile.mkdtemp(prefix=name+'-compiled-',dir=out))
(work/'tmp').mkdir()
env={**os.environ,'TMPDIR':str(work/'tmp'),'KOTOBA_IPQ_FS_CACHE':str(work/'ipq-cache')}

def run(command,label,timeout=360,expect_failure=False):
    p=subprocess.run(command,cwd=project if label.startswith('resolve') else work,text=True,capture_output=True,timeout=timeout,env=env)
    (work/(label+'.log')).write_text(p.stdout+p.stderr)
    assert p.returncode==(1 if expect_failure else 0),(label,p.returncode,p.stdout[-2500:],p.stderr[-2500:])
    return p.stdout

extra='{:deps {org.clojure/clojurescript {:mvn/version "1.11.132"} io.github.kotoba-lang/kotoba-test-cljs {:git/url "https://github.com/kotoba-lang/kotoba.git" :git/sha "f0ecb24b722664b825ab89992e9cc98c37ecaaf0" :deps/root "lib/kotoba.test/compiled"}}}'
cp=run(['clojure','-Srepro','-Sdeps',extra,'-Spath','-M:test'],'resolve').strip().split(os.pathsep)
views=[];jars=[];mapping=[];local_views=[]
for index,name in enumerate(cp):
    source=(project/name).resolve()
    if source.is_file():jars.append(str(source));continue
    assert source.is_dir(),source
    root=next((p for p in [source,*list(source.parents)[:4]] if (p/'cljk-origin.edn').is_file()),None)
    origins=dict(re.findall(r'"([^\"]+\.cljk)"\s+"(\.clj[sc]?)"',(root/'cljk-origin.edn').read_text())) if root else {}
    destination=work/'sources'/str(index);destination.mkdir(parents=True)
    if source in {project/'src',project/'test'}:local_views.append(str(destination))
    for file in source.rglob('*'):
        relative=file.relative_to(source)
        if any(v in {'.git','node_modules','target','.cpcache','.shadow-cljs','.cache'} for v in relative.parts):continue
        if not file.is_file():continue
        target_name=relative.as_posix()
        if target_name.endswith('.cljk'):
            extension=origins.get(file.relative_to(root).as_posix(),'.cljc') if root and file.is_relative_to(root) else '.cljc'
            if file.is_relative_to(project) and file.relative_to(project).as_posix() in row.get('host-extension-overrides',{}):
                key=file.relative_to(project).as_posix();assert not origins.get(key),'review conflicting original host annotation'
                extension=row['host-extension-overrides'][key]
            target_name=target_name[:-5] if target_name.endswith(('.clj.cljk','.cljs.cljk','.cljc.cljk')) else target_name[:-5]+extension
        target=destination/target_name;target.parent.mkdir(parents=True,exist_ok=True);data=file.read_bytes()
        assert not target.exists() or target.read_bytes()==data,('source-view collision',file,target)
        target.write_bytes(data);mapping.append({'source':str(file),'view':str(target.relative_to(work)),'sha256':hashlib.sha256(data).hexdigest()})
    views.append(str(destination))
(work/'source-mapping.json').write_text(json.dumps(mapping,indent=2)+'\n')
modules=project/'node_modules' if (project/'node_modules').is_dir() else owner/'node_modules'
if modules.is_dir():(work/'node_modules').symlink_to(modules,target_is_directory=True)
(work/'package.json').write_text('{"private":true,"type":"commonjs"}\n')
tests=[r['namespace'] for r in row['tests'] if r['compiled-CLJS']]
if tests:
    runner=work/'runner';runner.mkdir();views.insert(0,str(runner))
    (runner/'kotobase/protocols').mkdir(parents=True)
    (runner/'kotobase/protocols/gate_runner.cljs').write_text('''(ns kotobase.protocols.gate-runner
  (:require [cljs.test :as t :include-macros true]
'''+''.join('            ['+n+']\n' for n in tests)+'''))
(def ended? (atom false))
(defmethod t/report [::t/default :end-run-tests] [m]
  (reset! ended? true)
  (println "qualified-summary" (pr-str (select-keys m [:test :pass :fail :error])))
  (set! (.-exitCode js/process) (if (and (pos? (:test m)) (t/successful? m)) 0 1)))
(.on js/process "beforeExit" (fn [] (when-not @ended? (set! (.-exitCode js/process) 1))))
(t/run-tests '''+' '.join("'"+n for n in tests)+')\n')
    namespace='kotobase.protocols.gate-runner'
else:namespace='run'
if args.plant_failure:
    assert tests and args.project=='owner','negative control belongs to the portable owner suites'
    selected=row['tests'][0]['path']
    entry=next(r for r in mapping if r['source']==str(project/selected))
    view=work/entry['view'];before=view.read_bytes()
    view.write_bytes(before+b'\n(deftest planted-failure (is false))\n(deftest planted-error (throw (ex-info "planted gate error" {})))\n')
    (work/'planted-overlay.json').write_text(json.dumps({'view':entry['view'],'original-sha256':hashlib.sha256(before).hexdigest(),'planted-sha256':hashlib.sha256(view.read_bytes()).hexdigest(),'expected':'one failure and one error; Node exit1'},indent=2)+'\n')
classpath=os.pathsep.join([*views,*jars])
(work/'compiled').mkdir()
run(['java','-Xmx1800m','-Djava.io.tmpdir='+str(work/'tmp'),'-cp',classpath,'clojure.main','-m','cljs.main','--target','node','--output-dir','compiled/out','--output-to','compiled/tests.cjs','-c',namespace],'compile')
output=run(['node','compiled/tests.cjs'],'Node',timeout=600,expect_failure=args.plant_failure)
if tests:
    assert all('Testing '+n in output for n in tests),output[-2000:]
    assert re.search(r'Ran [1-9]\d* tests containing [1-9]\d* assertions\.',output)
    assert ('1 failures, 1 errors.' if args.plant_failure else '0 failures, 0 errors.') in output,output[-2000:]
else:assert 'all green' in output and 'FAIL' not in output
lint=None
if args.project == 'ipq':
    lint_cp=run(['clojure','-Srepro','-Spath','-M:lint'],'resolve-lint').strip()
    config='{:lint-as {kotoba.test/deftest clojure.test/deftest kotoba.test/is clojure.test/is kotoba.test/testing clojure.test/testing kotoba.test.cljs/deftest cljs.test/deftest kotoba.test.cljs/is cljs.test/is kotoba.test.cljs/testing cljs.test/testing} :linters {:unresolved-symbol {:exclude [thrown? thrown-with-msg?]}}}'
    lint_output=run(['java','-cp',lint_cp,'clojure.main','-m','clj-kondo.main','--lint',*local_views,'--config',config,'--fail-level','error'],'lint')
    count=re.search(r'errors: (\d+), warnings: (\d+)',lint_output);assert count and count[1]=='0'
    lint={'errors':int(count[1]),'warnings':int(count[2])};print(lint_output.strip())
(work/'result.json').write_text(json.dumps({'project':row['path'],'test-namespaces':tests,'host':'real compiled CLJS / Node','exit':1 if args.plant_failure else 0,'planted-failure-refused':args.plant_failure,'lint':lint,'summary':output[-1500:]},indent=2)+'\n')
print(output[-2200:]);print('Evidence:',work)
