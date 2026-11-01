#!/usr/bin/env python3
"""Observe native one-at-a-time xHCI selection and refusal on private QEMU media."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

if not __debug__:
    raise RuntimeError('do not run this assertion observer with Python -O')


def pin(path):
    b = path.read_bytes()
    return {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}


def main(a):
    for n in ('efi', 'kernel', 'media', 'qemu', 'firmware'):
        setattr(a, n, getattr(a, n).resolve(strict=True))
    assert pin(a.qemu)['sha256'] == a.qemu_sha256
    assert pin(a.firmware)['sha256'] == a.firmware_sha256
    assert a.efi.read_bytes().count(a.kernel.read_bytes()) == 1
    before = pin(a.media)
    out = a.output.resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    debug = out / 'debug.log'
    cmd = [str(a.qemu), '-machine', 'q35,accel=tcg,i8042=off', '-cpu', 'max,phys-bits=37',
           '-m', '128M', '-smp', '1', '-drive', f'if=pflash,format=raw,readonly=on,file={a.firmware}',
           '-drive', f'file={a.media},format=raw,if=ide,snapshot=on', '-boot', 'order=c',
           '-device', 'qemu-xhci,id=empty', '-device', 'qemu-xhci,id=hid',
           '-device', 'usb-kbd,bus=hid.0,port=1', '-device', 'usb-mouse,bus=hid.0,port=2',
           '-nic', 'none', '-display', 'none', '-no-reboot', '-serial', 'none',
           '-debugcon', f'file:{debug}', '-monitor', 'stdio']
    (out / 'command.json').write_text(json.dumps(cmd, indent=2) + '\n')
    status = 'FAILED'
    with (out / 'qemu.log').open('wb') as log:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log, stderr=log)
        try:
            end = time.monotonic() + 180
            while time.monotonic() < end:
                data = debug.read_bytes() if debug.exists() else b''
                if b'USBSEL ' in data:
                    assert b'USBSEL ffff\n' in data, data[-1000:]
                    status = 'PASS_NATIVE_USB_CONTROLLER_SELECTION_QEMU'
                    break
                assert p.poll() is None, (p.returncode, (out / 'qemu.log').read_text()[-1000:])
                time.sleep(.1)
            else:
                raise AssertionError('native USB selection marker not observed')
            assert pin(a.media) == before
        finally:
            if p.poll() is None:
                p.stdin.write(b'quit\n')
                p.stdin.flush()
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(timeout=10)
            (out / 'receipt.json').write_text(json.dumps({
                'status': status, 'nativeMask': 'ffff' if status.startswith('PASS') else None,
                'checks': ['initial fallback HID', 'two initial HID', 'out-of-range refusal',
                           'non-xHCI refusal', 'refusals retain HID count', 'select empty host',
                           'reselect HID host', 'draft range retained', 'NVMe state range retained', 'failed host refuses DMA reuse',
                           'HCI18 framing vectors', 'non-Bluetooth probe refused', 'large HCI complete accepted', 'oversized HCI complete refused', 'HOGP14 native keyboard report/admission refusals', 'mouse16 descriptor/decode controls', 'mouse8 encrypted-handle admission controls', 'LE6 non-flushable ACL header controls', 'USB OUT buffer rejects writes while device owns it', 'SMP10 passkey method/feature rejection controls', 'legacy c1 p1/p2 wire-endian layout against Core sample'],
                'artifacts': {n: pin(getattr(a, n)) for n in ('efi', 'kernel', 'media', 'qemu', 'firmware')},
                'observer': pin(Path(__file__)), 'physicalHardware': False,
                'BluetoothTransportQualified': False, 'simultaneousHosts': False,
            }, indent=2) + '\n')
    print(status)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for n in ('efi', 'kernel', 'media', 'qemu', 'firmware', 'output'):
        parser.add_argument('--' + n, type=Path, required=True)
    for n in ('qemu-sha256', 'firmware-sha256'):
        parser.add_argument('--' + n, required=True)
    main(parser.parse_args())
