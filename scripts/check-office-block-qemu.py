#!/usr/bin/env python3
"""Exercise a dedicated synthetic office scratch disk in native QEMU.

Usage: script AMU_DIR COMPILER COMPILER_SHA256 QEMU FIRMWARE NEW_OUTPUT
The script creates every writable disk itself in NEW_OUTPUT. No user disk,
keys, office app, transactional journal, physical device or release is used.
"""
import hashlib,importlib.util,json,re,struct,subprocess,sys,time
from pathlib import Path
if len(sys.argv)!=7:raise SystemExit(__doc__)
amu,compiler=map(lambda x:Path(x).resolve(strict=True),sys.argv[1:3]);expected_compiler=sys.argv[3]
qemu,firmware=map(lambda x:Path(x).resolve(strict=True),sys.argv[4:6]);out=Path(sys.argv[6]).resolve()
if not re.fullmatch(r'[0-9a-f]{64}',expected_compiler):raise ValueError('explicit compiler SHA-256 required')
if out.exists():raise ValueError('output must be new')
out.mkdir(parents=True,mode=0o700);fixture=out/'fixture';(fixture/'aiueos/native').mkdir(parents=True)
root=Path(__file__).resolve().parents[1]/'lib/kotoba.aiueos'
paths={'aiueos/native/office_block_probe.kotoba':root/'os/aiueos/native/office_block_probe.kotoba','aiueos/office_block_probe_test.kotoba':root/'test/aiueos/office_block_probe_test.kotoba'}
sha=lambda b:hashlib.sha256(b).hexdigest()
if sha(compiler.read_bytes())!=expected_compiler:raise ValueError('compiler digest mismatch')
files={name:p.read_bytes() for name,p in paths.items()}
for name,data in files.items():(fixture/name).write_bytes(data)
entry='aiueos/office_block_probe_test.kotoba'
lock=('KSL1\nentry /fixture/'+entry+'\nroot /fixture\n'+''.join('file '+sha(data)+' /fixture/'+name+'\n' for name,data in sorted(files.items()))).encode();(out/'probe.ksl').write_bytes(lock)
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
mac=load('mac',amu/'scripts/seed/check-aiueos-user-macos-native.py');qmp_path=amu/'scripts/seed/check-aiueos-application-pool-macos-native.py';q=load('qmp',qmp_path)
compile_args=('compile','/fixture/'+entry,'--target','x86_64-aiueos-kernel-v4','--artifact','image','--fuel','9007199254740991','--source-path','/fixture','--source-lock','probe.ksl','--source-lock-sha256',sha(lock))
for name in ('kernel.elf','kernel-repeat.elf'):mac.native_run(compiler,out,*compile_args,'--output',name)
if (out/'kernel.elf').read_bytes()!=(out/'kernel-repeat.elf').read_bytes():raise ValueError('kernel build not reproducible')
for name in ('boot.efi','boot-repeat.efi'):mac.native_run(compiler,out,'package-aiueos-boot','kernel.elf','--output',name,'--pci-resources','v1')
if (out/'boot.efi').read_bytes()!=(out/'boot-repeat.efi').read_bytes():raise ValueError('boot package not reproducible')
kernel=(out/'kernel.elf').read_bytes();rw=struct.unpack_from('<IIQQQQQQ',kernel,120)
if rw[:2]!=(1,6) or rw[3]!=0x400000:raise ValueError('unexpected v4 kernel layout')
marker=struct.pack('<4I',0x4f4e5449,0x31464346,1,2048)
def disk(name,sectors,valid):
 p=out/name;data=bytearray(sectors*512)
 if valid:data[:len(marker)]=marker
 p.write_bytes(data);return p,bytes(data)
