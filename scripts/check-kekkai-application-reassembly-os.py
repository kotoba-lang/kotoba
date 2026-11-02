#!/usr/bin/env python3
"""Stage native reassembly over the real ValueRuntime graph, observe in QEMU.

Amu discovers/checks/compiles/packages. Python supplies public fixtures and
independent byte expectations; it does not run the protocol or Kotoba. GDB
writes only a checkpoint acknowledgement in a test-owned scratch receipt.
All guest return/refusal assertions run natively. No physical deployment.
"""
import argparse,gzip,hashlib,importlib.util,json,os,shutil,socket,struct,subprocess,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SIZE=8388608
SENTINEL=262144
MUTATIONS={
    'ar-key':('(same-key o h binding 0)','(do (same-key o h binding 0) true)'),
    'ar-epoch':('(= (br64 binding 8) (r64 o 32))','true'),
    'ar-message':('(> total 1048576)','(> total 1048577)'),
    'ar-total':('(> (+ (- (r o 12) old) size) 4194304)','(> (+ (- (r o 12) old) size) 4194305)'),
    'ar-json':('(valid-staged (kernel-subregion o 8388608 6950912 1048576) size)',
               '(do (valid-staged (kernel-subregion o 8388608 6950912 1048576) size) true)'),
    'ar-wipe':('(zero o (+ 2756608 used) (+ 2756608 old))','0'),
    'ar-slots':('(if (>= s 128) free','(if (>= s 127) free'),
    'ar-timeout':('(>= (- now (r64 o (+ (header s) 72))) idle)','(> (- now (r64 o (+ (header s) 72))) idle)'),
}


def digest(raw):return hashlib.sha256(raw).hexdigest()
def pin(path):
    raw=path.read_bytes();return dict(bytes=len(raw),sha256=digest(raw))
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def fresh(epoch):
    raw=bytearray(SIZE);struct.pack_into('<8I2Q',raw,0,0x3152414b,1,0,0,0,0,SENTINEL,SENTINEL,epoch,0);return raw


def header(raw,at,ident,parts,now):
    struct.pack_into('<IIQ',raw,at,1,1,42);struct.pack_into('<Q',raw,at+16,11)
    struct.pack_into('<3I',raw,at+48,2,2,parts);struct.pack_into('<Q',raw,at+72,now)
    raw[at+128:at+130]=f'{ident:02x}'.encode()


def aggregate(ref):
    raw=fresh(42);struct.pack_into('<2I',raw,8,4,4194304)
    struct.pack_into('<2I',raw,24,0,3*2048+1497);struct.pack_into('<Q',raw,40,400)
    for s in range(4):
        at=4096+s*1024;header(raw,at,20+s,2048,400);struct.pack_into('<2I',raw,at+60,1498,1048576)
        for i in range(1498):
            identity=s*2048+i;n=min(700,1048576-i*700)
            following=identity+1 if i<1497 else ((s+1)*2048 if s<3 else SENTINEL)
            struct.pack_into('<IHI',raw,135168+identity*10,s*1048576+i*700,0x8000+n,following)
    raw[2756608:6950912]=ref.payload(1048576)*4
    return bytes(raw)


def completed(ref):
    raw=fresh(42);struct.pack_into('<2I',raw,16,1048576,1);struct.pack_into('<Q',raw,40,400)
    header(raw,128,30,1498,400);raw[6950912:7999488]=ref.payload(1048576);return bytes(raw)


def dense():
    raw=fresh(42);struct.pack_into('<I',raw,8,128)
    struct.pack_into('<2I',raw,24,0,127*2048+2046);struct.pack_into('<Q',raw,40,500)
    for s in range(128):
        at=4096+s*1024;header(raw,at,s,2048,500);struct.pack_into('<I',raw,at+60,2047)
        for i in range(2047):
            identity=s*2048+i
            following=identity+1 if i<2046 else ((s+1)*2048 if s<127 else SENTINEL)
            struct.pack_into('<IHI',raw,135168+identity*10,0,0x8000,following)
    return bytes(raw)


