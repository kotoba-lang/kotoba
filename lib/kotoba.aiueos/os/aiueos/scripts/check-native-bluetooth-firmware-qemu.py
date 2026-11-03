#!/usr/bin/env python3
"""Observe a native firmware admission verdict; no host firmware/parser oracle."""
import argparse,hashlib,json,subprocess,time
from pathlib import Path

def pin(p):
    b=p.read_bytes(); return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def main(a):
    for p,sha in ((a.qemu,a.qemu_sha256),(a.firmware,a.firmware_sha256)):
        if pin(p)['sha256']!=sha: raise ValueError('observer pin mismatch')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False,mode=0o700)
    cmd=[str(a.qemu.resolve()),'-machine','q35,accel=tcg','-cpu','max','-m','128M','-smp','1',
         '-drive',f'if=pflash,format=raw,readonly=on,file={a.firmware.resolve()}',
         '-drive',f'file={a.media.resolve()},format=raw,if=ide,snapshot=on','-boot','order=c',
         '-nic','none','-display','none','-monitor','none','-no-reboot',
         '-debugcon',f'file:{out / "debug.log"}','-global','isa-debugcon.iobase=0xe9',
         '-serial',f'file:{out / "serial.log"}']
    (out/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
    status='BLOCKED_NATIVE_FIRMWARE_GATE'
    with (out/'qemu.log').open('wb') as log:
        p=subprocess.Popen(cmd,stdout=log,stderr=log)
        try:
            until=time.monotonic()+45
            while time.monotonic()<until and p.poll() is None:
                b=(out/'debug.log').read_bytes() if (out/'debug.log').exists() else b''
                if b'FWPK ' in b:
                    if (f'FWPK {a.expected}\n'.encode()) not in b: raise ValueError('unexpected native verdict: '+repr(b[-100:]))
                    status='PASS_NATIVE_FIRMWARE_ADMISSION_QEMU';break
                time.sleep(.1)
        finally:
            if p.poll() is None:p.terminate();p.wait(timeout=5)
    receipt={'status':status,'expectedNativeVerdict':a.expected,'artifacts':{'efi':pin(a.efi),'kernel':pin(a.kernel),'media':pin(a.media)},'qemu':pin(a.qemu),'firmware':pin(a.firmware),'log':pin(out/'debug.log'),'scope':'native pinned-firmware format/digest only; no radio or upload'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    if not status.startswith('PASS'):raise ValueError(status)
    print(status,a.expected)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('efi','kernel','media','qemu','firmware','output'):p.add_argument('--'+n,type=Path,required=True)
    for n in ('qemu-sha256','firmware-sha256'):p.add_argument('--'+n,required=True)
    p.add_argument('--expected',type=int,choices=(0,1),required=True)
    main(p.parse_args())
