#!/usr/bin/env python3
"""Actual managed Noise ->256 pending requests: native full-byte/fault diagnostic.

Amu discovers/checks/compiles/packages. Python only stages pinned sources/public
fixtures and independently observes bytes. GDB acknowledges receipt checkpoints;
no protocol state, entropy, clock source, socket or consent is injected.
"""
from pathlib import Path
import argparse,json,importlib.util,hashlib,shutil,struct,socket,subprocess,time,gzip
R=Path(__file__).resolve().parents[1]
FAULTS={
 'channel':('(if (>= i 96) true (and (= (r64 o (+ 64 i))','(if (>= i 64) true (and (= (r64 o (+ 64 i))'),
 'capacity':('(>= (r o 8) 256)','(>= (r o 8) 128)'),
 'id':('(if (not (record-id-same o input count 258688)) -1','(if false -1'),
 'deadline':('(>= now (r64 o (+ (slot index) 24)))','(> now (r64 o (+ (slot index) 24)))'),
 'wipe':('(defn- finish [o result] :i64 (do (zero o 245760 262144) result))','(defn- finish [o result] :i64 result)')}
def pin(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def load(n,p):
 sp=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def main(a):
 if not __debug__:raise RuntimeError('assertions must remain enabled')
 A=a.amu_source.resolve(strict=True);B=a.baseline.resolve(strict=True);compiler=a.compiler.resolve(strict=True)
 m=load('pending_mac',A/'scripts/seed/check-aiueos-user-macos-native.py');pool=load('pending_qmp',A/'scripts/seed/check-aiueos-application-pool-macos-native.py');dbg=load('pending_gdb',R/'scripts/check-kekkai-application-reassembly-os.py')
 assert m.verify_macho(compiler)['sha256']=='efec34486903fc189eb9e3a6d45e02edeaa7f7edf73a9e3e12586c8de048b225'
 baseline=json.loads((B/'receipt.json').read_text());assert baseline['state']=='PASS_FULL_NATIVE_APPLICATION_RECEIVE' and pin(B/'receipt.json')['sha256']==a.baseline_sha256
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);stage=out/'source';stage.mkdir();report=dict(schema='kekkai.native-application-pending.v1',state='STAGING',fault=a.fault,physicalDeployment=False,installedApp=False,serviceExecution=False,trustedConsent=False,nativeSSH=False,releaseQualified=False,userELFExecuted=False,calls=[],checkpoints=[],compiler=pin(compiler),baseline=pin(B/'receipt.json'))
 def save():(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
 for v,sha in baseline['sourceGraph'].items():
  p=B/'source'/v.lstrip('/');assert pin(p)['sha256']==sha;t=stage/v.lstrip('/');t.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,t)
 for v,rel in [('/session-owner/kekkai/application_pending_region.kotoba','lib/kotoba.kekkai/kotoba/kekkai/application_pending_region.kotoba'),('/session-owner/kekkai/application_pending_gate.kotoba','lib/kotoba.kekkai/tools/application_pending_gate.kotoba'),('/session-owner/kekkai/application_message_region.kotoba','lib/kotoba.kekkai/kotoba/kekkai/application_message_region.kotoba')]:shutil.copyfile(R/rel,stage/v.lstrip('/'))
 flags=next(x['argv'][:-2] for x in baseline['calls'] if x['argv'][0]=='compile');roots=flags[8:flags.index('--source-lock')];entry=stage/flags[1].lstrip('/');entry.write_text(entry.read_text().replace('kekkai.application-receive-link-gate','kekkai.application-pending-gate'))
 for n in ['boot-font.bin','boot-user-slot.bin']:shutil.copyfile(B/'source'/n,stage/n)
 refpath=R/'lib/kotoba.kekkai/tools/application_pending_reference.py';shutil.copyfile(refpath,out/'public_reference.py');ref=load('pending_frozen_public',out/'public_reference.py')
 # The reference module resolves only its pinned public crypto fixtures below.
 public=out/'public-fixtures'
 for rel in ['lib/org.ietf.x25519/tools/reference.py','lib/org.ietf.chacha20Poly1305/tools/reference.py']:
  target=public/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/rel,target)
 ref.ROOT=public
 blob=ref.packed()
 report.update(observer=pin(Path(__file__)),reference=pin(refpath),nativeFixture=pin(R/'lib/kotoba.kekkai/tools/application_pending_gate.kotoba'),productionSources={rel:pin(R/rel) for rel in ['lib/kotoba.kekkai/kotoba/kekkai/application_pending_region.kotoba','lib/kotoba.kekkai/kotoba/kekkai/application_message_region.kotoba','lib/kotoba.json/src/kotoba/json/document_region.kotoba']},nativeHelpers={str(p.relative_to(A)):pin(p) for p in [A/'scripts/seed/check-aiueos-user-macos-native.py',A/'scripts/seed/check-aiueos-application-pool-macos-native.py']},gdbObserver=pin(R/'scripts/check-kekkai-application-reassembly-os.py'),publicCryptoSources={rel:pin(R/rel) for rel in ['lib/org.ietf.x25519/tools/reference.py','lib/org.ietf.chacha20Poly1305/tools/reference.py']})
 if a.fault:
  p=stage/'session-owner/kekkai/application_pending_region.kotoba';text=p.read_text();before,after=FAULTS[a.fault];assert text.count(before)==1;p.write_text(text.replace(before,after))
 font=bytearray((stage/'boot-font.bin').read_bytes());assert not any(font[393216+126000:393216+126000+len(blob)]);font[393216+126000:393216+126000+len(blob)]=blob;(stage/'boot-font.bin').write_bytes(font);channels=ref.public_channels(bytes(font));report.update(bootFont=pin(stage/'boot-font.bin'),userSlot=pin(stage/'boot-user-slot.bin'))
 def run(label,args):
  try:p=m.native_run(compiler,stage,*args)
  except ValueError:p=m.native_run(compiler,stage,*args,expected=1)
  (out/(label+'.stdout')).write_bytes(p.stdout);(out/(label+'.stderr')).write_bytes(p.stderr);report['calls'].append(dict(label=label,argv=args,exit=p.returncode));save();print(label,p.returncode,flush=True)
  if p.returncode:raise RuntimeError('native failed '+label)
  return p.stdout
 try:
  raw=run('modules',['modules',flags[1],*roots]);graph={}
  for line in raw.decode().splitlines():
   ns,v=line.split(' ',1);graph[v]=pin(stage/v.lstrip('/'))['sha256']
  lock=('KSL1\nentry '+flags[1]+'\n'+''.join('root '+v+'\n' for v in roots[1::2])+''.join('file '+v+' '+k+'\n' for k,v in sorted(graph.items()))).encode();(stage/'pending.ksl').write_bytes(lock);flags[-3]='pending.ksl';flags[-1]=hashlib.sha256(lock).hexdigest();report['sourceGraph']=graph
  assert len(graph)==37
  assert all(graph[k]==v for k,v in baseline['sourceGraph'].items() if k in graph and k!=flags[1])
  for name in ['kernel.elf','kernel-repeat.elf']:run(name,[*flags,'--output',name])
  assert pin(stage/'kernel.elf')==pin(stage/'kernel-repeat.elf')
  for name in ['boot.efi','boot-repeat.efi']:run(name,['package-aiueos-boot','kernel.elf','--output',name,'--font','boot-font.bin','--user-slot','boot-user-slot.bin','--pci-resources','v1'])
  assert pin(stage/'boot.efi')==pin(stage/'boot-repeat.efi')
  raw=(stage/'kernel.elf').read_bytes();ph=struct.unpack_from('<Q',raw,32)[0];assert struct.unpack_from('<H',raw,56)[0]==2
  rx,rw=[struct.unpack_from('<IIQQQQQQ',raw,ph+i*56) for i in range(2)]
  assert rx[:5]==(1,5,4096,0x101000,0x101000) and rx[5]==rx[6]<=2097152-4096
  assert rw[:5]==(1,6,3145728,0x400000,0x400000) and rw[5]==rw[6]==0x240000 and pin(stage/'boot.efi')['bytes']<=7247872
  report.update(kernel=pin(stage/'kernel.elf'),efi=pin(stage/'boot.efi'),layout=dict(rx=rx,rw=rw))
  report['state']='EXECUTING';save();directory=out/'qemu';(directory/'esp/EFI/BOOT').mkdir(parents=True);shutil.copyfile(stage/'boot.efi',directory/'esp/EFI/BOOT/BOOTX64.EFI')
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  qemu=str(a.qemu.resolve(strict=True));fw=str(a.firmware.resolve(strict=True));assert pin(Path(qemu))['sha256']=='c2bfa7fb0542f2c48c705676c0e494ddf8122d9ad1a111f2bf0767245bc82a43';assert pin(Path(fw))['sha256']=='33090cc07675baa5190d9f1e84bf5176b33bcbfa9bacac522961150cdb6dbb2a'
  cmd=[qemu,'-machine','q35,accel=tcg,i8042=off','-cpu','max,phys-bits=37','-m','128M','-smp','1','-drive',f'if=pflash,format=raw,readonly=on,file={fw}','-drive','file=fat:rw:esp,format=raw','-nic','none','-display','none','-no-reboot','-no-shutdown','-gdb',f'tcp:127.0.0.1:{port}','-qmp','stdio','-serial','file:serial.log','-debugcon','file:debug.log']
  report.update(qemu=pin(Path(qemu)),firmware=pin(Path(fw)),command=cmd,compilerProfile='pool-v4-main-2f842',publicChannels={k:v.hex() for k,v in channels.items() if k.startswith('binding')});save()
  q=subprocess.Popen(cmd,cwd=directory,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(directory/'stderr').open('wb'),bufsize=0);c=pool.QMP(q);g=dbg.GDB(port)
  try:
   if not c.call('query-status')['running']:c.call('cont')
   phase=0;before=None;violations=[];until=time.monotonic()+a.execution_seconds
   while time.monotonic()<until:
    assert q.poll() is None
    private=c.dump(0x400000,65536,directory,'private-last.bin');scratch=struct.unpack_from('<Q',private,272)[0];row=c.dump(scratch,4096,directory,'receipt-last.bin') if scratch else bytes(4096)
    if struct.unpack_from('<Q',row)[0]==0x315453504b:
     v=struct.unpack_from('<12Q',row)
     if v[5]>phase:
      c.call('stop');assert v[5]==phase+1;assert 0x400000<=v[4] and v[4]+262144<=0x640000 and v[4]%4096==0;assert v[11]>=0x1000000;assert struct.unpack_from('<3Q',private,33536)==(v[11],8388608,pool.MARKER);assert all(0x400000<=x and x+262144<=0x640000 and x%4096==0 for x in [v[4],v[9],v[10]]);assert len(set([v[4],v[9],v[10]]))==3;item=dict(phase=v[5],kind=v[8],errors=v[1],checks=v[2],owners={});owners={}
      for name,base,size in [('pending',v[4],262144),('session',v[9],262144),('io',v[10],262144),('input',v[11],1048577)]:
       b=c.dump(base,size,directory,name+'-last.bin');owners[name]=b;name=f'phase-{v[5]:03}-{name}.bin.gz';p=directory/name;p.write_bytes(gzip.compress(b,mtime=0));item['owners'][name]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
      if item['kind']==10:
       assert before is None;before=owners
      elif item['kind']==11:
       assert before is not None
       if before!=owners:violations.append(dict(phase=v[5],reason='whole refusal owner/session/IO/input changed',regions=[k for k in owners if owners[k]!=before[k]]))
       before=None
      else:
       expected=ref.goldens(item['kind'],v[4],v[9],v[11],channels)
       item['independent']={}
       for name,b in expected.items():
        item['independent'][name]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),match=b==owners[name])
        if b!=owners[name]:violations.append(dict(phase=v[5],kind=item['kind'],region=name,reason='whole independent bytes differ',firstDifferent=next(i for i,(x,y) in enumerate(zip(b,owners[name])) if x!=y)))
      report['checkpoints'].append(item);report['observationFailures']=violations;save();print('checkpoint',item['kind'],item['errors'],item['checks'],flush=True);g.ack_checkpoint(scratch+48,v[5]);phase=v[5];c.call('cont')
     if v[3]==2:break
    time.sleep(.03)
   else:raise TimeoutError('probe incomplete')
   assert phase==35 and before is None and v[3]==2
   assert (v[1]>0 or bool(violations))==bool(a.fault),('fault not normally detected' if a.fault else 'native/independent failure',v[1],violations)
   context=c.dump(0x63a000,8192,directory,'context.bin');assert struct.unpack_from('<I',context,300)[0]==0
   report.update(state='DETECTED_NATIVE_PENDING_FAULT' if a.fault else 'PASS_NATIVE_APPLICATION_PENDING',normalCompletion=True,nativeErrors=v[1],nativeChecks=v[2],phases=phase,nativeModules=len(graph),activeRequestBound=256,fullJSONBytes=1048576,refusalComparisons=13,actualChannelChangedAtSamePeerKeyEpochTime=True,scope='single managed-session data owner; no app/service/socket/consent or native Mac/physical qualification');save();print(report['state'],v[1],v[2],len(graph),len(violations),flush=True)
  finally:
   if q.poll() is None:
    try:c.call('quit')
    except Exception:q.terminate()
    q.wait(timeout=10)
   g.close()
 except BaseException as error:report.update(state='FAILED',failure=str(error));save();raise

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['amu-source','compiler','baseline','qemu','firmware','output']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--baseline-sha256',required=True);p.add_argument('--execution-seconds',type=int,default=600);p.add_argument('--fault',choices=list(FAULTS));main(p.parse_args())