def run(name,disk_path,phase,boot=None):
 directory=out/name;(directory/'esp/EFI/BOOT').mkdir(parents=True);(directory/'esp/EFI/BOOT/BOOTX64.EFI').write_bytes((boot or out/'boot.efi').read_bytes())
 cmd=[str(qemu),'-machine','q35,accel=tcg','-cpu','max','-m','128M','-smp','1','-drive',f'if=pflash,format=raw,readonly=on,file={firmware}','-drive','file=fat:rw:esp,format=raw','-boot','order=c','-nic','none','-display','none','-no-reboot','-no-shutdown','-serial','file:serial.log','-debugcon','file:debug.log']
 if disk_path is not None:cmd+=['-device','isa-ide,id=office-test','-drive',f'file={disk_path},format=raw,if=none,id=office,cache=directsync','-device','ide-hd,drive=office,bus=office-test.0,unit=1,serial=OFFICEPROBE000001']
 cmd+=['-qmp','stdio']
 (directory/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
 with (directory/'qemu.stderr').open('wb') as err:
  proc=subprocess.Popen(cmd,cwd=directory,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,bufsize=0);qmp=None
  try:
   qmp=q.QMP(proc);deadline=time.monotonic()+180
   while time.monotonic()<deadline:
    if proc.poll() is not None:raise RuntimeError(name+' exited')
    context=qmp.dump(0x400000,65536,directory,'context.bin');scratch=struct.unpack_from('<Q',context,272)[0]
    row=qmp.dump(scratch,4096,directory,'receipt.bin') if scratch else bytes(4096)
    if struct.unpack_from('<Q',row)[0]==0x314b434f4c424f:
     qmp.call('stop');values=struct.unpack_from('<4Q',qmp.dump(scratch,4096,directory,'final.bin'))
     if values[1:]!=(phase,1,207):raise ValueError((name,values))
     return {'name':name,'phase':phase,'receipt':list(values)}
    if qmp.call('query-status')['status'] in ('shutdown','guest-panicked'):raise RuntimeError(name+' failed before receipt')
    time.sleep(.15)
   raise TimeoutError(name)
  finally:
   if proc.poll() is None:
    if qmp is not None:
     try:qmp.call('quit')
     except Exception:pass
    if proc.poll() is None:proc.terminate()
    proc.wait(timeout=10)
valid,original=disk('valid.img',2048,True)
first=run('write',valid,1);written=valid.read_bytes();expected=bytearray(original);struct.pack_into('<I',expected,512,0x314b424f)
for sector in list(range(8,215))+[2047]:
 for at in range(0,512,4):struct.pack_into('<I',expected,sector*512+at,((sector*128+at//4)^0xa55a19c3)&0xffffffff)
if written!=expected:raise ValueError('host readback differs from fixture')
second=run('cold-read',valid,2)
if valid.read_bytes()!=written:raise ValueError('read-only restart changed disk')
bad,before=disk('bad-marker.img',2048,False);refused=run('bad-marker',bad,3)
if bad.read_bytes()!=before:raise ValueError('bad marker changed disk')
reserved,before=disk('bad-reserved.img',2048,True)
bad_bytes=bytearray(before);bad_bytes[16]=1;reserved.write_bytes(bad_bytes);before=bytes(bad_bytes)
reserved_refused=run('bad-reserved',reserved,3)
if reserved.read_bytes()!=before:raise ValueError('bad reserved field changed disk')
large,before=disk('wrong-size.img',4096,True);size_refused=run('wrong-size',large,3)
if large.read_bytes()!=before:raise ValueError('wrong-sized disk changed')
absent=run('no-disk',None,3)
# Compile a real mutant that executes the marker check but ignores its result.
# On a fresh blank test disk the mutant must take the forbidden write path;
# the unmodified image above must refuse and leave the identical fixture intact.
mutant=out/'mutant';(mutant/'fixture/aiueos/native').mkdir(parents=True)
key='aiueos/native/office_block_probe.kotoba';anchor=b'(provisioned scratch)'
if files[key].count(anchor)!=2:raise ValueError('mutation anchor changed')
changed=dict(files);changed[key]=changed[key].replace(anchor,b'(>= (if (provisioned scratch) 1 0) 0)')
for name,data in changed.items():(mutant/'fixture'/name).write_bytes(data)
mlock=('KSL1\nentry /fixture/'+entry+'\nroot /fixture\n'+''.join('file '+sha(data)+' /fixture/'+name+'\n' for name,data in sorted(changed.items()))).encode();(mutant/'probe.ksl').write_bytes(mlock)
mac.native_run(compiler,mutant,'compile','/fixture/'+entry,'--target','x86_64-aiueos-kernel-v4','--artifact','image','--fuel','9007199254740991','--source-path','/fixture','--source-lock','probe.ksl','--source-lock-sha256',sha(mlock),'--output','kernel.elf')
mac.native_run(compiler,mutant,'package-aiueos-boot','kernel.elf','--output','boot.efi','--pci-resources','v1')
mutant_disk,mutant_before=disk('mutant-bad-marker.img',2048,False)
mutant_result=run('mutant-bad-marker',mutant_disk,1,mutant/'boot.efi')
if mutant_disk.read_bytes()==mutant_before:raise ValueError('marker-bypass mutant not detected')
report={'status':'PASS_OFFICE_BLOCK_QEMU_SYNTHETIC','observerSha256':sha(Path(__file__).read_bytes()),'qmpHelperSha256':sha(qmp_path.read_bytes()),'compilerSha256':sha(compiler.read_bytes()),'qemuSha256':sha(qemu.read_bytes()),'firmwareSha256':sha(firmware.read_bytes()),'sourceLockSha256':sha(lock),'sources':{n:sha(d) for n,d in files.items()},'kernelSha256':sha(kernel),'efiSha256':sha((out/'boot.efi').read_bytes()),'diskBytes':len(written),'diskSha256':sha(written),'checks':[first,second,refused,reserved_refused,size_refused,absent],'markerBypassControl':{'detected':True,'sourceSha256':sha(changed[key]),'kernelSha256':sha((mutant/'kernel.elf').read_bytes()),'receipt':mutant_result},'scope':'isolated synthetic QEMU block transport; not app execution, a transaction journal, real data, physical storage or release'}
(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
