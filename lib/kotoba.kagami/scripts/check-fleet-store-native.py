#!/usr/bin/env python3
"""Exercise signed fleet storage with synthetic keys; no live trust or sync."""
import argparse
import concurrent.futures
import importlib.util
import re
import signal
import time
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('native_gate', ROOT / 'lib/kotoba.hata/scripts/native_gate.py')
native = importlib.util.module_from_spec(spec); spec.loader.exec_module(native)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--compiler', type=Path, required=True); p.add_argument('--compiler-sha256', required=True)
p.add_argument('--packager', type=Path); p.add_argument('--packager-sha256'); p.add_argument('--runner', type=Path)
p.add_argument('--output', type=Path, required=True)
gate = native.NativeGate(p.parse_args())
files = {
 'kagami/fleet_store_native.kotoba': ROOT / 'lib/kotoba.kagami/src/kagami/fleet_store_native.kotoba',
 'kagami/fleet_native.kotoba': ROOT / 'lib/kotoba.kagami/src/kagami/fleet_native.kotoba',
 'kagami/fleet_store_native_test.kotoba': ROOT / 'lib/kotoba.kagami/test/kagami/fleet_store_native_test.kotoba',
 'hata/store_io.kotoba': ROOT / 'lib/kotoba.hata/src/hata/store_io.kotoba',
 'hata/codec.kotoba': ROOT / 'lib/kotoba.hata/src/hata/codec.kotoba',
 'ed25519/selfhost.kotoba': ROOT / 'lib/org.ietf.ed25519/kotoba/ed25519/selfhost.kotoba',
 'sha2/core.kotoba': ROOT / 'lib/gov.nist.sha2/kotoba/sha2/core.kotoba'}
sources = {n:p.read_bytes() for n,p in files.items()}
image = gate.build('store', 'kagami/fleet_store_native_test.kotoba', sources)
base = gate.out / 'normal'; base.mkdir()
def run(label, mode, directory=base, expected=0):
 return gate.run(label, image, expected, [mode, directory], '35,38', directory)
for mode in ['init', 'state-old', 'invalid', 'state-old', 'success', 'state-new', 'already', 'state-new']:
 run('normal-'+mode+str(len(gate.observations)), mode)
announce = gate.out / 'announce'; announce.mkdir()
for mode in ['init','announce-invalid','state-old','announce','state-new','announce-already','state-new']:
 run('announce-'+mode+str(len(gate.observations)),mode,announce)
race = gate.out / 'race'; race.mkdir(); run('race-init', 'init', race)
# Each contender may observe a held lock or the newly committed checkpoint.
def race_one(i):
 if gate.darwin:
  r=gate.fd3([image, *gate.guest_args(['race',race])])
  if r.stderr or r.stdout: raise ValueError(('race output',r.stdout,r.stderr))
  return r.returncode
 command=[gate.runner,image,'0','0','x86_64','35,38','--','race',race]
 env=dict(gate.env('35,38',race), KEXE_FUEL='100000000000', KEXE_STRUCTURED_REPORT='1')
 r=subprocess.run(list(map(str,command)),cwd=gate.out,env=env,capture_output=True,timeout=600)
 m=re.search(rb':result (-?[0-9]+)\b',r.stdout)
 if r.returncode or r.stderr or not m: raise ValueError(('race output',r.returncode,r.stdout,r.stderr))
 return int(m.group(1))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 results=list(pool.map(race_one,range(2)))
if results.count(10)!=1 or any(x not in (10,11,12,16) for x in results): raise ValueError(('race',results))
run('race-reopen', 'state-new', race)
# Deliberately broken implementations must fail the same behavioral checks.
store_source = sources['kagami/fleet_store_native.kotoba']
for label,needle,replacement,mode,expected in [
 ('verify-bypass', b'(not (fleet/verify-edn-plan-into plan heads seq hash signer))', b'false', 'invalid', 4),
 ('compare-bypass', b'(string=? old observed)', b'true', 'stale', 6),
 ('replay-bypass', b'(string=? next observed)', b'true', 'stale', 6)]:
 if store_source.count(needle)!=1: raise ValueError('unexpected store source: '+label)
 mutant=dict(sources); mutant['kagami/fleet_store_native.kotoba']=store_source.replace(needle,replacement)
 broken=gate.build('control-'+label,'kagami/fleet_store_native_test.kotoba',mutant)
 directory=gate.out/('control-'+label+'-state'); directory.mkdir()
 run('control-init-'+label,'init',directory)
 if label in ('compare-bypass','replay-bypass'):
  path=directory/'fleet.state'; path.write_bytes(path.read_bytes().replace(b'0000000000000000',b'0000000000000009',1))
 gate.run('control-detected-'+label,broken,expected,[mode,directory],'35,38',directory)
