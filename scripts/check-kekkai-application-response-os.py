#!/usr/bin/env python3
"""Native Amu/QEMU managed receive -> codec -> full-capacity reassembly.

Python stages source/public fixtures and observes native execution. It is
never a language resolver/compiler, EDN evaluator, app backend or consent
authority. GDB writes only an acknowledgement in a dedicated test receipt.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BASELINE_SHA = '7819846b94d5504396fc19506e7cfce98b9a1a79a34181acffdc2e28ec7cb804'
COMPILER_PROFILES = {
    'pool-v4-35f-reference': '3eb3f37318b35a612c6322d638f24060f1e6579d31f12573a2ea1cae88239521',
    'pool-v4-main-2f842': 'efec34486903fc189eb9e3a6d45e02edeaa7f7edf73a9e3e12586c8de048b225'}
PUBLIC = [
    'scripts/native_application_response_peer.py', 'scripts/native_udp_link_peer.py',
    'lib/kotoba.kekkai/tools/application_receive_reference.py',
    'lib/kotoba.kekkai/tools/application_response_reference.py',
    'lib/kotoba.kekkai/tools/frame_link_reference.py',
    'lib/kotoba.kekkai/tools/session_region_reference.py',
    'lib/kotoba.kekkai/tools/application_frame_reference.py',
    'lib/org.ietf.chacha20Poly1305/tools/reference.py',
    'lib/org.ietf.x25519/tools/reference.py',
    'lib/kotoba.aiueos/os/aiueos/scripts/check-native-consent-qemu.py',
    'lib/kotoba.aiueos/os/aiueos/scripts/check-native-ed25519-qemu.py',
    'lib/kotoba.aiueos/os/aiueos/scripts/native_regions.py']
FAULTS = {
    'pin': ('lib/kotoba.kekkai/kotoba/kekkai/application_reassembly_region.kotoba', '(copy-in o 1152 binding 96 0 96)', '(copy-in o 1152 binding 96 0 64)'),
    'retag': ('lib/kotoba.kekkai/kotoba/kekkai/application_reassembly_region.kotoba', '(or (channel-empty o 1152) (channel-same o binding 0))', '(or (channel-empty o 1152) (channel-same o binding 0) (= (r o 20) 1))'),
    'binding': ('lib/kotoba.kekkai/kotoba/kekkai/application_pending_region.kotoba', '(defn- incoming-binding [o binding i] :bool\n  (if (>= i 96)', '(defn- incoming-binding [o binding i] :bool\n  (if (>= i 64)'),
    'discard': ('lib/kotoba.kekkai/kotoba/kekkai/application_response_region.kotoba', '(if (= held 0) (a/release pool 8388608)', '(if (>= held 0) (a/release pool 8388608)'),
    'release': ('lib/kotoba.kekkai/kotoba/kekkai/application_response_region.kotoba', '(a/release pool 8388608) -1)))', '1 -1)))')}



def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(raw): return hashlib.sha256(raw).hexdigest()
def pin(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=digest(raw))


def main(a):
    if not __debug__: raise RuntimeError('assertions must remain enabled')
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    stage, public = out/'source', out/'public-fixtures'
    stage.mkdir()
    report = dict(schema='kekkai.native-application-response.v1',state='STAGING',fault=a.fault,
        calls=[],shapeCheckpoints=[],observationFailures=[],observer=pin(Path(__file__)),
        physicalDeployment=False,appInstalled=False,trustedConsent=False,serviceExecution=False,
        nativeSSH=False,releaseQualified=False,userCodeExecuted=False,
        scope='isolated kernel diagnostic with public keys and synthetic time; no application effects')

    def save(): (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    proc = peer = gdb = q = None
    try:
        assert pin(a.baseline)['sha256'] == BASELINE_SHA
        baseline = json.loads(a.baseline.read_text())
        assert baseline['state'] == 'PASS_NATIVE_OS_APPLICATION_LINK' and len(baseline['sourceGraph']) == 39
        base = a.baseline.parent
        mac_path = a.amu_source/'scripts/seed/check-aiueos-user-macos-native.py'
        qmp_path = a.amu_source/'scripts/seed/check-aiueos-application-pool-macos-native.py'
        gdb_path = ROOT/'scripts/check-kekkai-application-reassembly-os.py'
        mac, pool, checkpoint = load('receive_mac',mac_path),load('receive_qmp',qmp_path),load('receive_gdb',gdb_path)
        assert mac.verify_macho(a.compiler) == dict(bytes=3826784,sha256=COMPILER_PROFILES[a.compiler_profile])
        assert pin(a.qemu)['sha256'] == a.qemu_sha256
        assert pin(a.firmware)['sha256'] == a.firmware_sha256
        report.update(compiler=pin(a.compiler),compilerProfile=a.compiler_profile,baseline=pin(a.baseline),qemu=pin(a.qemu),firmware=pin(a.firmware),
            nativeHelpers={str(p.relative_to(a.amu_source)):pin(p) for p in [mac_path,qmp_path]},gdbObserver=pin(gdb_path))
        for virtual,sha in baseline['sourceGraph'].items():
            source = base/'source'/virtual.lstrip('/')
            assert pin(source)['sha256'] == sha
            target = stage/virtual.lstrip('/')
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
        for name,key in [('boot-font.bin','bootFont'),('boot-user-slot.bin','diagnosticUserSlot')]:
            assert pin(base/'source'/name) == baseline[key]
            shutil.copyfile(base/'source'/name,stage/name)
        overlays = {}
        for filename,relative in [
            ('session_region.kotoba','lib/kotoba.kekkai/kotoba/kekkai/session_region.kotoba'),
            ('session_region_gate.kotoba','lib/kotoba.kekkai/tools/session_region_gate.kotoba')]:
            overlays[next(v for v in baseline['sourceGraph'] if v.endswith('/kekkai/'+filename))] = relative
        owner_root = Path(next(v for v in baseline['sourceGraph'] if v.endswith('/kekkai/application_frame_region.kotoba'))).parent
        for filename in ['application_receive_region.kotoba','application_reassembly_region.kotoba','application_message_region.kotoba','application_pending_region.kotoba','application_response_region.kotoba']:
            overlays[str(owner_root/filename)] = 'lib/kotoba.kekkai/kotoba/kekkai/'+filename
        overlays['/json-owner/kotoba/json/document_region.kotoba'] = 'lib/kotoba.json/src/kotoba/json/document_region.kotoba'
        for virtual,relative in overlays.items():
            target = stage/virtual.lstrip('/')
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/relative,target)
        if a.fault:
            relative,before,after = FAULTS[a.fault]
            virtual = next(k for k,v in overlays.items() if v==relative)
            path = stage/virtual.lstrip('/')
            text=path.read_text();assert text.count(before)==1,(a.fault,text.count(before));path.write_text(text.replace(before,after))
        old_gate = next(v for v in baseline['sourceGraph'] if v.endswith('/kekkai/application_link_gate.kotoba'))
        (stage/old_gate.lstrip('/')).unlink()
        new_gate = stage/str(Path(old_gate).with_name('application_response_link_gate.kotoba')).lstrip('/')
        shutil.copyfile(ROOT/'lib/kotoba.kekkai/tools/application_response_link_gate.kotoba',new_gate)
        entry = next(v for v in baseline['sourceGraph'] if v.endswith('/kekkai-application-link-region-entry.kotoba'))
        entry_path = stage/entry.lstrip('/')
        text = entry_path.read_text()
        assert text.count('kekkai.application-link-gate') == 1
        entry_path.write_text(text.replace('kekkai.application-link-gate','kekkai.application-response-link-gate'))
        for relative in PUBLIC:
            target = public/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/relative,target)
        ref = load('receive_frozen_reference',public/'lib/kotoba.kekkai/tools/application_response_reference.py')
        data,cases = ref.fixtures(a.small_development_probe,a.role=='initiator')
        font = bytearray((stage/'boot-font.bin').read_bytes())
        font[393216:] = data+bytes(131072-len(data))
        (stage/'boot-font.bin').write_bytes(font)
        flags = next(x['argv'][:-2] for x in baseline['calls'] if x['label'] == 'compile-KERNEL.ELF')
        flags[3] = 'x86_64-aiueos-kernel-v4'
        roots = flags[8:flags.index('--source-lock')]
        for root in roots[1::2]: (stage/root.lstrip('/')).mkdir(parents=True,exist_ok=True)
        report.update(overlays={p:pin(ROOT/p) for p in overlays.values()},nativeFixture=pin(new_gate),
            publicFixtureSources={p:pin(public/p) for p in PUBLIC},bootFont=pin(stage/'boot-font.bin'),
            userSlot=pin(stage/'boot-user-slot.bin'),fixture=dict(bytes=len(data),sha256=digest(data),cases=len(cases),managedRole=a.role,
            smallDevelopmentProbe=a.small_development_probe))

        def run(label,argv):
            try:
                result = mac.native_run(a.compiler,stage,*argv)
            except ValueError:
                # Preserve the complete native diagnostic with the identical
                # compiler/FD3 root. A refused build remains an unsuccessful
                # probe; this is not a host fallback or fault-detection pass.
                result = mac.native_run(a.compiler,stage,*argv,expected=1)
            (out/(label+'.stdout')).write_bytes(result.stdout)
            (out/(label+'.stderr')).write_bytes(result.stderr)
            report['calls'].append(dict(label=label,argv=argv,exit=result.returncode))
            save()
            if result.returncode: raise RuntimeError('native command failed: '+label)
            return result.stdout
        raw = run('modules',['modules',entry,*roots])
        graph = {}
        for line in raw.decode().splitlines():
            namespace,virtual = line.split(' ',1)
            graph[virtual] = pin(stage/virtual.lstrip('/'))['sha256']
        assert len(graph) == 45
        lock = ('KSL1\nentry '+entry+'\n'+''.join('root '+v+'\n' for v in roots[1::2])+
            ''.join('file '+v+' '+k+'\n' for k,v in sorted(graph.items()))).encode()
        (stage/'receive.ksl').write_bytes(lock)
        flags[-3],flags[-1] = 'receive.ksl',digest(lock)
        report.update(sourceGraph=graph,sourceLock=pin(stage/'receive.ksl'))
        for name in ['kernel.elf','kernel-repeat.elf']: run(name,[*flags,'--output',name])
        assert pin(stage/'kernel.elf') == pin(stage/'kernel-repeat.elf')
        for name in ['boot.efi','boot-repeat.efi']:
            run(name,['package-aiueos-boot','kernel.elf','--output',name,'--font','boot-font.bin',
                '--user-slot','boot-user-slot.bin','--pci-resources','v1'])
        assert pin(stage/'boot.efi') == pin(stage/'boot-repeat.efi')
        raw = (stage/'kernel.elf').read_bytes()
        ph = struct.unpack_from('<Q',raw,32)[0]
        assert struct.unpack_from('<H',raw,56)[0] == 2
        rx,rw = [struct.unpack_from('<IIQQQQQQ',raw,ph+i*56) for i in range(2)]
        assert rx[5] <= 2097152-4096 and rw[5] == 2359296
        directory = out/'qemu'
        (directory/'esp/EFI/BOOT').mkdir(parents=True)
        shutil.copyfile(stage/'boot.efi',directory/'esp/EFI/BOOT/BOOTX64.EFI')
        peer = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        peer.bind(('127.0.0.1',0))
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as reserve:
            reserve.bind(('127.0.0.1',0))
            target = ('127.0.0.1',reserve.getsockname()[1])
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as reserve:
            reserve.bind(('127.0.0.1',0))
            gdb_port = reserve.getsockname()[1]
        command = [str(a.qemu),'-machine','q35,accel=tcg,i8042=off','-cpu','max,phys-bits=37',
            '-m','128M','-smp','1','-drive','if=pflash,format=raw,readonly=on,file='+str(a.firmware),
            '-drive','file=fat:rw:esp,format=raw','-boot','order=c','-display','none','-no-reboot','-no-shutdown',
            '-serial','file:serial.log','-debugcon','file:debug.log','-netdev',
            f'dgram,id=link,local.type=inet,local.host=127.0.0.1,local.port={target[1]},remote.type=inet,remote.host=127.0.0.1,remote.port={peer.getsockname()[1]}',
            '-device','rtl8139,netdev=link,mac=52:54:00:12:34:56,addr=0x4',
            '-gdb',f'tcp:127.0.0.1:{gdb_port}','-qmp','stdio']
        report.update(state='BOOTING',kernel=pin(stage/'kernel.elf'),efi=pin(stage/'boot.efi'),
            layout=dict(rx=rx,rw=rw),command=command)
        save()
        with (directory/'qemu.stderr').open('wb') as error_log:
            proc = subprocess.Popen(command,cwd=directory,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=error_log,bufsize=0)
            q = pool.QMP(proc)
            gdb = checkpoint.GDB(gdb_port)
            # The new test GDB attachment pauses the initial guest.
            # Resume exactly once; only our later observation checkpoints pause.
            initial_status = q.call('query-status')
            report['statusAfterGDBAttach'] = initial_status
            if not initial_status['running']: q.call('cont')
            save()

            class Boot:
                work = 0x63a000
                def __init__(self): self.proc = proc
                def dump(self,at,size): return q.dump(at,size,directory,'read-last.bin')
                def W(self,i): return struct.unpack('<I',self.dump(self.work+i*4,4))[0]
            boot = Boot()
            until,phase,before = time.monotonic()+600,0,None
            while boot.W(79) != 1:
                if proc.poll() is not None: raise RuntimeError('QEMU terminated before NIC')
                private = boot.dump(0x400000,65536)
                scratch = struct.unpack_from('<Q',private,272)[0]
                receipt = boot.dump(scratch,4096) if scratch else bytes(4096)
                if struct.unpack_from('<Q',receipt)[0] == 0x315642524b:
                    current = struct.unpack_from('<Q',receipt,40)[0]
                    kind = struct.unpack_from('<Q',receipt,64)[0]
                    if current > phase:
                        assert current == phase+1 and kind in [1,2]
                        q.call('stop')
                        addresses = struct.unpack('<8I',boot.dump(boot.work+400,32))
                        bases = [addresses[i]+(addresses[i+1] << 32) for i in range(0,8,2)]
                        bases.append(boot.W(114)+(boot.W(115)<<32))
                        names = ['session','io','log','pool','pending']
                        owners = {name:boot.dump(base,8388608 if name=='pool' else 262144) for name,base in zip(names,bases)}
                        for name,value in owners.items():
                            packed = gzip.compress(value,compresslevel=3,mtime=0)
                            path = out/f'shape-{current:03}-{name}.gz'
                            path.write_bytes(packed)
                            assert gzip.decompress(path.read_bytes()) == value
                        match = True
                        if kind == 1:
                            assert before is None
                            before = owners
                        else:
                            assert before is not None
                            match = owners == before
                            before = None
                            if not match: report['observationFailures'].append('shape '+str(current))
                        report['shapeCheckpoints'].append(dict(phase=current,kind=kind,match=match,
                            owners={k:dict(bytes=len(v),sha256=digest(v)) for k,v in owners.items()}))
                        save()
                        gdb.ack_checkpoint(scratch+48,current)
                        phase = current
                        q.call('cont')
                        if kind == 2: print('receive/controller guard',phase//2,'/53',match,flush=True)
                if time.monotonic() >= until: raise TimeoutError('native bridge setup not complete')
                time.sleep(.02)
            assert phase == 106 and before is None and boot.W(108) == 38 and boot.W(119) == 15
            report['state'] = 'NATIVE_RECEIVE_RUNNING'
            save()
            observer = load('receive_frozen_peer',public/'scripts/native_application_response_peer.py')
            result,good = observer.exercise(boot,peer,target,out,a.small_development_probe,a.role=='initiator')
            report['receiveResult'] = result
            completed = (result['observed']['terminal'] == 2 and result['observed']['cases'] == len(cases)
                and result['observed']['released'] == len(cases) and result['observed']['rxErrors'] == 0)
            if a.fault:
                assert completed and not good and (result['observed']['nativeErrors'] > 0 or report['observationFailures'])
                report['state'] = 'DETECTED_NORMALLY_COMPLETED_RECEIVE_FAULT'
            else:
                assert good and not report['observationFailures'],result['violations'][:12]
                report['state'] = 'PASS_DEVELOPMENT_RECEIVE_PROBE' if a.small_development_probe else 'PASS_FULL_NATIVE_APPLICATION_RECEIVE'
            save()
            print(report['state'],len(cases),rx[5],flush=True)
    except BaseException as error:
        report.update(state='FAILED',failure=str(error),failureType=type(error).__name__)
        save()
        raise
    finally:
        if proc is not None and proc.poll() is None:
            try: q.call('quit')
            except Exception: proc.terminate()
            proc.wait(timeout=10)
        if gdb is not None: gdb.close()
        if peer is not None: peer.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',type=Path,required=True)
    parser.add_argument('--compiler-profile',choices=sorted(COMPILER_PROFILES),required=True)
    parser.add_argument('--amu-source',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--qemu',type=Path,required=True)
    parser.add_argument('--qemu-sha256',required=True)
    parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--firmware-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--role',choices=['responder','initiator'],default='responder')
    parser.add_argument('--small-development-probe',action='store_true')
    parser.add_argument('--fault',choices=sorted(FAULTS))
    main(parser.parse_args())
