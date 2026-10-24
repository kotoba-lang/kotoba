"""Run each engine project's declared host suites in isolated processes.

Requires the root npm lock installed with --ignore-scripts, Java/Clojure/Node
and explicit Kotoba CLI/SCI engine checkouts. No live service, native runtime,
deployment or production default is selected by this source qualification.
"""
from pathlib import Path
import argparse,json,os,re,subprocess,tempfile

parser=argparse.ArgumentParser()
parser.add_argument('workspace',type=Path)
parser.add_argument('--kotoba',required=True,type=Path)
parser.add_argument('--engine',required=True,type=Path)
args=parser.parse_args()
owner=Path(__file__).resolve().parent.parent
workspace=args.workspace.resolve();kotoba=args.kotoba.resolve();engine=args.engine.resolve()
ci_temp=Path(os.environ['RUNNER_TEMP']).resolve() if os.environ.get('RUNNER_TEMP') else None
assert '/github/workspaces/' in str(workspace) or (os.environ.get('GITHUB_ACTIONS')=='true' and ci_temp and workspace.is_relative_to(ci_temp))
assert (owner/'node_modules/@noble/hashes/sha2.js').is_file(),'run npm ci --ignore-scripts first'
assert (kotoba/'bin/kbb').is_file() and engine.is_file()
workspace.mkdir(parents=True,exist_ok=True)
work=Path(tempfile.mkdtemp(prefix='engine-hosts-',dir=workspace))
env={**os.environ,'KBB_HOME':str(kotoba),'KBB_ENGINE':str(engine),'KBB_NO_STDLIB':'1','KBB_NO_NPM':'1','NODE_PATH':str(owner/'node_modules'),'PATH':str(kotoba/'bin')+os.pathsep+os.environ.get('PATH','')}
matrix=json.loads((owner/'maintenance/engine-test-hosts.json').read_text())['projects']
results={'JVM':[],'SCI':[],'compiled-CLJS':[],'source-origins':[]}

def run(command,label,project=owner,timeout=600):
    p=subprocess.run([str(c) for c in command],cwd=project,env=env,text=True,capture_output=True,timeout=timeout)
    (work/(label+'.log')).write_text(p.stdout+p.stderr)
    assert p.returncode==0,(label,p.returncode,p.stdout[-2500:],p.stderr[-2500:])
    return p.stdout

for row in matrix:
    project=(owner/row['path']).resolve();name='owner' if row['path']=='.' else row['path'].rsplit('.',1)[-1]
    suites=[r['namespace'] for r in row['tests'] if r['JVM']]
    cp=run(['clojure','-Srepro','-Spath','-M:test'],name+'-JVM-resolve',project).strip()
    runner=work/(name+'-JVM.clj');runner.write_text("(require '[clojure.test :as t] "+' '.join("'"+n for n in suites)+")\n(let [r (t/run-tests "+' '.join("'"+n for n in suites)+")] (System/exit (if (and (pos? (:test r)) (t/successful? r)) 0 1)))\n")
    output=run(['java','-Xmx1000m','-cp',cp,'clojure.main','-i',kotoba/'tools/cljk_loader.cljk',runner],name+'-JVM',project)
    count=re.search(r'Ran (\d+) tests containing (\d+) assertions\.\s+0 failures, 0 errors\.',output);assert count and int(count[1])>0 and all('Testing '+n in output for n in suites)
    results['JVM'].append({'project':name,'tests':int(count[1]),'assertions':int(count[2]),'failures':0,'errors':0})
    runtime_cp=run([kotoba/'bin/kbb','-Spath','-M:test'],name+'-SCI-resolve',project).strip()
    if name in ['owner','legacy']:
        selected=[r['namespace'] for r in row['tests'] if r['compiled-CLJS']]
        output=run([kotoba/'bin/kbb','-M:test',*[v for n in selected for v in ['-n',n]]],name+'-SCI-tests',project)
        count=re.search(r'kbb test: ([1-9]\d*) test\(s\), (\d+) pass, 0 fail, 0 error',output);assert count and all('Testing '+n in output for n in selected)
        results['SCI'].append({'project':name,'tests':int(count[1]),'assertions':int(count[2]),'failures':0,'errors':0})
    if row['async-smoke']:
        output=run([kotoba/'bin/kbb','--backend','sci','--classpath',runtime_cp,row['async-smoke']],name+'-SCI-smoke',project)
        assert 'all green' in output and 'FAIL' not in output
        results['SCI'].append({'project':name,'runner':row['async-smoke'],'exit':0})
    if name!='owner':
        namespace='kotobase.engine' if name=='legacy' else 'kotobase.engine.'+name
        var='open' if name=='legacy' else name+'-engine'
        fixture=work/(name+'-origin.cljk')
        fixture.write_text(f"(ns engine-origin-{name} (:require [{namespace} :as impl] [kotobase.engine.contract :as contract]))\n(defn main [] (let [source (:file (meta #'impl/{var})) neutral (:file (meta #'contract/empty-state))] (assert (.startsWith source {json.dumps(str(project/'src'))})) (assert (.startsWith neutral {json.dumps(str(owner/'src'))})) {{:source source :contract neutral :admission :not-granted}}))\n")
        source_flags=[v for item in runtime_cp.split(os.pathsep) if item for v in ['--source-path',str((project/item).resolve())]]
        output=run([kotoba/'bin/kotoba','run',fixture,'--runtime','sci','--library','kotoba.test',*source_flags,'--json'],name+'-public-CLI-origin',project)
        envelope=json.loads(output);assert envelope['kotoba.cli/ok?'];value=envelope['kotoba.cli/data']['value'];assert value['admission']=='not-granted'
        results['source-origins'].append({'id':'kotoba.kotobase.engine.'+name,**value})
    output=run(['python3',owner/'scripts/test-engine-compiled.py',workspace,'--project',name],name+'-compiled',timeout=900)
    if name in ['owner','legacy']:
        count=re.search(r'Ran (\d+) tests containing (\d+) assertions\.\s+0 failures, 0 errors\.',output);assert count
        results['compiled-CLJS'].append({'project':name,'tests':int(count[1]),'assertions':int(count[2]),'failures':0})
    else:
        assert 'all green' in output
        results['compiled-CLJS'].append({'project':name,'runner':'test/run.cljk','failures':0})
    (work/'results.json').write_text(json.dumps(results,indent=2)+'\n');print('Qualified declared hosts:',name,flush=True)
assert len(results['source-origins'])==3
print(json.dumps(results,indent=2));print('Evidence:',work)
