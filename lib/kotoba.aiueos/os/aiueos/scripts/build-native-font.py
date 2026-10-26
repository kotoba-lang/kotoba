#!/usr/bin/env python3
"""Stage the licensed font and observe native copying/padding; emit no font."""
import argparse,hashlib,json,os,platform,shutil,struct,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
def pin(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def main(amu,compiler,expected,font,out):
 assert platform.system()=='Linux' and platform.machine() in ('aarch64','arm64','x86_64')
 assert pin(compiler)['sha256']==expected
 out.mkdir(parents=True,exist_ok=False);original=pin(font);shutil.copy2(font,out/'original.fnt')
 parts=[amu/'seed/00-ns-static.kotoba',amu/'seed/01-mem.kotoba',amu/'seed/02-io.kotoba',HERE.parent/'native/font-pad.kotoba']
 source=out/'font-pad.kotoba';source.write_bytes(b''.join(p.read_bytes()+b'\n' for p in parts))
 target='x86_64-linux' if platform.machine()=='x86_64' else 'aarch64-linux';tool=out/'font-pad.elf'
 # KEXE_SECCOMP opt-in passes through when the caller sets it: the hardened
 # runtime fails closed with `kexe-runtime: resource limit setup failed` on a
 # host whose seccomp(2) is unavailable (measured 2026-10-26 in an emulated
 # container); a native Linux host never sets it and behaves exactly as before.
 _kexe = {'KEXE_SECCOMP': os.environ['KEXE_SECCOMP']} if os.environ.get('KEXE_SECCOMP') else {}
 env=dict(PATH='/nonexistent',KEXE_CAP_RESOURCES_35=str(out),KEXE_STACK_BYTES='8388608',**_kexe);calls=[]
 for name,args in [('compile',[compiler,'compile',source,'--target',target,'--output',tool,'--format','static']),('pad',[tool,out/'original.fnt',out/'aiueos-padded.fnt'])]:
  if name=='pad':tool.chmod(0o755)
  r=subprocess.run(list(map(str,args)),env=env,capture_output=True,timeout=300)
  (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
  calls.append(dict(name=name,exit=r.returncode));(out/'calls.json').write_text(json.dumps(calls,indent=2)+'\n')
  assert not r.returncode and not r.stderr,(name,r.returncode,r.stderr)
 raw=font.read_bytes();padded=(out/'aiueos-padded.fnt').read_bytes();magic,version,n,reserved=struct.unpack_from('<4I',raw)
 assert magic==0x46554941 and version==1 and reserved==0 and len(raw)==16+n*36 and 0<n<=14563
 cps=[struct.unpack_from('<I',raw,16+i*4)[0]&0xffffff for i in range(n)]
 assert cps==sorted(set(cps)) and 0xfffd in cps
 assert len(padded)==524288 and padded[:len(raw)]==raw and padded[len(raw):]==bytes(524288-len(raw)) and pin(font)==original
 report=dict(status='PASS_NATIVE_FONT_PAD',original=original,padded=pin(out/'aiueos-padded.fnt'),compiler=pin(compiler),tool=pin(tool),sourceUnity=pin(source),glyphs=n,nativeFormatEmission=True,PythonFormatEmission=False)
 (out/'native-font.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['amu-source','compiler','font','output']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--compiler-sha256',required=True);a=p.parse_args();main(a.amu_source.resolve(),a.compiler.resolve(),a.compiler_sha256,a.font.resolve(),a.output.resolve())
