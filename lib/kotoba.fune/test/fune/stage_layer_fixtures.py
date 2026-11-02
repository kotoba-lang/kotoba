#!/usr/bin/env python3
"""Stage deterministic independent ustar/OCI byte fixtures; never decide a test verdict."""
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)

def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()

def archive(name, kind=tarfile.REGTYPE, data=b'abc', link=''):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        entry = tarfile.TarInfo(name)
        entry.type = kind
        entry.linkname = link
        entry.mode = 0o755 if kind == tarfile.DIRTYPE else 0o644
        entry.size = len(data) if kind == tarfile.REGTYPE else 0
        tar.addfile(entry, io.BytesIO(data) if entry.size else None)
    # Python tarfile pads to its 10 KiB record size; a tar ends with two blocks.
    size = 512 + ((entry.size + 511) // 512) * 512 + 1024
    return buf.getvalue()[:size]

def fix_checksum(buf):
    buf[148:156] = b'        '
    checksum = sum(buf[:512])
    buf[148:156] = ('%06o\0 ' % checksum).encode('ascii')

def multi_archive():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for name, data in [('one', b'a'), ('two', b'bc')]:
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            tar.addfile(entry, io.BytesIO(data))
    return buf.getvalue()[:3072]  # two header/data pairs and two zero blocks

valid = archive('bin/hello')
checksum = bytearray(valid)
checksum[0] ^= 1
terminator = bytearray(valid)
terminator[-1] = 1
numeric = bytearray(valid)
numeric[124:136] = b'\0' * 12
fix_checksum(numeric)
long_size = bytearray(valid)
long_size[124:136] = b'00000010000\0'  # 4096 bytes but less than that follows
fix_checksum(long_size)
cases = {
    'good': valid,
    'directory': archive('bin/', tarfile.DIRTYPE, b''),
    'prefix': archive('a' * 90 + '/' + 'b' * 40),
    'multi': multi_archive(),
    'absolute': archive('/etc/passwd'),
    'traversal': archive('bin/../escape'),
    'whiteout': archive('bin/.wh.removed'),
    'symlink': archive('bin/link', tarfile.SYMTYPE, b'', '../escape'),
    'device': archive('bin/dev', tarfile.CHRTYPE, b''),
    'checksum': bytes(checksum),
    'terminator': bytes(terminator),
    'numeric': bytes(numeric),
    'truncated': bytes(long_size),
    'pax': archive('header', tarfile.XHDTYPE, b''),
}
for name, data in cases.items():
    config = json.dumps({'architecture':'arm64', 'os':'linux',
        'rootfs':{'type':'layers','diff_ids':[sha(data)]},
        'config':{'Entrypoint':['/bin/hello'],'Cmd':[],'Env':[],'WorkingDir':'/'}},
        separators=(',', ':')).encode()
    manifest = json.dumps({'schemaVersion':2, 'mediaType':'application/vnd.oci.image.manifest.v1+json',
        'config':{'mediaType':'application/vnd.oci.image.config.v1+json','digest':sha(config),'size':len(config)},
        'layers':[{'mediaType':'application/vnd.oci.image.layer.v1.tar','digest':sha(data),'size':len(data)}]},
        separators=(',', ':')).encode()
    (out / (name + '.tar')).write_bytes(data)
    (out / (name + '.config')).write_bytes(config)
    (out / (name + '.manifest')).write_bytes(manifest)
    print(name, sha(manifest), sha(data), len(data))
