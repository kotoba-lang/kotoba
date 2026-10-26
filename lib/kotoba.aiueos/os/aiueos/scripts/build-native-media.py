#!/usr/bin/env python3
"""Stage/hash/observe only. Kotoba emits the GPT/FAT16 diagnostic media."""
import argparse
import hashlib
import importlib.util
import os
import json
from pathlib import Path
import platform
import shutil
import struct
import subprocess

HERE=Path(__file__).resolve().parent
def pin(path):
 b=path.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())

def main(amu,compiler,expected,efi,out):
 assert platform.system()=='Linux' and platform.machine() in ('aarch64','arm64','x86_64')
 assert pin(compiler)['sha256']==expected,'compiler pin drift'
 out.mkdir(parents=True,exist_ok=False);shutil.copy2(efi,out/'BOOTX64.EFI');original=pin(efi);local=out/'BOOTX64.EFI'
 machine=183 if platform.machine() in ('aarch64','arm64') else 62
 assert compiler.read_bytes()[:4]==b'\x7fELF' and struct.unpack_from('<H',compiler.read_bytes(),18)[0]==machine
 parts=[amu/'seed/00-ns-static.kotoba',amu/'seed/01-mem.kotoba',amu/'seed/02-io.kotoba',HERE.parent/'native/media-builder.kotoba']
 source=out/'media.kotoba';source.write_bytes(b''.join(p.read_bytes()+b'\n' for p in parts))
 # KEXE_SECCOMP opt-in passes through when the caller sets it (seccomp-less
 # hosts, measured 2026-10-26); native Linux is unchanged without it.
 _kexe = {'KEXE_SECCOMP': os.environ['KEXE_SECCOMP']} if os.environ.get('KEXE_SECCOMP') else {}
 env=dict(PATH='/nonexistent',KEXE_ALLOW='35,37,38,39',KEXE_CAP_RESOURCES_35=str(out),KEXE_STACK_BYTES='8388608',**_kexe)
 calls=[]
 def run(name,args,expected_exit=0,custom=None):
  r=subprocess.run(list(map(str,args)),env=custom or env,capture_output=True,timeout=300)
  (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
  calls.append(dict(name=name,exit=r.returncode,stdout=hashlib.sha256(r.stdout).hexdigest(),stderr=hashlib.sha256(r.stderr).hexdigest()))
  (out/'calls.json').write_text(json.dumps(calls,indent=2)+'\n')
  assert r.returncode==expected_exit,(name,r.returncode,r.stderr[-1000:])
  if expected_exit==0:assert not r.stderr,(name,r.stderr)
  return r
 tool=out/'media.elf';target='aarch64-linux' if machine==183 else 'x86_64-linux'
 run('compile',[compiler,'compile',source,'--target',target,'--output',tool,'--format','static']);tool.chmod(0o755)
 def invoke(name,operation,image,expected_exit=0,input_efi=local,custom=None):
  return run(name,[tool,operation,input_efi,image,original['sha256'],str(input_efi.stat().st_size)],expected_exit,custom)
 disk=out/'awai-native.img';again=out/'awai-native.reproduced.img'
 invoke('build','build',disk);invoke('verify','verify',disk);invoke('reproduce','build',again)
 assert pin(disk)==pin(again)
 invoke('existing-output-refused','build',disk,1);assert pin(disk)==pin(again)
 spec=importlib.util.spec_from_file_location('media_reader',HERE/'check-native-media-format.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
 independent=reader.verify(disk,local);raw=disk.read_bytes()
 offsets={'primary-gpt':512+24,'backup-gpt':len(raw)-512+24,'fat-mirror':1049088+4,'fat-chain-both':1049088+8,'directory-name':1122816+576,'efi-content':1123840+512}
 for name,offset in offsets.items():
  corrupted=bytearray(raw);corrupted[offset]^=1
  if name=='fat-chain-both':corrupted[offset+28672]^=1
  path=out/(name+'.img');path.write_bytes(corrupted);invoke(name,'verify',path,1)
  try:reader.verify(path,local)
  except (AssertionError,ValueError,struct.error):pass
  else:raise AssertionError('independent reader accepted '+name)
 for name,data in [('truncated',raw[:-1]),('trailer',raw+b'\0')]:
  path=out/(name+'.img');path.write_bytes(data);invoke(name,'verify',path,1)
 alternate=out/'wrong-expected.EFI';wrong=bytearray(local.read_bytes());wrong[-1]^=1;alternate.write_bytes(wrong)
 invoke('wrong-expected-efi','verify',disk,1,alternate)
 denied={**env,'KEXE_ALLOW':'37,38,39'}
 refused=invoke('no-fs-grant','verify',disk,120,custom=denied)
 assert b':wire 35 :refused :not-granted' in refused.stderr
 assert pin(efi)==original and pin(local)==original and pin(disk)==pin(again)
 report=dict(status='PASS_NATIVE_GPT_FAT16_DIAGNOSTIC_MEDIA',host=[platform.system(),platform.machine()],compiler=pin(compiler),tool=pin(tool),sources={str(p.relative_to(amu)) if p.is_relative_to(amu) else 'aiueos/native/media-builder.kotoba':pin(p) for p in parts},sourceUnity=pin(source),efi=original,image=pin(disk),independent=independent,negativeControls=11,nativeFormatEmission=True,PythonFormatEmission=False,nativeCompilerExecution=True,JVMNodeOrGraalFallback=False,cCompilerOrLoader=False,guestBoot=False,desktopInput=False,installer=False,physicalHardware=False)
 (out/'native-media.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'])

if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['amu-source','compiler','efi','output']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--compiler-sha256',required=True);a=p.parse_args();main(a.amu_source.resolve(),a.compiler.resolve(),a.compiler_sha256,a.efi.resolve(),a.output.resolve())
