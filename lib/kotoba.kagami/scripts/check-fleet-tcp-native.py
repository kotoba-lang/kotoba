#!/usr/bin/env python3
"""Build with the pinned Mac Amu root; exercise isolated Linux ARM loopback.

Usage: python3 check-fleet-tcp-native.py AMU_DIR NEW_OUTPUT_DIR
Requires the local python:3.12-alpine ARM image and a running Podman machine.
The app transport has no Noise handshake or provisioned production trust.
"""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

if len(sys.argv) != 3: raise SystemExit(__doc__)
amu, out = map(lambda x: Path(x).resolve(), sys.argv[1:])
repo = Path(__file__).resolve().parents[3]
out.mkdir(parents=True, exist_ok=False)
sha = lambda x: hashlib.sha256(x).hexdigest()
compiler = amu / 'seed/bootstrap/aarch64-macos/amu-full-root.macho'
if sha(compiler.read_bytes()) != '2c551579c06a0228029bb06bae177e93126ecbbc37d636d693c471dbac8d1536':
    raise ValueError('unexpected Amu compiler')
files = {
 'kagami/fleet_tcp_native_test.kotoba':'lib/kotoba.kagami/test/kagami/fleet_tcp_native_test.kotoba',
 'kagami/fleet_tcp_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_tcp_native.kotoba',
 'kagami/fleet_announce_edn.kotoba':'lib/kotoba.kagami/src/kagami/fleet_announce_edn.kotoba',
 'kagami/fleet_store_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_store_native.kotoba',
 'kagami/fleet_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_native.kotoba',
 'hata/store_io.kotoba':'lib/kotoba.hata/src/hata/store_io.kotoba',
 'hata/codec.kotoba':'lib/kotoba.hata/src/hata/codec.kotoba',
 'kotoba_harness/data.kotoba':'lib/kotoba.kotobaHarness/src/kotoba_harness/data.kotoba',
 'ed25519/selfhost.kotoba':'lib/org.ietf.ed25519/kotoba/ed25519/selfhost.kotoba',
 'sha2/core.kotoba':'lib/gov.nist.sha2/kotoba/sha2/core.kotoba',
 'sha3/core.kotoba':'lib/gov.nist.sha3/kotoba/sha3/core.kotoba',
 'noise/frame.kotoba':'lib/kotoba.noise/kotoba/noise/frame.kotoba',
 'noise/tcp.kotoba':'lib/kotoba.noise/kotoba/noise/tcp.kotoba'}
sources = {name:(repo / path).read_bytes() for name,path in files.items()}
spec = importlib.util.spec_from_file_location('mac', amu / 'scripts/seed/check-aiueos-user-macos-native.py')
mac = importlib.util.module_from_spec(spec); spec.loader.exec_module(mac)
runner_source = (amu / 'seed/x86_64-kx64-runner.kotoba').read_bytes()
observer = repo / 'lib/kotoba.kagami/scripts/check-fleet-tcp-loopback.py'
image_name = 'docker.io/library/python:3.12-alpine'
image_info = subprocess.run(['podman','image','inspect',image_name,'--format','{{.Id}} {{.Architecture}}'],
                            check=True,capture_output=True,text=True,timeout=30).stdout.strip()
if not image_info.endswith(' arm64'): raise ValueError('local Alpine image must be arm64')

def build(label, source_map):
    work = out / label; work.mkdir()
    for name,data in source_map.items():
        path = work / 'src' / name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
    lock = work / 'sources.ksl'
    lock.write_text('KSL1\nentry /src/kagami/fleet_tcp_native_test.kotoba\nroot /src\n' + ''.join(
        f'file {sha(data)} /src/{name}\n' for name,data in sorted(source_map.items())))
    mac.native_run(compiler, work, 'compile', '/src/kagami/fleet_tcp_native_test.kotoba',
                   '--target','aarch64-macos','--output','test.kseed','--source-path','/src',
                   '--source-lock','sources.ksl','--source-lock-sha256',sha(lock.read_bytes()))
    (work / 'runner.kotoba').write_bytes(runner_source)
    mac.native_run(compiler, work, 'compile','runner.kotoba','--target','aarch64-linux',
                   '--output','test.elf','--format','packed','--payload','test.kseed')
    (work / 'test.elf').chmod(0o755)
    return work

def run(work):
    return subprocess.run(['podman','run','--rm','--pull','never','--network','none','--platform','linux/arm64',
                           '-v',str(work)+':/work:rw','-v',str(observer)+':/observer.py:ro',
                           image_name,'python3','/observer.py'],capture_output=True,text=True,timeout=300)

work = build('normal', sources)
result = run(work)
if result.returncode != 0: raise ValueError(('normal',result.returncode,result.stdout,result.stderr[-1500:]))
report = json.loads((work / 'tcp-loopback-result.json').read_text())
if report['status'] != 'PASS_FLEET_TCP_LOOPBACK': raise ValueError(report)
needle = b'(not (valid-utf8? body))'
if sources['kagami/fleet_tcp_native.kotoba'].count(needle) != 1: raise ValueError('unexpected UTF-8 guard')
mutant = dict(sources)
mutant['kagami/fleet_tcp_native.kotoba'] = mutant['kagami/fleet_tcp_native.kotoba'].replace(needle,b'false')
bad = build('mutant', mutant)
negative = run(bad)
if negative.returncode == 0 or 'good PASS' not in negative.stdout or 'bad-utf8' not in negative.stderr:
    raise ValueError(('negative control not detected',negative.returncode,negative.stdout,negative.stderr[-1500:]))
evidence = {'status':'PASS_FLEET_TCP_NATIVE_SYNTHETIC', 'compilerSha256':sha(compiler.read_bytes()),
            'runnerSourceSha256':sha(runner_source), 'observerSha256':sha(observer.read_bytes()),
            'builderSha256':sha(Path(__file__).read_bytes()), 'image':image_info,
            'sources':{name:sha(data) for name,data in sorted(sources.items())},
            'kseedSha256':sha((work/'test.kseed').read_bytes()), 'elfSha256':sha((work/'test.elf').read_bytes()),
            'tests':report, 'utf8GuardMutant':{'exit':negative.returncode,'detected':True},
            'scope':'local Linux ARM container, network none plus loopback, synthetic fixtures; no Noise handshake, production fleet transport or live trust'}
(out/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
print('PASS_FLEET_TCP_NATIVE_SYNTHETIC', flush=True)
