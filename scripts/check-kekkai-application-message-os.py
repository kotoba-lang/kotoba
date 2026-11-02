#!/usr/bin/env python3
"""Full1MiB native application schema diagnostic; public vectors, no effects.

Native Amu discovers/checks/compiles/packages. Python stages immutable fixtures
and compares independent full-byte expectations. GDB writes only receipt ACKs.
"""
import argparse,gzip,hashlib,importlib.util,json,shutil,socket,struct,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COMPILER_SHA='efec34486903fc189eb9e3a6d45e02edeaa7f7edf73a9e3e12586c8de048b225'
BASELINE_SHA='4f4b0fe1566d6cb5081be6bea3f82e156c1f257d9767b4b010423d1374d2fe53'
FAULTS={
 'duplicate':('(not= (bit-and mask (i64-shift-left 1 (- kind 1))) 0)','false'),
 'padbits':('(= (mod previous 16) 0)','true'),
 'header':('(= (bit-and allowed bit) 0)','false'),
 'wipe':('(do (zero work 0) result)','(do result)'),
 'limit':('(<= count 1048576)','(<= count 65536)'),
}
def digest(raw):return hashlib.sha256(raw).hexdigest()
def pin(p):
 raw=p.read_bytes();return dict(bytes=len(raw),sha256=digest(raw))