# Each announcement field must be bound to the verified record.
for label,needle,replacement in [
 ('announce-type',b'(not (string=? message-type "head-announce"))',b'false'),
 ('announce-graph',b'(not (string=? graph "fleet-db"))',b'false'),
 ('announce-sequence',b'(= head-seq (+ seq (document-count heads)))',b'true'),
 ('announce-value',b'(string=? head-value (fs-hex-bytes plan 32))',b'true'),
 ('announce-record',b'(string=? announced-head last-head)',b'true')]:
 if store_source.count(needle)!=1: raise ValueError('unexpected announcement source: '+label)
 mutant=dict(sources);mutant['kagami/fleet_store_native.kotoba']=store_source.replace(needle,replacement)
 broken=gate.build('control-'+label,'kagami/fleet_store_native_test.kotoba',mutant)
 directory=gate.out/('control-'+label+'-state');directory.mkdir();run('control-init-'+label,'init',directory)
 gate.run('control-detected-'+label,broken,17,['announce-invalid',directory],'35,38',directory)
# Disk data is not a trust source: reject a modified stored value unchanged.
tamper=gate.out/'tamper';tamper.mkdir();run('tamper-init','init',tamper)
path=tamper/'fleet.state'; damaged=path.read_bytes().replace(b'0000000000000000',b'0000000000000009',1);path.write_bytes(damaged)
run('tamper-refusal','stale',tamper)
if path.read_bytes()!=damaged: raise ValueError('corrupt checkpoint was overwritten')
# Fault-only I/O adapters report failure after each real operation. The normal
# binary checks the on-disk state; this does not simulate loss of power.
io = sources['hata/store_io.kotoba']
write = b'(= (typed-cap-call :fs/app-data :string :string (string-concat path (string-concat "WRITE_SEP" data))) data)'
sync = b'(= (typed-cap-call :fs/app-data :string :string (string-concat path "FSYNC_SEP")) "1")'
rename = b'(= (typed-cap-call :fs/app-data :string :string (string-concat from (string-concat "RENAME_SEP" to))) "1")'
for stage,needle,replacement,expected_state in [
 ('write',write,b'(and '+write+b' false)','state-old'),
 ('file-sync',sync,b'(let [ok '+sync+b'] (if (>= (string-index-of path "fleet.state.pending") 0) false ok))','state-old'),
 ('rename',rename,b'(and '+rename+b' false)','state-new'),
 ('dir-sync',sync,b'(let [ok '+sync+b'] (if (< (string-index-of path "fleet.state.pending") 0) false ok))','state-new')]:
 if io.count(needle)!=1: raise ValueError('unexpected I/O source: '+stage)
 mutant = dict(sources); mutant['hata/store_io.kotoba'] = io.replace(needle,replacement)
 variant = gate.build('fault-'+stage, 'kagami/fleet_store_native_test.kotoba', mutant)
 directory=gate.out/('fault-'+stage+'-state'); directory.mkdir()
 run('fault-init-'+stage, 'init', directory)
 gate.run('fault-observe-'+stage, variant, 0, ['fault', directory], '35,38', directory)
 run('fault-reopen-'+stage, expected_state, directory)
# Reconciliation must not return already-committed when either fsync fails.
for stage,condition in [('retry-file-sync',b'(>= (string-index-of path "fleet.state") 0)'),
                        ('retry-dir-sync',b'(< (string-index-of path "fleet.state") 0)')]:
 mutant=dict(sources)
 mutant['hata/store_io.kotoba']=io.replace(sync,b'(let [ok '+sync+b'] (if '+condition+b' false ok))')
 variant=gate.build('fault-'+stage,'kagami/fleet_store_native_test.kotoba',mutant)
 directory=gate.out/('fault-'+stage+'-state');directory.mkdir()
 run('fault-init-'+stage,'init',directory);run('fault-commit-'+stage,'success',directory)
 gate.run('fault-observe-'+stage,variant,0,['fault',directory],'35,38',directory)
 run('fault-reopen-'+stage,'state-new',directory)
