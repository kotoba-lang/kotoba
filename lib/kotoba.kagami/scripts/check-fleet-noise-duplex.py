#!/usr/bin/env python3
"""Build synthetic authenticated Noise endpoints and test separate processes.

Usage: python3 check-fleet-noise-duplex.py AMU_DIR NEW_OUTPUT_DIR
Requires local ARM Alpine and Podman; no public network or real secrets.
"""
import hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
if len(sys.argv)!=3:raise SystemExit(__doc__)
amu,out=map(lambda x:Path(x).resolve(),sys.argv[1:]);repo=Path(__file__).resolve().parents[3]
out.mkdir(parents=True,exist_ok=False);sha=lambda x:hashlib.sha256(x).hexdigest()
compiler=amu/'seed/bootstrap/aarch64-macos/amu-full-root.macho'
if sha(compiler.read_bytes())!='2c551579c06a0228029bb06bae177e93126ecbbc37d636d693c471dbac8d1536':raise ValueError('compiler mismatch')
spec=importlib.util.spec_from_file_location('pq',repo/'scripts/check-pq-native.py');pq=importlib.util.module_from_spec(spec);spec.loader.exec_module(pq)
paths=dict(pq.TCP_DEMO['files'])
paths.update({'kagami/fleet_noise_handshake.kotoba':'lib/kotoba.kagami/src/kagami/fleet_noise_handshake.kotoba',
 'kagami/fleet_noise_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_noise_native.kotoba',
 'kagami/fleet_tcp_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_tcp_native.kotoba',
 'kagami/fleet_announce_edn.kotoba':'lib/kotoba.kagami/src/kagami/fleet_announce_edn.kotoba',
 'kagami/fleet_store_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_store_native.kotoba',
 'kagami/fleet_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_native.kotoba',
 'hata/store_io.kotoba':'lib/kotoba.hata/src/hata/store_io.kotoba',
 'hata/codec.kotoba':'lib/kotoba.hata/src/hata/codec.kotoba',
 'kotoba_harness/data.kotoba':'lib/kotoba.kotobaHarness/src/kotoba_harness/data.kotoba'})
original={k:(repo/v).read_bytes() for k,v in paths.items()}
driver=(repo/'lib/kotoba.kagami/test/kagami/fleet_noise_duplex_driver.kotoba').read_bytes()
base=original['noise/tcp_demo.kotoba'];ns=b'(:require [noise.native :as n] [noise.identity :as id] [noise.tcp :as t])'
if base.count(ns)!=1 or base.count(b'(defn main [] :i64')!=1:raise ValueError('fixture changed')
base=base[:base.index(b'(defn main [] :i64')].replace(ns,ns[:-1]+b' [kagami.fleet-noise-native :as fleet] [kagami.fleet-noise-handshake :as hs] [hata.store-io :as io])\n  (:capabilities [:cli/args])')+driver
sources=dict(original);sources['noise/tcp_demo.kotoba']=base
spec=importlib.util.spec_from_file_location('mac',amu/'scripts/seed/check-aiueos-user-macos-native.py');mac=importlib.util.module_from_spec(spec);spec.loader.exec_module(mac)
runner=(amu/'seed/x86_64-kx64-runner.kotoba').read_bytes();observer=repo/'lib/kotoba.kagami/scripts/check-fleet-noise-duplex-loopback.py';image='docker.io/library/python:3.12-alpine'
image_info=subprocess.run(['podman','image','inspect',image,'--format','{{.Id}} {{.Architecture}}'],check=True,capture_output=True,text=True).stdout.strip()
if not image_info.endswith(' arm64'):raise ValueError('expected local arm64 image')
def build(name,staged):
 work=out/name;work.mkdir()
 for key,data in staged.items():
  p=work/'src'/key;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 lock=work/'sources.ksl';lock.write_text('KSL1\nentry /src/noise/tcp_demo.kotoba\nroot /src\n'+''.join(f'file {sha(data)} /src/{key}\n' for key,data in sorted(staged.items())))
 mac.native_run(compiler,work,'compile','/src/noise/tcp_demo.kotoba','--target','aarch64-macos','--output','test.kseed','--source-path','/src','--source-lock','sources.ksl','--source-lock-sha256',sha(lock.read_bytes()))
 (work/'runner.kotoba').write_bytes(runner)
 mac.native_run(compiler,work,'compile','runner.kotoba','--target','aarch64-linux','--output','test.elf','--format','packed','--payload','test.kseed');(work/'test.elf').chmod(0o755)
 return work
def run(work):
 return subprocess.run(['podman','run','--rm','--pull','never','--network','none','--platform','linux/arm64',
  '-v',str(work)+':/work:rw','-v',str(observer)+':/observer.py:ro',image,'python3','/observer.py'],capture_output=True,text=True,timeout=600)
good=build('good',sources);r=run(good)
if r.returncode:raise ValueError(('good',r.returncode,r.stdout,r.stderr[-1500:]))
report=json.loads((good/'duplex-result.json').read_text())
needle=b'(identity/verify-payload (tail done) hash expected)';key='kagami/fleet_noise_handshake.kotoba'
if sources[key].count(needle)!=1:raise ValueError('identity guard anchor')
mutant=dict(sources);mutant[key]=mutant[key].replace(needle,b'true')
bad=build('identity-mutant',mutant);r=run(bad)
if r.returncode==0 or 'good PASS' not in r.stdout or 'wrong' not in r.stderr:raise ValueError(('mutant not detected',r.returncode,r.stdout,r.stderr[-1500:]))
responder_mutant_exit=r.returncode
needle=b'(not (identity/verify-payload (tail message) hash expected))'
if sources[key].count(needle)!=1:raise ValueError('initiator identity guard anchor')
mutant=dict(sources);mutant[key]=mutant[key].replace(needle,b'false')
bad=build('initiator-identity-mutant',mutant);r=run(bad)
if r.returncode==0 or 'good PASS' not in r.stdout or 'wrong-server' not in r.stderr:raise ValueError(('initiator mutant not detected',r.returncode,r.stdout,r.stderr[-1500:]))
evidence={'status':'PASS_FLEET_NOISE_DUPLEX_SYNTHETIC','compilerSha256':sha(compiler.read_bytes()),'runnerSourceSha256':sha(runner),
 'builderSha256':sha(Path(__file__).read_bytes()),'observerSha256':sha(observer.read_bytes()),'driverSha256':sha(driver),'image':image_info,
 'sources':{k:sha(v) for k,v in sorted(original.items())},'stagedEntrySha256':sha(base),'kseedSha256':sha((good/'test.kseed').read_bytes()),'elfSha256':sha((good/'test.elf').read_bytes()),
 'result':report,'responderIdentityGuardMutant':{'exit':responder_mutant_exit,'detected':True},
 'initiatorIdentityGuardMutant':{'exit':r.returncode,'detected':True},
 'scope':'two Linux ARM processes over isolated loopback, deterministic synthetic keys; no live trust, multiple hosts, constant-time or production qualification'}
(out/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n');print('PASS_FLEET_NOISE_DUPLEX_SYNTHETIC',flush=True)
