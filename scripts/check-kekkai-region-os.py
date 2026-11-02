#!/usr/bin/env python3
"""Compile/boot the allocation-free Noise hash owner under the actual OS ABI.

Mac observer/stager only. Amu discovers/compiles/packages all guest code;
QEMU executes the region implementation and native KAT/refusal assertions.
Python hashlib/HMAC supply independent public expected bytes, not language
execution or compilation. No physical deployment, identity or app admission.
"""
import argparse
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
OS_SCRIPTS=ROOT/'lib/kotoba.aiueos/os/aiueos/scripts'
MUTATIONS={
 'rotate':('(vp st b (rr (bit-xor (v st b) (v st c)) 7))','(vp st b (rr (bit-xor (v st b) (v st c)) 6))'),
 'final':('(if (= final 1)','(if (= final 0)'),
 'long-key':('(> (ld st 224) 64)','(> (ld st 224) 4096)'),
 'carry':('(put st 228 (+ (ld st 228) 1))','(put st 228 (ld st 228))'),
 'overflow':('(not (and (= (ld st 224) 4294967295) (= (ld st 228) 4294967295)))','true'),
 'phase':('(= (ld st 236) 1)','(or (= (ld st 236) 1) (= (ld st 236) 2))')}

def pin(path):
    raw=path.read_bytes();return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main(a):
    out=a.output.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False)
    state=dict(schema='kekkai.os-region-blake2s.v1',state='STAGING',mutation=a.mutation,
               calls=[],physicalDeployment=False,appInstallQualified=False,
               productUserABIQualified=False,existingABIExportsRetained=True,
               observer=pin(Path(__file__)),pythonVersion=sys.version.split()[0])
    def save():(out/'receipt.json').write_text(json.dumps(state,indent=2)+'\n')
    save()
    try:
        sys.path.insert(0,str(OS_SCRIPTS))
        builder=load('region_kernel_builder',OS_SCRIPTS/'build-native-kernel-macos.py')
        a.compiler=a.compiler.resolve(strict=True)
        builder.verify_compiler(a.compiler,a.compiler_sha256)
        for name in ['packager','qemu','firmware']:
            path=getattr(a,name).resolve(strict=True);setattr(a,name,path)
            if pin(path)['sha256']!=getattr(a,name+'_sha256'):raise ValueError(name+' pin differs')
        baseline=a.source_stage.resolve(strict=True);lock=(baseline/'kernel.ksl').read_bytes()
        if hashlib.sha256(lock).hexdigest()!=a.source_lock_sha256:raise ValueError('baseline lock pin differs')
        state['compiler']=pin(a.compiler);state['baselineLockSHA256']=a.source_lock_sha256
        stage=out/'source';stage.mkdir();roots=[];entry=None
        if not lock.startswith(b'KSL1\n'):raise ValueError('baseline lock format')
        for line in lock.decode().splitlines()[1:]:
            kind,value=line.split(' ',1)
            if kind=='entry':entry=value
            elif kind=='root':roots.append(value)
            elif kind=='file':
                digest,virtual=value.split(' ',1);p=Path(virtual)
                if not p.is_absolute() or '..' in p.parts:raise ValueError('baseline path')
                raw=(baseline/virtual.lstrip('/')).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('baseline source drift')
                target=stage/virtual.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
            else:raise ValueError('unknown lock record')
        if entry!='/os/aiueos/native/usb-update-test-entry.kotoba':raise ValueError('unexpected baseline entry')
        source=(stage/entry.lstrip('/')).read_text()
        before='''(defn main [] :i64
  ;; The root explicitly selects the image's private GOP/Browser profile.
  ;; PCI/GOP/font sealing happens before any Kotoba body receives a region.
  (let [width (kernel-framebuffer-width)
        registered (kernel-register-value-domain 73)
        published (kernel-publish-current-domain 73)
        enabled (kernel-value-enable-user)]
    (if (and (> width 0) (> registered 0) (= published 73) (= enabled 1))
      (fixture/run) 0)))'''
        for old,new in [
          ('aiueos.native.usb-update-test-entry','aiueos.native.kekkai-blake2s-region-entry'),
          ('[aiueos.native.usb-update-probe :as fixture]','[noise.blake2s-region-gate :as fixture]'),
          (before,'(defn main [] :i64\n  (fixture/run))')]:
            if source.count(old)!=1:raise ValueError('baseline entry changed')
            source=source.replace(old,new)
        entry='/os/aiueos/native/kekkai-blake2s-region-entry.kotoba'
        (stage/entry.lstrip('/')).write_text(source)
        core=ROOT/'lib/kotoba.noise/kotoba/noise/blake2s_region.kotoba'
        fixture=ROOT/'lib/kotoba.noise/tools/blake2s_region_gate.kotoba'
        core_bytes=core.read_bytes();state['ownerSource']=pin(core);state['fixtureSource']=pin(fixture)
        if a.mutation:
            old,new=MUTATIONS[a.mutation];text=core_bytes.decode()
            if text.count(old)!=1:raise ValueError('mutation is not unique')
            core_bytes=text.replace(old,new).encode()
        for virtual,raw in [('noise/blake2s_region.kotoba',core_bytes),('noise/blake2s_region_gate.kotoba',fixture.read_bytes())]:
            target=stage/'noise-owner'/virtual;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        roots.append('/noise-owner');flags=[v for r in roots for v in ('--source-path',r)]
        payload=a.payload.resolve(strict=True)
        if pin(payload)['sha256']!=a.payload_sha256:raise ValueError('boot payload pin differs')
        (stage/'boot-payload.bin').write_bytes(payload.read_bytes());state['bootPayload']=pin(payload)
        fd=os.open(stage,os.O_RDONLY|os.O_DIRECTORY)
        if fd!=3:os.dup2(fd,3);os.close(fd)
        def run(label,argv):
            p=subprocess.run([str(a.compiler),*argv],cwd=stage,env={'PATH':'/nonexistent'},pass_fds=(3,),capture_output=True,timeout=180)
            for suffix,raw in [('stdout',p.stdout),('stderr',p.stderr)]: (out/(label+'.'+suffix)).write_bytes(raw)
            state['calls'].append(dict(label=label,argv=argv,exit=p.returncode,stdout=p.stdout.decode(errors='replace'),stderr=p.stderr.decode(errors='replace')));save()
            if p.returncode or p.stderr:raise RuntimeError(label+': '+p.stderr.decode(errors='replace')[:1000])
            return p.stdout
        modules=run('modules',['modules',entry,*flags]);graph={}
        for line in modules.decode().splitlines():
            namespace,virtual=line.split(' ',1)
            if not namespace or not virtual.startswith('/') or virtual in graph:raise ValueError('module graph shape')
            graph[virtual]=pin(stage/virtual.lstrip('/'))['sha256']
        state['sourceGraph']=graph
        current='KSL1\nentry '+entry+'\n'+''.join('root '+r+'\n' for r in roots)+''.join('file '+s+' '+p+'\n' for p,s in sorted(graph.items()))
        (stage/'region.ksl').write_text(current)
        compile_args=['compile',entry,'--target','x86_64-aiueos-kernel-v3','--artifact','image','--fuel','9007199254740991',*flags,'--source-lock','region.ksl','--source-lock-sha256',hashlib.sha256(current.encode()).hexdigest()]
        for name in ['KERNEL.ELF','KERNEL.reproduced.ELF']:run('compile-'+name,[*compile_args,'--output',name])
        if (stage/'KERNEL.ELF').read_bytes()!=(stage/'KERNEL.reproduced.ELF').read_bytes():raise ValueError('kernel reproduction differs')
        for name in ['BOOTX64.EFI','BOOTX64.reproduced.EFI']:
            run('package-'+name,['package-aiueos-boot','KERNEL.ELF','--output',name,'--payload','boot-payload.bin','--pci-resources','v1'])
        if (stage/'BOOTX64.EFI').read_bytes()!=(stage/'BOOTX64.reproduced.EFI').read_bytes():raise ValueError('EFI reproduction differs')
        efi=stage/'BOOTX64.EFI';kernel=stage/'KERNEL.ELF'
        cmd=[sys.executable,str(OS_SCRIPTS/'build-native-media-macos.py'),'--amu-source',str(a.amu_source.resolve(strict=True)),
             '--compiler-image',str(a.compiler),'--compiler-sha256',a.compiler_sha256,'--packager-image',str(a.packager),
             '--packager-sha256',a.packager_sha256,'--efi',str(efi),'--efi-sha256',pin(efi)['sha256'],'--output',str(out/'media')]
        media_run=subprocess.run(cmd,capture_output=True,timeout=180)
        (out/'media.stdout').write_bytes(media_run.stdout);(out/'media.stderr').write_bytes(media_run.stderr)
        if media_run.returncode:raise RuntimeError('native media build failed: '+media_run.stderr.decode(errors='replace')[:1000])
        media=out/'media/awai-native.img'
        if not media.exists():raise ValueError('native media output missing')
        state['state']='COMPILED_NOT_BOOTED';save()
        media_before=pin(media)
        keys=load('region_qemu_observer',OS_SCRIPTS/'check-native-keystore-qemu.py')
        state['qemuHelper']=pin(OS_SCRIPTS/'check-native-keystore-qemu.py')
        boot=keys.Boot.__new__(keys.Boot)
        try:
            keys.Boot.__init__(boot,SimpleNamespace(kernel=kernel,efi=efi,media=media,qemu=a.qemu,firmware=a.firmware),out,'region-crypto',None,
                               extra=('-serial','file:serial.log','-debugcon','file:debug.log'),first_frame_seconds=a.first_frame_seconds)
            words=struct.unpack('<6I',boot.dump(boot.work+74*4,24))
            raw=boot.dump(boot.work+keys.native_regions.WINDOW_BYTES,303*32)
        except BaseException:
            if hasattr(boot,'proc') and boot.proc.poll() is None:
                (out/'failure-context.bin').write_bytes(boot.dump(boot.work,8192))
                boot.send('info registers');state['failureRegisters']=boot.drain();save()
            raise
        finally:
            if hasattr(boot,'proc'):boot.quit()
        (out/'native-digests.bin').write_bytes(raw)
        if pin(media)!=media_before:raise ValueError('fixture medium changed during QEMU boot')
        state['mediaUnchanged']=True
        if hashlib.blake2s(b'abc').hexdigest()!='508c5e8c327c14e2e1a72ba34eeb452f37458b209ed63a294d999b4c86675982':raise ValueError('reference KAT differs')
        if hmac.digest(b'',b'','blake2s').hex()!='eaf4bb25938f4d20e72656bbbc7a9bf63c0c18537333c35bdb67db1402661acd':raise ValueError('reference HMAC KAT differs')
        pattern=lambda n:bytes((i*17+3)%256 for i in range(n))
        expected=[hashlib.blake2s(pattern(n)).digest() for n in range(258)]
        expected.extend([hashlib.blake2s(b'abc').digest(),hashlib.blake2s(pattern(65536)).digest(),hashlib.blake2s(pattern(1048576)).digest()])
        for kn in [0,32,64,65,100,4096]:
            key=bytes((i*29+11)%256 for i in range(kn))
            for n in [0,1,63,64,65,257,4096]:expected.append(hmac.digest(key,pattern(n),'blake2s'))
        expected=b''.join(expected);(out/'expected-digests.bin').write_bytes(expected)
        mismatches=[i for i in range(303) if raw[i*32:i*32+32]!=expected[i*32:i*32+32]]
        observed=dict(knownAnswerMask=words[0],operationErrors=words[1],guardMask=words[2],canaryMask=words[3],digestCount=words[4],completed=words[5],mismatchedDigests=mismatches)
        state['observed']=observed;state['artifacts']={n:pin(p) for n,p in [('kernel',kernel),('efi',efi),('media',media),('qemu',a.qemu),('firmware',a.firmware)]}
        good=words==(3,0,1023,1,303,1) and not mismatches
        if a.mutation:
            if words[1]!=0 or words[3:]!=(1,303,1):raise AssertionError('mutation did not complete bounded native controls')
            if good:raise AssertionError('mutation escaped native controls')
            state['state']='DETECTED_NATIVE_MUTATION'
        else:
            if not good:raise AssertionError('native digest/control mismatch: '+str(observed))
            state['state']='PASS_NATIVE_OS_REGION_BLAKE2S_HMAC'
        state['kernelReproduced']=True;state['efiReproduced']=True;save();print(state['state'],json.dumps(observed))
    except BaseException as error:
        state['failure']=type(error).__name__+': '+str(error);save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['compiler','packager','amu-source','source-stage','payload','qemu','firmware','output']:p.add_argument('--'+name,type=Path,required=True)
    for name in ['compiler-sha256','packager-sha256','source-lock-sha256','payload-sha256','qemu-sha256','firmware-sha256']:p.add_argument('--'+name,required=True)
    p.add_argument('--first-frame-seconds',type=float,default=240)
    p.add_argument('--mutation',choices=MUTATIONS)
    main(p.parse_args())
