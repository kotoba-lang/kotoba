#!/usr/bin/env python3
"""Observe the actual native NVMe/ESP journal, including cold-boot refusals.

Private fixture media only. Python observes native decisions and audits disk
bytes; it does not implement the journal state machine or grant boot health.
The component image disables user mode/refuses user ABI calls. The full
product's real ValueRuntime and USB/NVMe gates are separate and unchanged.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct

HERE = Path(__file__).resolve().parent


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE/file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


keys = module('journal_keys', 'check-native-keystore-qemu.py')
nvme = module('journal_nvme', 'check-native-nvme-qemu.py')
nvme.OWN_SIZE = 4096


def pin(p):
    data = p.read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def layout(raw):
    v = nvme.fat32_volume(raw)
    efi = nvme.fat32_dir(raw, v, v['root'])['EFI        '][0]
    own = nvme.fat32_dir(raw, v, efi)['ITONAMI    '][0]
    return v, nvme.fat32_dir(raw, v, own)


def main(a):
    for n in ('kernel', 'efi', 'media', 'qemu', 'firmware'):
        setattr(a, n, getattr(a, n).resolve(strict=True))
    assert pin(a.qemu)['sha256'] == a.qemu_sha256
    assert pin(a.firmware)['sha256'] == a.firmware_sha256
    assert a.efi.read_bytes().count(a.kernel.read_bytes()) == 1
    out = a.output.resolve(); out.mkdir(mode=0o700, parents=True, exist_ok=False)
    disk = out/'state.raw'; nvme.fat32_disk(out, disk)
    original = disk.read_bytes(); events = []; status = 'FAILED'
    bootstrap_media = pin(a.media)

    def boot(name, path=disk, action='0'):
        assert action in '0123456789AB'
        before = path.read_bytes(); variables = out/(name+'-vars.fd')
        shutil.copyfile(a.firmware.with_name('edk2-i386-vars.fd'), variables)
        b = keys.Boot.__new__(keys.Boot)
        try:
            keys.Boot.__init__(b, a, out, name, None, [
                '-cpu','max,phys-bits=37',
                '-drive',f'if=pflash,format=raw,file={variables}',
                '-drive',f'file={path},format=raw,if=none,id=nv0,cache=directsync',
                '-device','nvme,serial=AWAI122JOURNAL,drive=nv0',
                '-fw_cfg',f'name=opt/aiueos/journal,string={action}'], first_frame_seconds=180)
            c = struct.unpack('<224I', b.dump(b.work, 896))
            result = c[74] if c[74] < 2**31 else c[74]-2**32
            metadata = dict(offset=c[212]+(c[213]<<32), generation=c[215], phase=c[216], policy=c[217],
                            floor=c[218]+(c[219]<<32), confirmed=c[220]+(c[221]<<32), candidate=c[222]+(c[223]<<32))
            events.append(dict(name=name, action=action, result=result, metadata=metadata))
        finally:
            if hasattr(b,'proc'): b.quit()
        after = path.read_bytes()
        if action in '06789':
            assert after == before, (name, 'read/refusal modified disk')
        return result, metadata, before, after

    def clone(name, raw):
        p = out/(name+'.raw'); p.write_bytes(raw); return p

    try:
        r, _, _, _ = boot('absent-read-only')
        assert r == -70 and disk.read_bytes() == original
        r, m, _, saved = boot('provision-and-prepare', action='1')
        assert r == 2 and m['generation'] == 2 and m['phase'] == 1
        assert m['floor'] == 5 and m['confirmed'] == 3 and m['candidate'] == 5 and m['policy'] == 3
        v, entries = layout(saved); meta = entries['OSMETA  BIN']; state = entries['STATE   BIN']
        assert meta[1] == state[1] == 20480
        mc = nvme.fat32_chain(saved,v,meta[0]); sc = nvme.fat32_chain(saved,v,state[0])
        assert not set(mc)&set(sc)
        at = v['data']+(meta[0]-2)*v['cluster']; st = v['data']+(state[0]-2)*v['cluster']
        assert at == m['offset'] and at % 4096 == st % 4096 == 0
        assert saved[at:at+8] == b'OSUPMETA' and saved[st:st+8] == b'AWAIDRFT'
        state_bytes = saved[st:st+20480]
        assert saved[:v['base']] == original[:v['base']] and saved[v['end']:] == original[v['end']:]
        assert nvme.fat32_files(saved)[1]['BOOTX64 EFI'][0] == nvme.fat32_files(original)[1]['BOOTX64 EFI'][0]
        for k in range(1,v['fats']):
            assert saved[v['fat']:v['fat']+v['fat_bytes']] == saved[v['fat']+k*v['fat_bytes']:v['fat']+(k+1)*v['fat_bytes']]
        r, m, _, _ = boot('cold-prepared')
        assert r == 2 and m['floor'] == 5 and m['phase'] == 1
        r, _, _, _ = boot('duplicate-prepare-refused', action='6'); assert r == -87
        r, m, _, trial = boot('trial-published', action='2')
        assert r == 3 and m['phase'] == 2 and m['confirmed'] == 3
        r, _, _, _ = boot('wrong-confirm-digest-refused', action='9'); assert r == -89
        r, m, _, _ = boot('confirm-exact-candidate', action='3')
        assert r == 4 and m['phase'] == 0 and m['confirmed'] == m['floor'] == 5 and m['candidate'] == 0
        r, m, _, rolled = boot('failed-trial-keeps-floor', action='4')
        assert r == 7 and m['phase'] == 3 and m['confirmed'] == 5 and m['floor'] == 6
        r, _, _, _ = boot('rollback-release-replay-refused', action='6'); assert r == -87
        r, m, _, _ = boot('policy-persisted', action='5'); assert r == 8 and m['policy'] == 7
        r, m, _, _ = boot('cold-policy'); assert r == 8 and m['policy'] == 7 and m['floor'] == 6
        r, _, _, _ = boot('existing-journal-not-reinitialized', action='7'); assert r == -86
        r, _, _, _ = boot('unknown-policy-bit-refused', action='8'); assert r == -91
        r, m, _, _ = boot('u64-floor-above-u32', action='A')
        assert r == 11 and m['floor'] == 4294967297 and m['confirmed'] == 5
        r, m, _, _ = boot('u64-positive-limit', action='B')
        assert r == 14 and m['floor'] == 9223372036854775807 and m['confirmed'] == 5
        r, m, _, _ = boot('cold-u64-limit'); assert r == 14 and m['floor'] == 9223372036854775807
        # Restore the earlier native head over a valid newer native slot.
        # This models a crash before publication without manufacturing records.
        unpublished = bytearray(trial); unpublished[at+4096:at+8192] = saved[at+4096:at+8192]
        r, m, _, _ = boot('unpublished-valid-slot-ignored', clone('unpublished',unpublished))
        assert r == 2 and m['phase'] == 1
        for label, offset in [('marker',0),('head',4096),('published-slot',3*4096),
                              ('published-payload',3*4096+100),('head-digest',4096+480),('marker-reserved',32)]:
            bad = bytearray(trial); bad[at+offset] ^= 1
            r, _, _, _ = boot('corrupt-'+label, clone('corrupt-'+label,bad))
            assert r < 0
        # Checksummed but invalid schemas must still refuse. Hashing bytes is
        # an independent data oracle; all admission decisions remain native.
        for label, relative, value in [('policy',12,8),('phase',16,99),
                                      ('reserved',168,1),('negative-floor-high',36,0x80000000),
                                      ('candidate-floor-mismatch',40,7)]:
            bad = bytearray(trial); pos = at+3*4096
            struct.pack_into('<I',bad,pos+relative,value)
            digest = hashlib.sha256(bad[pos:pos+480]).digest()
            bad[pos+480:pos+512] = digest
            bad[at+4096+480:at+4096+512] = digest
            r, _, _, _ = boot('invalid-schema-'+label,clone('invalid-schema-'+label,bad)); assert r == -76
        alias = bytearray(saved)
        struct.pack_into('<H',alias,meta[2]+20,state[0]>>16); struct.pack_into('<H',alias,meta[2]+26,state[0]&65535)
        r, _, _, _ = boot('cross-file-alias-refused',clone('alias',alias)); assert r == -70
        bad = bytearray(saved); bad[528] ^= 1; bad[-512+16] ^= 1
        r, _, _, _ = boot('bad-gpt-crc-refused',clone('bad-gpt',bad)); assert r == -70
        current = disk.read_bytes()
        assert current[st:st+20480] == state_bytes, 'journal changed app-state file'
        assert pin(a.media) == bootstrap_media
        status = 'PASS_NATIVE_UPDATE_JOURNAL_QEMU'
    finally:
        (out/'receipt.json').write_text(json.dumps(dict(status=status, events=events,
            artifacts={n:pin(getattr(a,n)) for n in ('kernel','efi','media','qemu','firmware')},
            observer=pin(Path(__file__)), helper=pin(HERE/'check-native-keystore-qemu.py'),
            syntheticDigestAndHealth=True, automaticUpdateIntegrated=False, productionValueRuntimeQualified=False,
            physicalHardware=False, powerCutHardwareQualified=False, tpmAntiRollback=False),indent=2)+'\n')
    print(status,len(events),'boots')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('kernel','efi','media','qemu','firmware','output'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('qemu-sha256','firmware-sha256'):
        p.add_argument('--'+name,required=True)
    main(p.parse_args())