class GDB:
    def __init__(self,port):
        self.s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);self.s.settimeout(10);self.s.connect(('127.0.0.1',port))
    def read(self,n):
        data=bytearray()
        while len(data)<n:
            row=self.s.recv(n-len(data))
            if not row:raise RuntimeError('GDB closed')
            data.extend(row)
        return bytes(data)
    def ack_checkpoint(self,address,phase):
        body=f'M{address:x},8:{struct.pack("<Q",phase).hex()}'.encode()
        self.s.sendall(b'$'+body+b'#'+f'{sum(body)%256:02x}'.encode())
        while self.read(1)!=b'$':pass
        result=bytearray()
        while True:
            ch=self.read(1)
            if ch==b'#':break
            result.extend(ch)
        checksum=self.read(2)
        assert checksum==f'{sum(result)%256:02x}'.encode() and result==b'OK',(result,checksum)
        self.s.sendall(b'+')
    def close(self):self.s.close()


def main(a):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False,mode=0o700)
    report=dict(schema='kekkai.native-reassembly.v1',state='STAGING',mutation=a.mutation,calls=[],checkpoints=[],
                physicalDeployment=False,appConnection=False,serviceExecution=False,trustedConsent=False,nativeLinuxExecution=False)
    def save():(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    save();q=None;c=None;gdb=None
    try:
        amu=a.amu_repo.resolve(strict=True)
        m=load('reassembly_mac',amu/'scripts/seed/check-aiueos-user-macos-native.py')
        pool=load('reassembly_pool',amu/'scripts/seed/check-aiueos-application-pool-macos-native.py')
        refpath=ROOT/'lib/kotoba.kekkai/tools/application_reassembly_reference.py';ref=load('reassembly_public',refpath)
        B=a.baseline_run.resolve(strict=True);assert pin(B/'receipt.json')['sha256']==a.baseline_receipt_sha256
        baseline=json.loads((B/'receipt.json').read_text());assert baseline['state']=='PASS_NATIVE_OS_APPLICATION_FRAME' and not baseline['mutation']
        assert baseline['cases']['count']==113 and len(baseline['sourceGraph'])==17
        build=json.loads((a.mac_build/'mac-aiueos-user-target.json').read_text());assert build['status']=='PASS_MAC_NATIVE_USER_TARGET_SELFHOST'
        assert build['generations'][-1]['container']==build['generations'][-2]['container']
        for row in build['sources']:assert pin(amu/row['name'])=={k:row[k] for k in ['bytes','sha256']}
        compiler=a.mac_build/f"F{build['generations'][-1]['number']}-signed.macho";assert m.verify_macho(compiler)==build['generations'][-1]['signed']
        for name in ['qemu','firmware']:
            path=getattr(a,name).resolve(strict=True);setattr(a,name,path);assert pin(path)['sha256']==getattr(a,name+'_sha256')
        stage=out/'source';stage.mkdir()
        for virtual,sha in baseline['sourceGraph'].items():
            assert virtual.startswith('/') and '..' not in Path(virtual).parts
            source=B/'source'/virtual.lstrip('/');assert pin(source)['sha256']==sha
            target=stage/virtual.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        flags=next(row['argv'][:-2] for row in baseline['calls'] if row['argv'][0]=='compile' and row['argv'][-1]=='KERNEL.ELF')
        assert flags[3]=='x86_64-aiueos-kernel-v3';flags[3]='x86_64-aiueos-kernel-v4'
        roots=flags[8:flags.index('--source-lock')]
        for root in roots[1::2]:
            assert root.startswith('/') and '..' not in Path(root).parts
            (stage/root.lstrip('/')).mkdir(parents=True,exist_ok=True)
        owners={
            '/application-owner/kekkai/application_frame_region.kotoba':'lib/kotoba.kekkai/kotoba/kekkai/application_frame_region.kotoba',
            '/application-owner/kekkai/application_reassembly_region.kotoba':'lib/kotoba.kekkai/kotoba/kekkai/application_reassembly_region.kotoba',
            '/application-owner/kekkai/application_reassembly_gate.kotoba':'lib/kotoba.kekkai/tools/application_reassembly_gate.kotoba',
            '/json-owner/kotoba/json/document_region.kotoba':'lib/kotoba.json/src/kotoba/json/document_region.kotoba'}
        report['productionSources']={}
        for virtual,relative in owners.items():
            target=stage/virtual.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,target);report['productionSources'][relative]=pin(ROOT/relative)
        owner=stage/'application-owner/kekkai/application_reassembly_region.kotoba'
        if a.mutation:
            before,after=MUTATIONS[a.mutation];text=owner.read_text();assert text.count(before)==1,(a.mutation,text.count(before));owner.write_text(text.replace(before,after))
        gate=stage/'application-owner/kekkai/application_frame_gate.kotoba';text=gate.read_text()
        before='[kotoba.json.region :as j] [kotoba.edn.region :as e])';assert text.count(before)==1
        text=text.replace(before,'[kotoba.json.region :as j] [kotoba.edn.region :as e]\n            [kekkai.application-reassembly-gate :as reassembly])')
        before='(p 79 1) (shared-known-answers)';assert text.count(before)==1
        gate.write_text(text.replace(before,'(p 79 1) (reassembly/run-tests) (shared-known-answers)'))
        report['fixtureAdapter']=dict(original=baseline['sourceGraph']['/application-owner/kekkai/application_frame_gate.kotoba'],staged=pin(gate),old113CasesRetained=True)
        for filename,field in [('boot-font.bin','bootFont'),('boot-user-slot.bin','diagnosticUserSlot')]:
            assert pin(B/'source'/filename)==baseline[field];shutil.copyfile(B/'source'/filename,stage/filename)
        public,docs=ref.documents();font=bytearray((stage/'boot-font.bin').read_bytes());assert not any(font[475136:475136+len(public)])
        font[475136:475136+len(public)]=public;(stage/'boot-font.bin').write_bytes(font)
        report.update(baselineReceipt=pin(B/'receipt.json'),compilerBuild=pin(a.mac_build/'mac-aiueos-user-target.json'),compiler=pin(compiler),
                      qemu=pin(a.qemu),firmware=pin(a.firmware),observer=pin(Path(__file__)),reference=pin(refpath),documents=docs,
                      bootFont=pin(stage/'boot-font.bin'),diagnosticUserSlot=pin(stage/'boot-user-slot.bin'),userCodeExecuted=False)
        def run(label,argv):
            started=time.monotonic();p=m.native_run(compiler,stage,*argv)
            (out/(label+'.stdout')).write_bytes(p.stdout);(out/(label+'.stderr')).write_bytes(p.stderr)
            report['calls'].append(dict(label=label,argv=argv,exit=p.returncode,seconds=time.monotonic()-started));save();return p.stdout
        discovery=run('modules',['modules',flags[1],*roots]);graph={}
        for line in discovery.decode().splitlines():
            namespace,virtual=line.split(' ',1);assert namespace and virtual.startswith('/') and virtual not in graph
            graph[virtual]=pin(stage/virtual.lstrip('/'))['sha256']
        assert len(graph)==20 and all(graph[k]==v for k,v in baseline['sourceGraph'].items() if k not in [*owners,'/application-owner/kekkai/application_frame_gate.kotoba'])
        lock=('KSL1\nentry '+flags[1]+'\n'+''.join('root '+v+'\n' for v in roots[1::2])+''.join('file '+v+' '+k+'\n' for k,v in sorted(graph.items()))).encode()
        (stage/'reassembly.ksl').write_bytes(lock);flags[-3]='reassembly.ksl';flags[-1]=digest(lock)
        report.update(sourceGraph=graph,sourceLock=pin(stage/'reassembly.ksl'));save()
        for name in ['kernel.elf','kernel-repeat.elf']:run(name,[*flags,'--output',name])
        assert pin(stage/'kernel.elf')==pin(stage/'kernel-repeat.elf')
        for name in ['boot.efi','boot-repeat.efi']:
            run(name,['package-aiueos-boot','kernel.elf','--output',name,'--font','boot-font.bin','--user-slot','boot-user-slot.bin','--pci-resources','v1'])
        assert pin(stage/'boot.efi')==pin(stage/'boot-repeat.efi')
        kernel=(stage/'kernel.elf').read_bytes();ph=struct.unpack_from('<Q',kernel,32)[0];assert struct.unpack_from('<H',kernel,56)[0]==2
        rx,rw=[struct.unpack_from('<IIQQQQQQ',kernel,ph+i*56) for i in range(2)]
        assert rx[:5]==(1,5,4096,0x101000,0x101000) and rx[5]==rx[6]<=2097152-4096
        assert rw[:5]==(1,6,3145728,0x400000,0x400000) and rw[5]==rw[6]==0x240000
        assert pin(stage/'boot.efi')['bytes']<=7247872
        directory=out/'qemu';(directory/'esp/EFI/BOOT').mkdir(parents=True);shutil.copyfile(stage/'boot.efi',directory/'esp/EFI/BOOT/BOOTX64.EFI')
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1',0));gdb_port=reserved.getsockname()[1]
        cmd=[str(a.qemu),'-machine','q35,accel=tcg,i8042=off','-cpu','max,phys-bits=37','-m','128M','-smp','1',
             '-drive',f'if=pflash,format=raw,readonly=on,file={a.firmware}','-drive','file=fat:rw:esp,format=raw','-boot','order=c',
             '-nic','none','-display','none','-no-reboot','-no-shutdown','-serial','file:serial.log','-debugcon','file:debug.log',
             '-gdb',f'tcp:127.0.0.1:{gdb_port}','-qmp','stdio']
        report.update(state='EXECUTING',kernel=pin(stage/'kernel.elf'),efi=pin(stage/'boot.efi'),layout=dict(rx=rx,rw=rw),command=cmd);save()
        err=(directory/'qemu.stderr').open('wb');q=subprocess.Popen(cmd,cwd=directory,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,bufsize=0)
        c=pool.QMP(q);gdb=GDB(gdb_port);until=time.monotonic()+a.execution_seconds;phase=0;before=None;before_input=None;observation_failures=[]
        # Attaching this test observer pauses the freshly created guest.
        # Resume exactly once here; later unexpected pauses remain failures.
        if not c.call('query-status')['running']:c.call('cont')
        aggregate_expected=aggregate(ref);completed_expected=completed(ref);dense_expected=dense()
        while time.monotonic()<until:
            assert q.poll() is None,'QEMU exited before native completion'
            private=c.dump(0x400000,65536,directory,'private-last.bin');scratch=struct.unpack_from('<Q',private,272)[0]
            row=c.dump(scratch,4096,directory,'receipt-last.bin') if scratch else bytes(4096)
            if struct.unpack_from('<Q',row)[0]==0x31545341524b:
                values=struct.unpack_from('<13Q',row);current,kind=values[5],values[8]
                if current>phase:
                    assert current==phase+1;c.call('stop')
                    base,size,ready=struct.unpack_from('<3Q',private,33536);assert base==values[4] and size==SIZE and ready==pool.MARKER
                    assert base>=0x1000000 and base%4096==0 and base+SIZE<=2**32
                    raw=c.dump(base,SIZE,directory,'owner-last.bin');inputs=c.dump(scratch+4096,4096,directory,'input-last.bin')
                    compressed=gzip.compress(raw,mtime=0);assert gzip.decompress(compressed)==raw
                    name=f'phase-{current:03d}-owner.bin.gz';(directory/name).write_bytes(compressed)
                    result=dict(phase=current,kind=kind,owner=dict(bytes=SIZE,sha256=digest(raw)),input=hashlib.sha256(inputs).hexdigest(),
                                compressed=dict(name=name,**pin(directory/name)),nativeErrors=values[1],nativeChecks=values[2],match=True)
                    if kind==1:before,before_input=raw,inputs
                    elif kind==2:
                        assert before is not None
                        result['match']=raw==before and inputs==before_input
                        result['result']=struct.unpack_from('<q',row,56)[0]
                        if not result['match']:observation_failures.append(dict(phase=current,kind=kind,reason='refusal changed full owner/input'))
                        before=before_input=None
                    else:
                        expected=aggregate_expected if kind==4 else (bytes(fresh(43)) if kind==5 else completed_expected if kind==3 else dense_expected if kind==7 else None)
                        if expected is not None:
                            result['expectedSHA256']=digest(expected);result['match']=raw==expected
                            if not result['match']:observation_failures.append(dict(phase=current,kind=kind,reason='full owner differs',actual=digest(raw),expected=digest(expected)))
                        elif kind==6:
                            n=struct.unpack_from('<I',raw,16)[0];assert 0<n<=1048576
                            result['match']=raw[6950912:6950912+n]==ref.payload(n) and not any(raw[6950912+n:7999488])
                            if not result['match']:observation_failures.append(dict(phase=current,kind=kind,reason='completed bytes differ'))
                        else:raise AssertionError(('unknown checkpoint',kind))
                    report['checkpoints'].append(result);report['observationFailures']=observation_failures;save()
                    gdb.ack_checkpoint(scratch+48,current);phase=current;c.call('cont');print('checkpoint',phase,kind,result['match'],flush=True)
                context=c.dump(0x63a000,8192,directory,'context-last.bin');words=struct.unpack_from('<6I',context,74*4)
                if values[3]==2 and words[-1]==2:break
            status=c.call('query-status');assert status['running'],status
            time.sleep(.02)
        else:raise TimeoutError('native reassembly/retained corpus did not complete')
        c.call('stop');row=c.dump(scratch,4096,directory,'receipt.bin');values=struct.unpack_from('<13Q',row)
        assert values[0]==0x31545341524b and values[3]==2 and values[12]==0x1234abcd
        context=c.dump(0x63a000,8192,directory,'context.bin');words=struct.unpack_from('<6I',context,74*4)
        assert words==(113,0,1,1,113,2),words
        assert struct.unpack_from('<3I',context,91*4)==(1,12,0)
        old_owner,old_caller=struct.unpack_from('<2Q',context,400)
        assert c.dump(old_owner,8192,directory,'old-work.bin')==bytes(8192)
        pairs=c.dump(old_caller+196608,113*16,directory,'old-returns.bin');assert all(x==y for x,y in struct.iter_unpack('<qq',pairs))
        hashes=c.dump(old_caller+229376,113*32,directory,'old-hashes.bin');assert hashes==bytes.fromhex(''.join(baseline['cases']['expectedHashes']))
        assert c.dump(old_caller+163840,113*4,directory,'old-assertions.bin')==bytes(113*4)
        assert all(not current['owner']['sha256']=='' for current in report['checkpoints']) and before is None
        assert phase>=60 and all(sum(row['kind']==kind for row in report['checkpoints'])==1 for kind in [3,4,7])
        failed=values[1]>0 or bool(observation_failures)
        assert failed==bool(a.mutation),('mutation not normally detected' if a.mutation else 'native assertions/byte observations failed',values,observation_failures)
        report.update(state='DETECTED_NATIVE_REASSEMBLY_FAULT' if a.mutation else 'PASS_NATIVE_APPLICATION_REASSEMBLY',
                      nativeErrors=values[1],nativeChecks=values[2],nativeReceipt=list(values),retainedCases=113,retainedCursorGuards=12,
                      retainedKnownAnswers=True,oldOwner=old_owner,oldCaller=old_caller,poolBase=values[4],poolBytes=SIZE,
                      fullMessages=1048576,partsPerMessage=2048,pendingAssemblies=128,pendingPayloadBytes=4194304,
                      simultaneousIncompleteParts=128*2047,
                      normalCompletion=True,oldABIAndRuntimeRetained=True);save();print(report['state'],values[1],values[2],flush=True)
    except BaseException as error:
        report.update(state='FAILED',failure=str(error));save();raise
    finally:
        if q is not None and q.poll() is None:
            try:c.call('quit')
            except Exception:q.terminate()
            q.wait(timeout=10)
        if gdb is not None:gdb.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['amu-repo','mac-build','baseline-run','qemu','firmware','output']:p.add_argument('--'+name,type=Path,required=True)
    for name in ['baseline-receipt-sha256','qemu-sha256','firmware-sha256']:p.add_argument('--'+name,required=True)
    p.add_argument('--execution-seconds',type=int,default=1200)
    p.add_argument('--mutation',choices=list(MUTATIONS))
    main(p.parse_args())
