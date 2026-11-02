#!/usr/bin/env python3
"""Observe native console coordinate/key/modal admission; no wire/consent claim."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('console_keys',HERE/'check-native-keystore-qemu.py')
keys = importlib.util.module_from_spec(spec); spec.loader.exec_module(keys)


def pin(p):
    data = p.read_bytes(); return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main(a):
    for n in ('efi','kernel','media','qemu','firmware'):
        setattr(a,n,getattr(a,n).resolve(strict=True))
    assert pin(a.qemu)['sha256'] == a.qemu_sha256
    assert pin(a.firmware)['sha256'] == a.firmware_sha256
    assert a.efi.read_bytes().count(a.kernel.read_bytes()) == 1
    out = a.output.resolve(); out.mkdir(mode=0o700,parents=True,exist_ok=False)
    before = pin(a.media); b = keys.Boot.__new__(keys.Boot); status = 'FAILED'; observed = None
    try:
        keys.Boot.__init__(b,a,out,'console-policy',None,first_frame_seconds=180)
        c = struct.unpack('<178I',b.dump(b.work,712))
        observed = dict(shapeMask=c[74],modalMask=c[75],bandMask=c[76],identityMask=c[77],tailMask=c[78],refusals=c[177],pending=c[87])
        assert observed == dict(shapeMask=1023,modalMask=63,bandMask=255,identityMask=63,tailMask=3,refusals=10,pending=0), observed
        assert pin(a.media) == before
        status = 'PASS_NATIVE_REMOTE_CONSOLE_POLICY_QEMU'
    finally:
        if hasattr(b,'proc'): b.quit()
        (out/'receipt.json').write_text(json.dumps(dict(status=status,observed=observed,
            artifacts={n:pin(getattr(a,n)) for n in ('efi','kernel','media','qemu','firmware')},
            observer=pin(Path(__file__)),helper=pin(HERE/'check-native-keystore-qemu.py'),
            wireSignatureQualified=False,humanApprovalQualified=False,physicalHardware=False,
            productUserABIQualified=False),indent=2)+'\n')
    print(status)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('efi','kernel','media','qemu','firmware','output'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('qemu-sha256','firmware-sha256'):
        p.add_argument('--'+name,required=True)
    main(p.parse_args())
