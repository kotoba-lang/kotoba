#!/usr/bin/env python3
"""Observe native profile metadata and the byte-exact public KAT table packing.

The old literal fixture is data, not a host crypto implementation. This gate
compares every native selector byte (including padding and out-of-range reads).
It does not qualify renderer speed, Bluetooth pairing, or physical hardware.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('profile_boot', HERE/'check-native-keystore-qemu.py')
keys = importlib.util.module_from_spec(spec); spec.loader.exec_module(keys)


def pin(p):
    data = p.read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main(a):
    for name in ('efi', 'kernel', 'media', 'qemu', 'firmware', 'fixture'):
        setattr(a, name, getattr(a, name).resolve(strict=True))
    assert pin(a.qemu)['sha256'] == a.qemu_sha256
    assert pin(a.firmware)['sha256'] == a.firmware_sha256
    assert a.efi.read_bytes().count(a.kernel.read_bytes()) == 1
    tables = json.loads(a.fixture.read_text())['fixtures']
    assert len(tables) == 19
    expected = b''
    for table in tables:
        data = bytes(table['bytes'])
        assert len(data) == table['length'] <= 64
        assert hashlib.sha256(data).hexdigest() == table['sha256']
        expected += data.ljust(64, b'\0')
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False, mode=0o700)
    before = pin(a.media); b = None; status = 'FAILED'; metadata = None
    try:
        b = keys.Boot.__new__(keys.Boot)
        keys.Boot.__init__(b, a, out, 'profile', None, first_frame_seconds=180)
        assert b.W(74) == 63, ('native metadata fixture mask', b.W(74))
        got = b.dump(b.work+1024, 1216)
        assert got == expected, 'native packed public bytes differ from original literals'
        assert b.dump(b.work+2240, 38) == bytes(38), 'out-of-range case default changed'
        # A wrong public oracle must be detected, independently of hashes.
        changed = bytearray(expected); changed[0] ^= 1
        assert got != changed
        (out/'public-table-bytes.bin').write_bytes(got)
        values = struct.unpack('<41I', b.dump(b.work+8192+352, 164))
        metadata = dict(zip(range(88, 129), values))
        assert values[20] == 1 and values[22] == 1 and values[23] == 0
        wide = lambda at: values[at-88] + (values[at-87] << 32)
        assert wide(118) == wide(100) > 0
        assert wide(112) == wide(92) and wide(114) == wide(94) and wide(116) == wide(98)
        assert wide(124) == wide(120) > 0 and wide(126) == wide(122) > 0
        assert values[40] == 1515870810, 'adjacent motion-state sentinel changed'
        assert pin(a.media) == before
        status = 'PASS_NATIVE_RENDER_PROFILE_QEMU'
    finally:
        if b is not None and hasattr(b, 'proc'):
            b.quit()
        (out/'receipt.json').write_text(json.dumps(dict(
            status=status, comparedNativeSelectorBytes=1216, outOfRangeBytes=38,
            changedOracleRejected=True if status.startswith('PASS') else None,
            publicOriginalBytes=sum(t['length'] for t in tables), metadata=metadata,
            artifacts={n:pin(getattr(a,n)) for n in ('efi','kernel','media','qemu','firmware','fixture')},
            observer=pin(Path(__file__)), helper=pin(HERE/'check-native-keystore-qemu.py'),
            physicalHardwareQualified=False, rendererSpeedQualified=False,
            bluetoothPairingQualified=False), indent=2)+'\n')
    print(status)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('efi','kernel','media','qemu','firmware','fixture','output'):
        p.add_argument('--'+n, type=Path, required=True)
    for n in ('qemu-sha256','firmware-sha256'):
        p.add_argument('--'+n, required=True)
    main(p.parse_args())
