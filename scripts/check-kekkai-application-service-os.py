#!/usr/bin/env python3
"""Native configured-service association; no product endpoint or consent gate."""
import argparse, hashlib, importlib.util, json, shutil, socket, struct, subprocess, time
from pathlib import Path
R=Path(__file__).resolve().parents[1]

def pin(path):
    raw=path.read_bytes();return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main(a):
    if not __debug__:raise RuntimeError('assertions must remain enabled')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);stage=out/'source';stage.mkdir()
    shutil.copyfile(Path(__file__),out/'observer-source.py')
    A=a.amu_source.resolve(strict=True);B=a.baseline.resolve(strict=True);C=a.compiler.resolve(strict=True)
    base=json.loads((B/'receipt.json').read_text());assert base['state']=='PASS_FULL_NATIVE_APPLICATION_SEND'
    assert pin(B/'receipt.json')['sha256']==a.baseline_sha256
    report=dict(schema='kekkai.native-application-service.v1',state='STAGING',calls=[],observer=pin(Path(__file__)),
        compiler=pin(C),baseline=pin(B/'receipt.json'),installedApp=False,nativeMacBackend=False,
        physicalDeployment=False,serviceExecution=False,trustedConsent=False,endpointQualified=False,
        nativeSSH=False,hostileCPL3Executed=False,releaseQualified=False)
    def save():(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    mac=load('service_mac',A/'scripts/seed/check-aiueos-user-macos-native.py')
    pool=load('service_qmp',A/'scripts/seed/check-aiueos-application-pool-macos-native.py')
    assert mac.verify_macho(C)==dict(bytes=3843200,sha256='2a6b64dce3bf868ee9868e7d78687244f01fca1915276588fde27939ab20348b')
    for v,h in base['sourceGraph'].items():
        p=B/'source'/v.lstrip('/');assert pin(p)['sha256']==h
        target=stage/v.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    for name,relative in [('application_service_region.kotoba','lib/kotoba.kekkai/kotoba/kekkai/application_service_region.kotoba'),('application_service_gate.kotoba','lib/kotoba.kekkai/tools/application_service_gate.kotoba')]:
        shutil.copyfile(R/relative,stage/'session-owner/kekkai'/name)
    flags=next(c['argv'][:-2] for c in base['calls'] if c['label']=='kernel.elf')
    roots=flags[8:flags.index('--source-lock')];entry=stage/flags[1].lstrip('/')
    for root in roots[1::2]:(stage/root.lstrip('/')).mkdir(parents=True,exist_ok=True)
    text=entry.read_text();assert text.count('kekkai.application-send-link-gate')==1
    entry.write_text(text.replace('kekkai.application-send-link-gate','kekkai.application-service-gate'))
    for name in ['boot-font.bin','boot-user-slot.bin']:shutil.copyfile(B/'source'/name,stage/name)
    reference=load('service_public_frame',R/'lib/kotoba.kekkai/tools/frame_link_reference.py')
    raw,_=reference.fixtures();assert len(raw)<65536
    blob=bytearray(raw)+bytes(65536+64-len(raw))
    at=struct.unpack_from('<I',raw,36)[0];peer=raw[at:at+32].hex()
    for i,value in enumerate([
        dict(version=1,serviceName='local-docs',peerKey=peer,port=443,baseUrl='',direction=0),
        dict(version=1,serviceName='local-docs',peerKey=peer,port=443,baseUrl='http://127.0.0.1:8080',direction=1),
        dict(messageType='request',requestId='native-service',serviceName='local-docs',method='GET',path='/docs',headers={},port=443,bodyBase64='')]):
        data=json.dumps(value,separators=(',',':')).encode();struct.pack_into('<II',blob,65536+i*8,len(blob),len(data));blob+=data
    assert len(blob)<=131072
    font=bytearray((stage/'boot-font.bin').read_bytes());font[393216:]=blob+bytes(131072-len(blob));(stage/'boot-font.bin').write_bytes(font)
    report.update(bootFont=pin(stage/'boot-font.bin'),userSlot=pin(stage/'boot-user-slot.bin'),fixtureBytes=len(blob),
        productionSources={rel:pin(R/rel) for rel in ['lib/kotoba.kekkai/kotoba/kekkai/application_service_region.kotoba']})
    def run(label,args):
        try:p=mac.native_run(C,stage,*args)
        except ValueError:p=mac.native_run(C,stage,*args,expected=1)
        (out/(label+'.stdout')).write_bytes(p.stdout);(out/(label+'.stderr')).write_bytes(p.stderr)
        report['calls'].append(dict(label=label,argv=args,exit=p.returncode));save();print(label,p.returncode,flush=True)
        if p.returncode:raise RuntimeError('native failed '+label)
        return p.stdout
    try:
        raw=run('modules',['modules',flags[1],*roots]);graph={}
        for line in raw.decode().splitlines():
            namespace,virtual=line.split(' ',1);graph[virtual]=pin(stage/virtual.lstrip('/'))['sha256']
        lock=('KSL1\nentry '+flags[1]+'\n'+''.join('root '+v+'\n' for v in roots[1::2])+''.join('file '+v+' '+h+'\n' for v,h in sorted(graph.items()))).encode()
        (stage/'service.ksl').write_bytes(lock);flags[-3]='service.ksl';flags[-1]=hashlib.sha256(lock).hexdigest();report['sourceGraph']=graph
        for name in ['kernel.elf','kernel-repeat.elf']:run(name,[*flags,'--output',name])
        assert pin(stage/'kernel.elf')==pin(stage/'kernel-repeat.elf')
        for name in ['boot.efi','boot-repeat.efi']:run(name,['package-aiueos-boot','kernel.elf','--output',name,'--font','boot-font.bin','--user-slot','boot-user-slot.bin','--pci-resources','v1'])
        assert pin(stage/'boot.efi')==pin(stage/'boot-repeat.efi')
        raw=(stage/'kernel.elf').read_bytes();ph=struct.unpack_from('<Q',raw,32)[0]
        assert struct.unpack_from('<H',raw,56)[0]==2
        rx,rw=[struct.unpack_from('<IIQQQQQQ',raw,ph+i*56) for i in range(2)]
        assert rx[5]<=2093056 and rw[5]==2359296
        directory=out/'qemu';(directory/'esp/EFI/BOOT').mkdir(parents=True);shutil.copyfile(stage/'boot.efi',directory/'esp/EFI/BOOT/BOOTX64.EFI')
        cmd=[str(a.qemu.resolve(strict=True)),'-machine','q35,accel=tcg,i8042=off','-cpu','max,phys-bits=37','-m','128M','-smp','1','-drive','if=pflash,format=raw,readonly=on,file='+str(a.firmware.resolve(strict=True)),'-drive','file=fat:rw:esp,format=raw','-nic','none','-display','none','-no-reboot','-no-shutdown','-serial','file:serial.log','-debugcon','file:debug.log','-qmp','stdio']
        assert pin(a.qemu)['sha256']=='c2bfa7fb0542f2c48c705676c0e494ddf8122d9ad1a111f2bf0767245bc82a43'
        assert pin(a.firmware)['sha256']=='33090cc07675baa5190d9f1e84bf5176b33bcbfa9bacac522961150cdb6dbb2a'
        report.update(state='EXECUTING',layout=dict(rx=rx,rw=rw),command=cmd);save()
        p=subprocess.Popen(cmd,cwd=directory,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(directory/'stderr').open('wb'),bufsize=0);q=pool.QMP(p)
        try:
            until=time.monotonic()+a.execution_seconds
            while time.monotonic()<until:
                assert p.poll() is None
                private=q.dump(0x400000,65536,directory,'private.bin');scratch=struct.unpack_from('<Q',private,272)[0]
                receipt=q.dump(scratch,4096,directory,'receipt.bin') if scratch else bytes(4096)
                if struct.unpack_from('<Q',receipt)[0]==0x3156534b:
                    values=struct.unpack_from('<16Q',receipt)
                    if values[3]==2:break
                time.sleep(.03)
            else:raise TimeoutError('native service diagnostic incomplete')
            report.update(state='PASS_DEVELOPMENT_SERVICE_PROBE',nativeErrors=values[1],nativeChecks=values[2],normalCompletion=True)
            assert values[1]==0
            for name,address,size in [('service',values[4],65536),('session',values[9],262144),('io',values[10],262144),('pool',values[11],8388608),('transmit',values[14],1048576)]:
                data=q.dump(address,size,directory,name+'.bin');report.setdefault('finalMemory',{})[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
            save();print(report['state'],values[2],len(graph),rx[5],flush=True)
        finally:
            if p.poll() is None:
                try:q.call('quit')
                except Exception:p.terminate()
                p.wait(timeout=10)
    except BaseException as e:report.update(state='FAILED',failure=str(e));save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['output','baseline','compiler','amu-source','qemu','firmware']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--baseline-sha256',required=True);p.add_argument('--execution-seconds',type=int,default=600);main(p.parse_args())
