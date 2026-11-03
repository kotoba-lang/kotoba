#!/usr/bin/env python3
"""Synthetic XXhfs identity + encrypted fleet receive in Linux ARM loopback.

Usage: python3 check-fleet-noise-native.py AMU_DIR NEW_OUTPUT_DIR
Uses existing noise.tcp-demo fixtures, local Podman Alpine ARM image, and no
real key or network. Not production qualification or a constant-time claim.
"""
import hashlib, importlib.util, json, subprocess, sys
from pathlib import Path

if len(sys.argv) != 3: raise SystemExit(__doc__)
amu,out = map(lambda x:Path(x).resolve(),sys.argv[1:]); repo=Path(__file__).resolve().parents[3]
out.mkdir(parents=True,exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
compiler=amu/'seed/bootstrap/aarch64-macos/amu-full-root.macho'
if sha(compiler.read_bytes())!='df6b602af6375ec96d951c7bea9bfdd4c456702af7e1f1487d0a2e7fa3874574': raise ValueError('compiler mismatch')
spec=importlib.util.spec_from_file_location('pq',repo/'scripts/check-pq-native.py');pq=importlib.util.module_from_spec(spec);spec.loader.exec_module(pq)
paths=dict(pq.TCP_DEMO['files'])
paths.update({'kagami/fleet_noise_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_noise_native.kotoba',
 'kagami/fleet_tcp_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_tcp_native.kotoba',
 'kagami/fleet_announce_edn.kotoba':'lib/kotoba.kagami/src/kagami/fleet_announce_edn.kotoba',
 'kagami/fleet_store_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_store_native.kotoba',
 'kagami/fleet_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_native.kotoba',
 'hata/store_io.kotoba':'lib/kotoba.hata/src/hata/store_io.kotoba',
 'hata/codec.kotoba':'lib/kotoba.hata/src/hata/codec.kotoba',
 'kotoba_harness/data.kotoba':'lib/kotoba.kotobaHarness/src/kotoba_harness/data.kotoba'})
original={name:(repo/path).read_bytes() for name,path in paths.items()}
driver=(repo/'lib/kotoba.kagami/test/kagami/fleet_noise_driver.kotoba').read_bytes()
base=original['noise/tcp_demo.kotoba']; ns=b'(:require [noise.native :as n] [noise.identity :as id] [noise.tcp :as t])'
if base.count(ns)!=1 or base.count(b'(defn main [] :i64')!=1: raise ValueError('unexpected fixture')
base=base[:base.index(b'(defn main [] :i64')].replace(ns,ns[:-1]+b' [kagami.fleet-noise-native :as fleet] [hata.store-io :as io])\n  (:capabilities [:cli/args])')+driver
sources=dict(original);sources['noise/tcp_demo.kotoba']=base
spec=importlib.util.spec_from_file_location('mac',amu/'scripts/seed/check-aiueos-user-macos-native.py');mac=importlib.util.module_from_spec(spec);spec.loader.exec_module(mac)
runner=(amu/'seed/x86_64-kx64-runner.kotoba').read_bytes()
image='docker.io/library/python:3.12-alpine'
image_info=subprocess.run(['podman','image','inspect',image,'--format','{{.Id}} {{.Architecture}}'],check=True,text=True,capture_output=True).stdout.strip()
if not image_info.endswith(' arm64'): raise ValueError('expected local arm64 Alpine')

def build(name, staged):
 work=out/name;work.mkdir()
 for key,data in staged.items():
  p=work/'src'/key;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 lock=work/'sources.ksl';lock.write_text('KSL1\nentry /src/noise/tcp_demo.kotoba\nroot /src\n'+''.join(f'file {sha(data)} /src/{key}\n' for key,data in sorted(staged.items())))
 mac.native_run(compiler,work,'compile','/src/noise/tcp_demo.kotoba','--target','aarch64-macos','--output','test.kseed','--source-path','/src','--source-lock','sources.ksl','--source-lock-sha256',sha(lock.read_bytes()))
 (work/'runner.kotoba').write_bytes(runner)
 mac.native_run(compiler,work,'compile','runner.kotoba','--target','aarch64-linux','--output','test.elf','--format','packed','--payload','test.kseed')
 (work/'test.elf').chmod(0o755);(work/'state').mkdir()
 return work

def run(work,expected):
 env={'KEXE_ALLOW':'35,38,43,44,45,46,47','KEXE_CAP_RESOURCES_35':'/work',
      'KEXE_CAP_RESOURCES_43':'127.0.0.1:47011','KEXE_CAP_RESOURCES_45':'127.0.0.1:47011',
      'KEXE_FUEL':'100000000000','KEXE_STRUCTURED_REPORT':'1','KEXE_SECCOMP':'if-available','KEXE_STACK_BYTES':'8388608'}
 cmd=['podman','run','--rm','--pull','never','--network','none','--platform','linux/arm64','-v',str(work)+':/work:rw']
 for k,v in env.items():cmd+=['-e',k+'='+v]
 result=subprocess.run(cmd+[image,'/work/test.elf','/work/state'],capture_output=True,text=True,timeout=600)
 if result.returncode or result.stderr or f':status :ok :result {expected} ' not in result.stdout:
  raise ValueError((work.name,result.returncode,result.stdout[-1000:],result.stderr[-1000:]))
 return result

good=build('good',sources);run(good,0)
needle=b'(id/verify-payload (g-tail v2) h2 (g-want-i))'
if base.count(needle)!=1:raise ValueError('identity guard anchor')
mutant=dict(sources);mutant['noise/tcp_demo.kotoba']=base.replace(needle,b'(id/verify-payload (g-tail v2) h2 (g-want-r))')
bad=build('wrong-peer',mutant);run(bad,1)
old='fleet-checkpoint/v1\n0\n'+'1'*64+'\n'+'0'*64+'\n'+'did:key:z6MktwupdmLXVVqTzCw4i46r4uGyosGXRnR3XjN4Zq7oMMsw\n'
if (bad/'state/fleet.state').read_text()!=old:raise ValueError('untrusted peer changed checkpoint')
needle=b'(t/send-frame c (g-tail o3))'
if base.count(needle)!=1:raise ValueError('ciphertext anchor')
mutant=dict(sources);mutant['noise/tcp_demo.kotoba']=base.replace(needle,b'(t/send-frame c (vector-alloc 16))')
corrupt=build('bad-ciphertext',mutant);run(corrupt,1)
if (corrupt/'state/fleet.state').read_text()!=old:raise ValueError('corrupt ciphertext changed checkpoint')
evidence={'status':'PASS_FLEET_NOISE_NATIVE_SYNTHETIC','compilerSha256':sha(compiler.read_bytes()),'runnerSourceSha256':sha(runner),
 'builderSha256':sha(Path(__file__).read_bytes()),'driverSha256':sha(driver),'image':image_info,
 'sources':{k:sha(v) for k,v in sorted(original.items())},'stagedEntrySha256':sha(base),
 'kseedSha256':sha((good/'test.kseed').read_bytes()),'elfSha256':sha((good/'test.elf').read_bytes()),
 'cases':['XXhfs mutual fixture identity and handshake hash','encrypted signed successor committed',
          'bad signed record rejected while receive nonce advances','ciphertext replay refused without state change',
          'wrong expected peer identity prevents checkpoint update', 'corrupt ciphertext prevents checkpoint update'],
 'scope':'one Linux ARM process with loopback sockets and synthetic deterministic test keys; no real fleet trust, multi-host interoperability, constant-time or production qualification'}
(out/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
print('PASS_FLEET_NOISE_NATIVE_SYNTHETIC',flush=True)
