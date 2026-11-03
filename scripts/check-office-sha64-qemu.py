#!/usr/bin/env python3
"""Cross-check bounded native SHA-256 in a synthetic QEMU kernel.

Usage: script AMU_DIR COMPILER COMPILER_SHA256 QEMU FIRMWARE NEW_OUTPUT
Only guest-owned RAM is used; no user data, disk, app or release is involved.
"""
import hashlib,importlib.util,json,re,struct,subprocess,sys,time
from pathlib import Path
if len(sys.argv)!=7:raise SystemExit(__doc__)
amu,compiler=map(lambda x:Path(x).resolve(strict=True),sys.argv[1:3]);expected=sys.argv[3];qemu,firmware=map(lambda x:Path(x).resolve(strict=True),sys.argv[4:6]);out=Path(sys.argv[6]).resolve()
if not re.fullmatch(r'[0-9a-f]{64}',expected):raise ValueError('compiler digest required')
sha=lambda b:hashlib.sha256(b).hexdigest()
if sha(compiler.read_bytes())!=expected:raise ValueError('compiler digest mismatch')
if out.exists():raise ValueError('output must be new')
out.mkdir(parents=True,mode=0o700);root=Path(__file__).resolve().parents[1]/'lib/kotoba.aiueos';fixture=out/'fixture';(fixture/'aiueos').mkdir(parents=True)
paths={'aiueos/sha256.kotoba':root/'os/aiueos/kotoba/aiueos/sha256.kotoba','aiueos/office_sha64_qemu_test.kotoba':root/'test/aiueos/office_sha64_qemu_test.kotoba'};files={n:p.read_bytes() for n,p in paths.items()}
for name,data in files.items():(fixture/name).write_bytes(data)
entry='aiueos/office_sha64_qemu_test.kotoba';lock=('KSL1\nentry /fixture/'+entry+'\nroot /fixture\n'+''.join('file '+sha(v)+' /fixture/'+n+'\n' for n,v in sorted(files.items()))).encode();(out/'probe.ksl').write_bytes(lock)
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
mac=load('mac',amu/'scripts/seed/check-aiueos-user-macos-native.py');qmp_path=amu/'scripts/seed/check-aiueos-application-pool-macos-native.py';q=load('qmp',qmp_path)
flags=('compile','/fixture/'+entry,'--target','x86_64-aiueos-kernel-v4','--artifact','image','--fuel','9007199254740991','--source-path','/fixture','--source-lock','probe.ksl','--source-lock-sha256',sha(lock))
for n in ('kernel.elf','kernel-repeat.elf'):mac.native_run(compiler,out,*flags,'--output',n)
if (out/'kernel.elf').read_bytes()!=(out/'kernel-repeat.elf').read_bytes():raise ValueError('kernel mismatch')
for n in ('boot.efi','boot-repeat.efi'):mac.native_run(compiler,out,'package-aiueos-boot','kernel.elf','--output',n,'--pci-resources','v1')
if (out/'boot.efi').read_bytes()!=(out/'boot-repeat.efi').read_bytes():raise ValueError('EFI mismatch')
kernel=(out/'kernel.elf').read_bytes();rw=struct.unpack_from('<IIQQQQQQ',kernel,120)
if rw[:2]!=(1,6) or rw[3]!=0x400000:raise ValueError('kernel layout')
d=out/'boot';(d/'esp/EFI/BOOT').mkdir(parents=True);(d/'esp/EFI/BOOT/BOOTX64.EFI').write_bytes((out/'boot.efi').read_bytes())
cmd=[str(qemu),'-machine','q35,accel=tcg','-cpu','max','-m','128M','-smp','1','-drive',f'if=pflash,format=raw,readonly=on,file={firmware}','-drive','file=fat:rw:esp,format=raw','-boot','order=c','-nic','none','-display','none','-no-reboot','-no-shutdown','-serial','file:serial.log','-debugcon','file:debug.log','-qmp','stdio'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
with (d/'qemu.stderr').open('wb') as err:
 proc=subprocess.Popen(cmd,cwd=d,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,bufsize=0);qmp=None
 try:
  qmp=q.QMP(proc);deadline=time.monotonic()+180
  while time.monotonic()<deadline:
   if proc.poll() is not None:raise RuntimeError('QEMU exited')
   ctx=qmp.dump(0x400000,65536,d,'context.bin');scratch=struct.unpack_from('<Q',ctx,272)[0];row=qmp.dump(scratch,4096,d,'receipt.bin') if scratch else bytes(4096)
   if struct.unpack_from('<Q',row)[0]==0x315445474944464f:
    qmp.call('stop');row=qmp.dump(scratch,4096,d,'final.bin');break
   if qmp.call('query-status')['status'] in ('shutdown','guest-panicked'):raise RuntimeError('guest stopped before receipt')
   time.sleep(.15)
  else:raise TimeoutError('hash probe')
 finally:
  if proc.poll() is None:
   if qmp is not None:
    try:qmp.call('quit')
    except Exception:pass
   if proc.poll() is None:proc.terminate()
   proc.wait(timeout=10)
if struct.unpack_from('<3Q',row,8)!=(1,1,1):raise ValueError('refusal or legacy parity failed')
input_bytes=bytes((i*17+123)&255 for i in range(65536));lengths=[0,1,55,56,63,64,65,1024,12288,35000,65536]
for i,n in enumerate(lengths):
 if row[64+i*32:96+i*32]!=hashlib.sha256(input_bytes[:n]).digest():raise ValueError('digest mismatch '+str(n))
report={'status':'PASS_OFFICE_SHA64_QEMU_SYNTHETIC','compilerSha256':sha(compiler.read_bytes()),'qemuSha256':sha(qemu.read_bytes()),'firmwareSha256':sha(firmware.read_bytes()),'observerSha256':sha(Path(__file__).read_bytes()),'qmpHelperSha256':sha(qmp_path.read_bytes()),'sourceLockSha256':sha(lock),'sources':{n:sha(v) for n,v in files.items()},'kernelSha256':sha(kernel),'efiSha256':sha((out/'boot.efi').read_bytes()),'lengths':lengths,'refusals':['negative-or-oversized-length','short-output','short-workspace','input-output-overlap','input-workspace-overlap','output-workspace-overlap'],'legacyParityLength':12288,'scope':'synthetic QEMU kernel memory; no user data, app execution, persistent storage or release'}
(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