def load(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main(a):
 if not __debug__:raise RuntimeError('assertions must remain enabled')
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);stage=out/'source';stage.mkdir()
 report=dict(schema='kekkai.native-application-message.v1',state='STAGING',fault=a.fault,calls=[],checkpoints=[],observationFailures=[],
  physicalDeployment=False,appInstalled=False,serviceExecution=False,trustedConsent=False,nativeSSH=False,releaseQualified=False,userCodeExecuted=False)
 def save():(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
 save();q=c=gdb=None
 try:
  amu=a.amu_source.resolve(strict=True);B=a.baseline.resolve(strict=True)
  assert pin(B/'receipt.json')['sha256']==BASELINE_SHA
  baseline=json.loads((B/'receipt.json').read_text());assert baseline['state']=='PASS_NATIVE_OS_APPLICATION_FRAME' and baseline['cases']['count']==113 and len(baseline['sourceGraph'])==17
  helper=amu/'scripts/seed/check-aiueos-user-macos-native.py';qmp=amu/'scripts/seed/check-aiueos-application-pool-macos-native.py';gdbfile=ROOT/'scripts/check-kekkai-application-reassembly-os.py'
  m,pool,dbg=load('schema_mac',helper),load('schema_qmp',qmp),load('schema_gdb',gdbfile)
  assert m.verify_macho(a.compiler)==dict(bytes=3826784,sha256=COMPILER_SHA)
  assert pin(a.qemu)['sha256']==a.qemu_sha256 and pin(a.firmware)['sha256']==a.firmware_sha256
  report.update(observer=pin(Path(__file__)),compiler=pin(a.compiler),compilerProfile='pool-v4-main-2f842',baselineReceipt=pin(B/'receipt.json'),qemu=pin(a.qemu),firmware=pin(a.firmware),nativeHelpers={str(p.relative_to(amu)):pin(p) for p in [helper,qmp]},gdbObserver=pin(gdbfile))
  for v,sha in baseline['sourceGraph'].items():
   source=B/'source'/v.lstrip('/');assert pin(source)['sha256']==sha;target=stage/v.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
  overlays={
   '/json-owner/kotoba/json/document_region.kotoba':'lib/kotoba.json/src/kotoba/json/document_region.kotoba',
   '/application-owner/kekkai/application_message_region.kotoba':'lib/kotoba.kekkai/kotoba/kekkai/application_message_region.kotoba',
   '/application-owner/kekkai/application_message_gate.kotoba':'lib/kotoba.kekkai/tools/application_message_gate.kotoba'}
  for v,rel in overlays.items():
   target=stage/v.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,target)
  if a.fault:
   p=stage/'application-owner/kekkai/application_message_region.kotoba';text=p.read_text();before,after=FAULTS[a.fault];assert text.count(before)==1;(p).write_text(text.replace(before,after))
  gate=stage/'application-owner/kekkai/application_frame_gate.kotoba';text=gate.read_text();before='[kotoba.edn.region :as e])';assert text.count(before)==1
  text=text.replace(before,'[kotoba.edn.region :as e] [kekkai.application-message-gate :as msg])')
  before='(work-zero 0) (check (work-matches 0 0)) (p 76 1)';assert text.count(before)==1
  gate.write_text(text.replace(before,'(work-zero 0) (check (work-matches 0 0)) (msg/run-tests) (p 76 1)'))
  for n in ['boot-font.bin','boot-user-slot.bin']:shutil.copyfile(B/'source'/n,stage/n)
  refpath=ROOT/'lib/kotoba.kekkai/tools/application_message_reference.py';shutil.copyfile(refpath,out/'public_reference.py');ref=load('schema_public',out/'public_reference.py');blob,cases,public=ref.packed()
  font=bytearray((stage/'boot-font.bin').read_bytes());assert not any(font[475136:475136+len(blob)]);font[475136:475136+len(blob)]=blob;(stage/'boot-font.bin').write_bytes(font)
  flags=next(row['argv'][:-2] for row in baseline['calls'] if row['argv'][0]=='compile' and row['argv'][-1]=='KERNEL.ELF');flags[3]='x86_64-aiueos-kernel-v4';roots=flags[8:flags.index('--source-lock')]
  for root in roots[1::2]:(stage/root.lstrip('/')).mkdir(parents=True,exist_ok=True)
  report.update(productionSources={rel:pin(ROOT/rel) for rel in overlays.values()},reference=pin(refpath),fixture=dict(bytes=len(blob),sha256=digest(blob),cases=public),bootFont=pin(stage/'boot-font.bin'),userSlot=pin(stage/'boot-user-slot.bin'),retained113=True,retainedCursorGuards=12)
  def run(label,args):
   try:p=m.native_run(a.compiler,stage,*args)
   except ValueError:p=m.native_run(a.compiler,stage,*args,expected=1)
   (out/(label+'.stdout')).write_bytes(p.stdout);(out/(label+'.stderr')).write_bytes(p.stderr);report['calls'].append(dict(label=label,argv=args,exit=p.returncode));save()
   if p.returncode:raise RuntimeError('native command failed: '+label)
   return p.stdout
  raw=run('modules',['modules',flags[1],*roots]);graph={}
  for line in raw.decode().splitlines():
   ns,v=line.split(' ',1);assert ns and v.startswith('/') and v not in graph;graph[v]=pin(stage/v.lstrip('/'))['sha256']
  assert len(graph)==20
  assert all(graph[k]==v for k,v in baseline['sourceGraph'].items() if k!='/application-owner/kekkai/application_frame_gate.kotoba')
  lock=('KSL1\nentry '+flags[1]+'\n'+''.join('root '+v+'\n' for v in roots[1::2])+''.join('file '+v+' '+k+'\n' for k,v in sorted(graph.items()))).encode();(stage/'schema.ksl').write_bytes(lock);flags[-3]='schema.ksl';flags[-1]=digest(lock)
  report.update(sourceGraph=graph,sourceLock=pin(stage/'schema.ksl'));save()
  for name in ['kernel.elf','kernel-repeat.elf']:run(name,[*flags,'--output',name])
  assert pin(stage/'kernel.elf')==pin(stage/'kernel-repeat.elf')
  for name in ['boot.efi','boot-repeat.efi']:run(name,['package-aiueos-boot','kernel.elf','--output',name,'--font','boot-font.bin','--user-slot','boot-user-slot.bin','--pci-resources','v1'])
  assert pin(stage/'boot.efi')==pin(stage/'boot-repeat.efi')
  raw=(stage/'kernel.elf').read_bytes();ph=struct.unpack_from('<Q',raw,32)[0];assert struct.unpack_from('<H',raw,56)[0]==2
  rx,rw=[struct.unpack_from('<IIQQQQQQ',raw,ph+i*56) for i in range(2)]
  assert rx[:5]==(1,5,4096,0x101000,0x101000) and rx[5]==rx[6]<=2097152-4096
  assert rw[:5]==(1,6,3145728,0x400000,0x400000) and rw[5]==rw[6]==0x240000
  assert pin(stage/'boot.efi')['bytes']<=7247872
  directory=out/'qemu';(directory/'esp/EFI/BOOT').mkdir(parents=True);shutil.copyfile(stage/'boot.efi',directory/'esp/EFI/BOOT/BOOTX64.EFI')
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  cmd=[str(a.qemu),'-machine','q35,accel=tcg,i8042=off','-cpu','max,phys-bits=37','-m','128M','-smp','1','-drive',f'if=pflash,format=raw,readonly=on,file={a.firmware}','-drive','file=fat:rw:esp,format=raw','-boot','order=c','-nic','none','-display','none','-no-reboot','-no-shutdown','-serial','file:serial.log','-debugcon','file:debug.log','-gdb',f'tcp:127.0.0.1:{port}','-qmp','stdio']
  report.update(state='EXECUTING',kernel=pin(stage/'kernel.elf'),efi=pin(stage/'boot.efi'),layout=dict(rx=rx,rw=rw),command=cmd);save()
  with (directory/'qemu.stderr').open('wb') as err:q=subprocess.Popen(cmd,cwd=directory,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,bufsize=0)
  c=pool.QMP(q);gdb=dbg.GDB(port);until=time.monotonic()+a.execution_seconds;phase=0
  if not c.call('query-status')['running']:c.call('cont')
  while time.monotonic()<until:
   assert q.poll() is None,'QEMU exited'
   private=c.dump(0x400000,65536,directory,'private-last.bin');scratch=struct.unpack_from('<Q',private,272)[0];row=c.dump(scratch,4096,directory,'receipt-last.bin') if scratch else bytes(4096)
   if struct.unpack_from('<Q',row)[0]==0x3154534d4b:
    values=struct.unpack_from('<10Q',row);current=values[5]
    if current>phase:
     assert current==phase+1;c.call('stop');index=values[8];assert index==phase;case=cases[index]
     base,size,ready=struct.unpack_from('<3Q',private,33536);assert base==values[4] and size==8388608 and ready==pool.MARKER
     assert base>=0x1000000 and base%4096==0 and base+size<=2**32
     caller=values[9];context=c.dump(0x63a000,8192,directory,'context-last.bin');assert caller==struct.unpack_from('<Q',context,400)[0] and 0x400000<=caller and caller+262144<=0x640000 and caller%4096==0
     expected_input=case['raw']+b' '*(1048576-len(case['raw']))+b'Z'
     expected_work=bytes(8192) if case['processed'] else bytes([165])*8192
     expected_work+=bytes([165]);expected_out=bytearray(bytes([165])*65537)
     if case['record'] is not None:
      rec=bytearray(case['record']);struct.pack_into('<Q',rec,16,base);expected_out[:4096]=rec
     result=dict(phase=current,label=case['label'],nativeResult=struct.unpack_from('<q',row,56)[0],expectedResult=case['expected'],nativeErrors=values[1],snapshots={})
     for label,address,expected in [('input',base,expected_input),('work',caller+122880,expected_work),('output',caller+139264,bytes(expected_out))]:
      actual=c.dump(address,len(expected),directory,label+'-last.bin');compressed=gzip.compress(actual,mtime=0);assert gzip.decompress(compressed)==actual
      name=f'phase-{current:03d}-{label}.bin.gz';(directory/name).write_bytes(compressed)
      rowresult=dict(actual=dict(bytes=len(actual),sha256=digest(actual)),expected=dict(bytes=len(expected),sha256=digest(expected)),match=actual==expected,compressed=dict(name=name,**pin(directory/name)))
      result['snapshots'][label]=rowresult
      if actual!=expected:report['observationFailures'].append(dict(phase=current,label=case['label'],region=label,firstDifferent=next(i for i,(x,y) in enumerate(zip(actual,expected)) if x!=y)))
     report['checkpoints'].append(result);save();gdb.ack_checkpoint(scratch+48,current);phase=current;c.call('cont');print('checkpoint',phase,case['label'],result['nativeResult'],len(report['observationFailures']),flush=True)
    context=c.dump(0x63a000,8192,directory,'context-last.bin');words=struct.unpack_from('<6I',context,74*4)
    if values[3]==2 and words[-1]==2:break
   assert c.call('query-status')['running'];time.sleep(.02)
  else:raise TimeoutError('native schema corpus incomplete')
  c.call('stop');row=c.dump(scratch,4096,directory,'receipt.bin');values=struct.unpack_from('<10Q',row);context=c.dump(0x63a000,8192,directory,'context.bin');words=struct.unpack_from('<6I',context,74*4)
  assert words==(113,0,1,1,113,2),words
  assert struct.unpack_from('<3I',context,91*4)==(1,12,0)
  old_owner,old_caller=struct.unpack_from('<2Q',context,400)
  assert c.dump(old_owner,8192,directory,'old-work.bin')==bytes(8192)
  pairs=c.dump(old_caller+196608,113*16,directory,'old-returns.bin');assert all(x==y for x,y in struct.iter_unpack('<qq',pairs))
  hashes=c.dump(old_caller+229376,113*32,directory,'old-hashes.bin');assert hashes==bytes.fromhex(''.join(baseline['cases']['expectedHashes']))
  assert c.dump(old_caller+163840,113*4,directory,'old-assertions.bin')==bytes(113*4)
  assert values[3]==2 and phase==len(cases)
  failed=values[1]>0 or bool(report['observationFailures']);assert failed==bool(a.fault),('mutation not normally detected' if a.fault else 'native/independent assertions failed',values,report['observationFailures'])
  report.update(state='DETECTED_NATIVE_MESSAGE_FAULT' if a.fault else 'PASS_NATIVE_APPLICATION_MESSAGE',normalCompletion=True,nativeErrors=values[1],nativeChecks=values[2],cases=len(cases),cursorGuards=12,retainedKnownAnswers=True,oldABIAndRuntimeRetained=True,fullMessageBytes=1048576,pendingRequestLimitNotChanged=256,poolBase=values[4]);save();print(report['state'],values[1],values[2],flush=True)
 except BaseException as error:report.update(state='FAILED',failure=str(error));save();raise
 finally:
  if q is not None and q.poll() is None:
   try:c.call('quit')
   except Exception:q.terminate()
   q.wait(timeout=10)
  if gdb is not None:gdb.close()

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['amu-source','compiler','baseline','qemu','firmware','output']:p.add_argument('--'+name,type=Path,required=True)
 for name in ['qemu-sha256','firmware-sha256']:p.add_argument('--'+name,required=True)
 p.add_argument('--execution-seconds',type=int,default=1200);p.add_argument('--fault',choices=list(FAULTS));main(p.parse_args())
