#!/usr/bin/env python3
"""Test a signed fleet checkpoint under an injected Linux ARM64 read error.

The native Amu candidate compiles the source-locked guest and runner. Python
only stages bytes and observes isolated Podman processes with synthetic keys.
"""
import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--amu', type=Path, required=True)
p.add_argument('--compiler', type=Path, required=True)
p.add_argument('--compiler-sha256', required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
amu, compiler, out = a.amu.resolve(), a.compiler.resolve(strict=True), a.output.resolve()
sha = lambda x: hashlib.sha256(x).hexdigest()
if sha(compiler.read_bytes()) != a.compiler_sha256:
    raise ValueError('compiler SHA mismatch')
out.mkdir(parents=True, exist_ok=False)
paths = {
 'kagami/fleet_store_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_store_native.kotoba',
 'kagami/fleet_announce_edn.kotoba':'lib/kotoba.kagami/src/kagami/fleet_announce_edn.kotoba',
 'kagami/fleet_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_native.kotoba',
 'kagami/fleet_store_native_test.kotoba':'lib/kotoba.kagami/test/kagami/fleet_store_native_test.kotoba',
 'hata/store_io.kotoba':'lib/kotoba.hata/src/hata/store_io.kotoba',
 'hata/codec.kotoba':'lib/kotoba.hata/src/hata/codec.kotoba',
 'kotoba_harness/data.kotoba':'lib/kotoba.kotobaHarness/src/kotoba_harness/data.kotoba',
 'ed25519/selfhost.kotoba':'lib/org.ietf.ed25519/kotoba/ed25519/selfhost.kotoba',
 'sha2/core.kotoba':'lib/gov.nist.sha2/kotoba/sha2/core.kotoba'}
sources = {name: (ROOT / path).read_bytes() for name, path in paths.items()}
for name, data in sources.items():
    dest = out / 'src' / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
lock = out / 'sources.ksl'
lock.write_text('KSL1\nentry /src/kagami/fleet_store_native_test.kotoba\nroot /src\n' + ''.join(
    f'file {sha(data)} /src/{name}\n' for name, data in sorted(sources.items())))
spec = importlib.util.spec_from_file_location('mac', amu / 'scripts/seed/check-aiueos-user-macos-native.py')
mac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mac)
mac.native_run(compiler, out, 'compile', '/src/kagami/fleet_store_native_test.kotoba', '--target', 'aarch64-macos',
               '--output', 'store.kseed', '--source-path', '/src', '--source-lock', 'sources.ksl', '--source-lock-sha256', sha(lock.read_bytes()))
(out / 'runner.kotoba').write_bytes((amu / 'seed/x86_64-kx64-runner.kotoba').read_bytes())
mac.native_run(compiler, out, 'compile', 'runner.kotoba', '--target', 'aarch64-linux', '--output', 'store.elf',
               '--format', 'packed', '--payload', 'store.kseed')
(out / 'store.elf').chmod(0o755)
image = 'docker.io/library/python:3.12-alpine'
env = {'KEXE_ALLOW':'35,38', 'KEXE_CAP_RESOURCES_35':'/work', 'KEXE_FUEL':'100000000000',
       'KEXE_STRUCTURED_REPORT':'1', 'KEXE_SECCOMP':'if-available', 'KEXE_STACK_BYTES':'8388608'}
def run(mode, name, expected, profile=None):
    cmd = ['podman','run','--rm','--pull','never','--network','none','--platform','linux/arm64', '-v', str(out)+':/work:rw']
    if profile: cmd += ['--security-opt','seccomp='+str(profile)]
    for key,value in env.items(): cmd += ['-e',key+'='+value]
    result = subprocess.run(cmd+[image,'/work/store.elf',mode,'/work/'+name], capture_output=True, text=True, timeout=180)
    if result.returncode or result.stderr or f':status :ok :result {expected} ' not in result.stdout:
        raise ValueError((mode,name,result.returncode,result.stdout[-800:],result.stderr[-800:]))
    return result.stdout.strip()
for name in ('fault','negative','normal'):
    (out / name).mkdir()
    run('init',name,0)
old = (out / 'fault/fleet.state').read_bytes()
if not old or any((out / name / 'fleet.state').read_bytes() != old for name in ('negative','normal')):
    raise ValueError('fixture checkpoints differ')
profile = out / 'pread-eio.json'
profile.write_text(json.dumps({'defaultAction':'SCMP_ACT_ALLOW','architectures':['SCMP_ARCH_AARCH64'],
 'syscalls':[{'names':['pread64'],'action':'SCMP_ACT_ERRNO','errnoRet':5,
              'args':[{'index':2,'value':len(old),'op':'SCMP_CMP_EQ'}]}]}))
fault_result=run('fault','fault',0,profile)
if (out / 'fault/fleet.state').read_bytes()!=old or (out/'fault/fleet.state.pending').exists():
    raise ValueError('read fault changed the checkpoint')
negative=run('fault','negative',15)
if (out / 'negative/fleet.state').read_bytes()==old:
    raise ValueError('disabled fault did not commit, negative control invalid')
run('success','normal',0)
receipt={'status':'PASS_FLEET_READ_EIO_LINUX_ARM64','compilerSha256':sha(compiler.read_bytes()),
 'sources':{n:sha(v) for n,v in sorted(sources.items())},'elfSha256':sha((out/'store.elf').read_bytes()),
 'observerSha256':sha(Path(__file__).read_bytes()),'checkpointBytes':len(old),'faultResult':fault_result,
 'negativeResult':negative,'scope':'isolated Linux ARM64 container, synthetic keys; not production fleet or power-loss evidence'}
(out/'evidence.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(receipt['status'],flush=True)