# Pause a test-only adapter after an operation, verify the real lock is held,
# SIGKILL the writer and reopen from a fresh process. No power cut is simulated.
pause_helper = b"""
(defn- pause-after [enabled :bool ok :bool] :bool
  (if (and enabled ok)
    (let [base (typed-cap-call :cli/args :string :string "1")
          signal (typed-cap-call :fs/app-data :string :string
                   (string-concat base "/readyWRITE_SEPready"))]
      (if (not= signal "ready") false
        (loop [i 0] (if (= i 9223372036854775807) false (recur (+ i 1)))))) ok))
"""
crash_results=[]
for stage,needle,replacement,expected_state in [
 ('partial-write',write,b'(pause-after true (= (typed-cap-call :fs/app-data :string :string (string-concat path \"WRITE_SEPpartial\")) \"partial\"))','state-old'),
 ('write',write,b'(pause-after true '+write+b')','state-old'),
 ('file-sync',sync,b'(pause-after (>= (string-index-of path "fleet.state.pending") 0) '+sync+b')','state-old'),
 ('rename',rename,b'(pause-after true '+rename+b')','state-new'),
 ('dir-sync',sync,b'(pause-after (< (string-index-of path "fleet.state.pending") 0) '+sync+b')','state-new')]:
 if io.count(needle)!=1: raise ValueError('unexpected I/O source: '+stage)
 modified=io.replace(b'(:capabilities [:fs/app-data])',b'(:capabilities [:fs/app-data :cli/args])')
 modified=modified.replace(needle,replacement)+pause_helper
 mutant=dict(sources);mutant['hata/store_io.kotoba']=modified
 writer=gate.build('crash-'+stage,'kagami/fleet_store_native_test.kotoba',mutant)
 directory=gate.out/('crash-'+stage+'-state');directory.mkdir();run('crash-init-'+stage,'init',directory)
 if gate.darwin:
  child=gate.fd3([writer,*gate.guest_args(['race',directory])],popen=True)
 else:
  command=[gate.runner,writer,'0','0','x86_64','35,38','--','race',directory]
  env=dict(gate.env('35,38',directory),KEXE_FUEL='100000000000',KEXE_STRUCTURED_REPORT='1')
  child=subprocess.Popen(list(map(str,command)),cwd=gate.out,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:
  deadline=time.monotonic()+60
  while not (directory/'ready').exists():
   if child.poll() is not None: raise ValueError(('writer exited before hook',stage,child.communicate()))
   if time.monotonic()>=deadline: raise TimeoutError(('writer hook',stage))
   time.sleep(.01)
  run('crash-lock-held-'+stage,'race',directory,11)
 finally:
  if child.poll() is None: child.kill()
  stdout,stderr=child.communicate(timeout=10)
 if child.returncode!=-signal.SIGKILL or stdout or stderr: raise ValueError(('unexpected writer exit',stage,child.returncode,stdout,stderr))
 run('crash-reopen-'+stage,expected_state,directory)
 run('crash-retry-'+stage,'success' if expected_state=='state-old' else 'already',directory)
 run('crash-final-'+stage,'state-new',directory)
 crash_results.append({'stage':stage,'exit':child.returncode,'reopened':expected_state,'retry':'success' if expected_state=='state-old' else 'already'})
gate.finish('PASS_FLEET_STORE_SYNTHETIC', observerSHA256=native.sha(Path(__file__).read_bytes()), raceResults=results, crashResults=crash_results, injectedFaults=['write','file-sync','rename','dir-sync','retry-file-sync','retry-dir-sync'], negativeControls=['signature-verification-bypass','checkpoint-compare-bypass','replay-compare-bypass','announcement-type','announcement-graph','announcement-sequence','announcement-value','modified-checkpoint'],
 scope='local native synthetic data and SIGKILL only; no power-cut test, rollback protection, real trust, network or release')
