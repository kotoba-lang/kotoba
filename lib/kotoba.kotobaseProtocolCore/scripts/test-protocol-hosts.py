"""Qualify declared project hosts and public source origins in isolated classpaths."""
from pathlib import Path
import argparse, json, os, re, subprocess, tempfile

parser = argparse.ArgumentParser()
parser.add_argument('workspace', type=Path)
parser.add_argument('--kotoba', required=True, type=Path)
parser.add_argument('--engine', required=True, type=Path)
args = parser.parse_args()
owner = Path(__file__).resolve().parent.parent
workspace, kotoba, engine = args.workspace.resolve(), args.kotoba.resolve(), args.engine.resolve()
ci_temp = Path(os.environ['RUNNER_TEMP']).resolve() if os.environ.get('RUNNER_TEMP') else None
assert '/github/workspaces/' in str(workspace) or (os.environ.get('GITHUB_ACTIONS') == 'true' and ci_temp and workspace.is_relative_to(ci_temp))
assert (kotoba / 'bin/kbb').is_file() and engine.is_file()
workspace.mkdir(parents=True, exist_ok=True)
work = Path(tempfile.mkdtemp(prefix='protocol-hosts-', dir=workspace))
(work / 'tmp').mkdir()
empty = work / 'empty-nbb.edn'; empty.write_text('{:paths []}\n')
env = {**os.environ, 'TMPDIR': str(work / 'tmp'), 'KOTOBA_IPQ_FS_CACHE': str(work / 'ipq-cache'), 'KBB_HOME': str(kotoba), 'KBB_ENGINE': str(engine), 'KBB_NO_STDLIB': '1', 'KBB_NO_NPM': '1', 'PATH': str(kotoba / 'bin') + os.pathsep + os.environ.get('PATH', '')}
matrix = json.loads((owner / 'maintenance/protocol-test-hosts.json').read_text())['projects']
results = {'JVM': [], 'SCI': [], 'compiled-CLJS': [], 'source-origins': []}

def run(command, label, project=owner, timeout=600):
    p = subprocess.run([str(c) for c in command], cwd=project, env=env, text=True, capture_output=True, timeout=timeout)
    (work / (label + '.log')).write_text(p.stdout + p.stderr)
    assert p.returncode == 0, (label, p.returncode, p.stdout[-3000:], p.stderr[-3000:])
    return p.stdout

def summary(output, selected):
    count = re.search(r'Ran (\d+) tests containing (\d+) assertions\.\s+0 failures, 0 errors\.', output)
    assert count and int(count[1]) > 0 and all('Testing ' + n in output for n in selected)
    return {'tests': int(count[1]), 'assertions': int(count[2]), 'failures': 0, 'errors': 0}

for row in matrix:
    project = (owner / row['path']).resolve()
    name = 'owner' if row['path'] == '.' else row['path'].rsplit('.', 1)[-1]
    cp = run(['clojure', '-Srepro', '-Spath', '-M:test'], name + '-resolve', project).strip()
    selected = [r['namespace'] for r in row['tests'] if r['JVM']]
    if selected:
        driver = work / (name + '-JVM.clj')
        driver.write_text("(require '[clojure.test :as t] " + ' '.join("'" + n for n in selected) + ")\n(let [r (t/run-tests " + ' '.join("'" + n for n in selected) + ")] (System/exit (if (and (pos? (:test r)) (t/successful? r)) 0 1)))\n")
        output = run(['java', '-Xmx1000m', '-Djava.io.tmpdir=' + str(work / 'tmp'), '-cp', cp, 'clojure.main', '-i', kotoba / 'tools/cljk_loader.cljk', driver], name + '-JVM', project)
        results['JVM'].append({'project': name, **summary(output, selected)})
    directories = [str((project / p).resolve()) for p in cp.split(os.pathsep) if (project / p).is_dir()]
    selected = [r['namespace'] for r in row['tests'] if r['SCI']]
    driver = work / (name + '-SCI.cljk')
    driver.write_text('(ns protocol-sci-' + name + ' (:require [cljs.test :as t] ' + ' '.join('[' + n + ']' for n in selected) + "))\n(defmethod t/report [::t/default :end-run-tests] [m] (when-not (and (pos? (:test m)) (t/successful? m)) (set! (.-exitCode js/process) 1)))\n(t/run-tests " + ' '.join("'" + n for n in selected) + ')\n')
    output = run([kotoba / 'bin/kbb', '--backend', 'sci', '--config', empty, '--classpath', os.pathsep.join(directories), driver], name + '-SCI', project)
    results['SCI'].append({'project': name, **summary(output, selected)})
    if name != 'owner':
        namespace, var = {'ipq': ('kotobase.protocols.ipq', 'handle'), 'query-surfaces': ('kotobase.query.surfaces', 'enrich'), 'lfs': ('kotobase.lfs.engine', 'handle-batch')}[name]
        neutral = name != 'lfs'
        requires = f'[{namespace} :as impl]' + (' [kotobase.protocols.http :as neutral]' if neutral else '')
        fields = ':source source :admission :not-granted' + (' :contract contract' if neutral else '')
        bindings = "source (:file (meta #'impl/" + var + '))' + (" contract (:file (meta #'neutral/response))" if neutral else '')
        checks = '(assert (.startsWith source ' + json.dumps(str(project / 'src')) + '))' + (' (assert (.startsWith contract ' + json.dumps(str(owner / 'src')) + '))' if neutral else '')
        fixture = work / (name + '-origin.cljk')
        fixture.write_text(f'(ns protocol-origin-{name} (:require {requires}))\n(defn main [] (let [{bindings}] {checks} {{{fields}}}))\n')
        flags = [v for directory in directories for v in ['--source-path', directory]]
        output = run([kotoba / 'bin/kotoba', 'run', fixture, '--runtime', 'sci', '--library', 'kotoba.test', *flags, '--json'], name + '-public-CLI-origin', project)
        envelope = json.loads(output); assert envelope['kotoba.cli/ok?']
        value = envelope['kotoba.cli/data']['value']; assert value['admission'] == 'not-granted'
        results['source-origins'].append({'id': 'kotoba.kotobase.protocol.' + name, **value})
    output = run(['python3', owner / 'scripts/test-protocol-compiled.py', workspace, '--project', name], name + '-compiled', timeout=900)
    selected = [r['namespace'] for r in row['tests'] if r['compiled-CLJS']]
    results['compiled-CLJS'].append({'project': name, **summary(output, selected)})
    (work / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print('Qualified declared hosts:', name, flush=True)
assert len(results['JVM']) == 3 and len(results['SCI']) == len(results['compiled-CLJS']) == 4 and len(results['source-origins']) == 3
print(json.dumps(results, indent=2)); print('Evidence:', work)
