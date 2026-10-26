#!/usr/bin/env python3
"""Observe complete native live graphs, user entry, media and desktop on x86."""
import hashlib,json,os,platform,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;OUT=Path(os.environ['RUNNER_TEMP']);AMU=ROOT/'.native-inputs/amu'
assert platform.system()=='Linux' and platform.machine()=='x86_64'
qemu=shutil.which('qemu-system-x86_64');firmware=Path('/usr/share/OVMF/OVMF_CODE_4M.fd');assert qemu and firmware.is_file()
calls=[]
def run(name,args,env=None,timeout=1800):
 r=subprocess.run(list(map(str,args)),env=env or os.environ,capture_output=True,timeout=timeout)
 (OUT/(name+'.stdout')).write_bytes(r.stdout);(OUT/(name+'.stderr')).write_bytes(r.stderr)
 calls.append(dict(name=name,exit=r.returncode));(OUT/'native-live-calls.json').write_text(json.dumps(calls,indent=2)+'\n')
 assert not r.returncode and not r.stderr,(name,r.returncode,r.stderr[-2000:]);print(name,'PASS',flush=True)
def build(name,entry):
 env=dict(os.environ,AIUEOS_NATIVE_KERNEL_SOURCE=str(ROOT/'os/aiueos/native'/entry),AIUEOS_NATIVE_OUT=str(OUT/name),AIUEOS_NATIVE_FUEL='1000000')
 run('build-'+name,[sys.executable,HERE/'build-native-kernel.py',AMU],env)
 state=json.loads((OUT/name/'build-state.json').read_text())
 assert state['sourceModuleCount']=={'value-context':9,'value-call':27,'user-entry':27}[name]
 assert state['sourceGraph'][-1]['path'].endswith('/'+entry)
 return OUT/name
for name,entry,flag,count in [('value-context','value-context-v2-probe.kotoba','--value-context',12),('value-call','value-call-gate-probe.kotoba','--value-call',16)]:
 guest=build(name,entry);output=OUT/('qemu-'+name)
 run('qemu-'+name,[sys.executable,AMU/'scripts/seed/check-aiueos-entry-qemu.py','--efi',guest/'BOOTX64.EFI','--kernel',guest/'KERNEL.ELF','--qemu',qemu,'--firmware',firmware,'--output',output,flag],timeout=240)
 result=json.loads((output/'entry-qemu.json').read_text());key='valueContext' if count==12 else 'valueCall';assert result[key]['checks']==[1]*count
user=build('user-entry','user-entry-probe.kotoba')
for mode in range(8):
 run('qemu-user-'+str(mode),[sys.executable,AMU/'scripts/seed/check-aiueos-user-qemu.py','--efi',user/'BOOTX64.EFI','--kernel',user/'KERNEL.ELF','--qemu',qemu,'--firmware',firmware,'--output',OUT/('qemu-user-'+str(mode)),'--mode',str(mode)],timeout=240)
desktop=OUT/'native-desktop'
run('build-desktop',[sys.executable,HERE/'build-native-desktop.py','--amu-source',AMU,'--output',desktop],timeout=3600)
run('qemu-desktop',[sys.executable,HERE/'check-native-desktop-qemu.py','--efi',desktop/'kernel/BOOTX64.EFI','--kernel',desktop/'kernel/KERNEL.ELF','--media',desktop/'media/awai-native.img','--font',desktop/'font/aiueos-padded.fnt','--qemu',qemu,'--firmware',firmware,'--output',OUT/'qemu-desktop'],timeout=1200)
# Raw GPT boot is exercised by the desktop with the exact packaged image.
report=dict(status='PASS_NATIVE_X86_LIVE_MEDIA_DESKTOP',calls=calls,nativeCompiler=True,guestEmulation='QEMU TCG',valueContextChecks=12,typedCallChecks=16,userEntryCases=8,mediaNegativeControls=11,privateDesktopPageTables=True,BrowserCSSOMParity=False,dappsExecuted=False,preemptiveScheduler=False,physicalHardware=False,nativeController='separate pinned Amu exact-head CI')
(OUT/'native-live-ci.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
