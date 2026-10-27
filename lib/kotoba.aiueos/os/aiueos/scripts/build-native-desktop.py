#!/usr/bin/env python3
"""Orchestrate native font, complete locked kernel, EFI and diagnostic media."""
import argparse,hashlib,importlib.util,json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
# The native desktop polls for its entire session. The previous 2^30 fuel
# budget was observed to expire during ordinary interactive use (AIUEOS #506).
DESKTOP_FUEL=9007199254740991
def main(amu,out,*,profile='desktop',distribution='aiueos'):
 # Distribution selects static composition metadata, never a kernel fork,
 # runtime profile, admission decision or automatic component installation.
 if distribution not in ('aiueos','awai'):raise ValueError('unknown distribution: '+distribution)
 descriptor=HERE.parents[2]/'distributions'/distribution/'distribution.json'
 descriptor_bytes=descriptor.read_bytes()
 out.mkdir(parents=True,exist_ok=False)
 (out/'distribution.json').write_bytes(descriptor_bytes)
 spec=importlib.util.spec_from_file_location('native_kernel',HERE/'build-native-kernel.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
 compiler,digest=driver.select_native_compiler(amu);env=dict(os.environ,AIUEOS_AMU_SELFHOST_BIN=str(compiler),AIUEOS_AMU_SELFHOST_SHA256=digest)
 calls=[]
 def run(name,args,custom=env):
  r=subprocess.run([sys.executable,*map(str,args)],env=custom,capture_output=True,timeout=10800)
  (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr);calls.append(dict(name=name,exit=r.returncode));(out/'calls.json').write_text(json.dumps(calls,indent=2)+'\n')
  assert not r.returncode and not r.stderr,(name,r.returncode,r.stderr[-2000:]);print(name,'PASS',flush=True)
 font=out/'font/aiueos-padded.fnt';kernel=out/'kernel';media=out/'media'
 run('font',[HERE/'build-native-font.py','--amu-source',amu,'--compiler',compiler,'--compiler-sha256',digest,'--font',HERE.parent/'fonts/aiueos-16.fnt','--output',out/'font'])
 entry='workspace-entry.kotoba' if profile=='local-draft' else 'desktop-entry.kotoba'
 env.update(AIUEOS_NATIVE_OUT=str(kernel),AIUEOS_NATIVE_KERNEL_SOURCE=str(HERE.parent/'native'/entry),AIUEOS_NATIVE_FUEL=str(DESKTOP_FUEL),AIUEOS_NATIVE_BOOT_PAYLOAD=str(font),AIUEOS_NATIVE_BOOT_PAYLOAD_SHA256=hashlib.sha256(font.read_bytes()).hexdigest())
 run('kernel',[HERE/'build-native-kernel.py',amu])
 run('media',[HERE/'build-native-media.py','--amu-source',amu,'--compiler',compiler,'--compiler-sha256',digest,'--efi',kernel/'BOOTX64.EFI','--output',media])
 state=json.loads((kernel/'build-state.json').read_text());assert state['state']=='NATIVE_IMAGE_CANDIDATE' and state['sourceModuleCount']==31
 result=dict(schema='aiueos.native-desktop-candidate.v1',state='NATIVE_DESKTOP_MEDIA_CANDIDATE',profile=profile,localDraftCandidate=profile=='local-draft',D2WorkspaceCodec=False,signedHeadAuthority=False,kernel=state['images'][0],efi=state['efiImages'][0],media=json.loads((media/'native-media.json').read_text())['image'],font=json.loads((out/'font/native-font.json').read_text())['padded'],compiler=state['compiler'],sourceModuleCount=31,kernelFuelInitial=DESKTOP_FUEL,JVMNodeOrGraalFallback=False,cCompilerOrLoader=False,guestBoot=False,desktopInput=False,BrowserCSSOMParity=False,dappsExecuted=False,physicalHardware=False)
 result['distribution']=dict(id=distribution,descriptor=dict(path='distribution.json',bytes=len(descriptor_bytes),sha256=hashlib.sha256(descriptor_bytes).hexdigest()))
 (out/'native-desktop.json').write_text(json.dumps(result,indent=2)+'\n');print(result['state'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--amu-source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--profile',choices=['desktop','local-draft'],default='desktop');p.add_argument('--distribution',choices=['aiueos','awai'],default='aiueos');a=p.parse_args();main(a.amu_source.resolve(),a.output.resolve(),profile=a.profile,distribution=a.distribution)
