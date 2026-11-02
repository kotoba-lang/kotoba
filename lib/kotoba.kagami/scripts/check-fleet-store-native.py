#!/usr/bin/env python3
"""Exercise signed fleet storage with synthetic keys; no live trust or sync."""
import argparse
import concurrent.futures
import importlib.util
import re
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
for mode in ['init', 'state-old', 'invalid', 'state-old', 'success', 'state-new', 'stale', 'state-new']:
 run('normal-'+mode+str(len(gate.observations)), mode)
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
if results.count(10)!=1 or any(x not in (10,11,12) for x in results): raise ValueError(('race',results))
run('race-reopen', 'state-new', race)
# Deliberately broken implementations must fail the same behavioral checks.
store_source = sources['kagami/fleet_store_native.kotoba']
for label,needle,replacement,mode,expected in [
 ('verify-bypass', b'(not (fleet/verify-edn-plan-into plan heads seq hash signer))', b'false', 'invalid', 4),
 ('compare-bypass', b'(not (string=? old observed))', b'false', 'stale', 6)]:
 if store_source.count(needle)!=1: raise ValueError('unexpected store source: '+label)
 mutant=dict(sources); mutant['kagami/fleet_store_native.kotoba']=store_source.replace(needle,replacement)
 broken=gate.build('control-'+label,'kagami/fleet_store_native_test.kotoba',mutant)
 directory=gate.out/('control-'+label+'-state'); directory.mkdir()
 run('control-init-'+label,'init',directory)
 if label=='compare-bypass': run('control-advance-'+label,'success',directory)
 gate.run('control-detected-'+label,broken,expected,[mode,directory],'35,38',directory)
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
gate.finish('PASS_FLEET_STORE_SYNTHETIC', observerSHA256=native.sha(Path(__file__).read_bytes()), raceResults=results, injectedFaults=['write','file-sync','rename','dir-sync'], negativeControls=['signature-verification-bypass','checkpoint-compare-bypass','modified-checkpoint'],
 scope='local native synthetic data; trusted checkpoint supplied externally; no rollback protection, real trust, network or release')
