#!/usr/bin/env python3
"""Observe current office source compilation boundaries; this is not OS execution.

Usage: python3 scripts/check-office-qemu-compile-boundary.py AMU BUNSHO_BUILD HYOKEISAN_BUILD ZUHYO_BUILD OUT
All build inputs must be existing candidate directories with matching receipts.
"""
import hashlib
import importlib.util
import json
import re
import struct
import sys
from pathlib import Path

if len(sys.argv) != 6:
    raise SystemExit(__doc__)
amu, *args = (Path(x).resolve() for x in sys.argv[1:])
builds = dict(zip(('bunsho', 'hyokeisan', 'zuhyo'), args[:3]))
out = args[3]
out.mkdir(parents=True, exist_ok=False)
compiler = amu / 'seed/bootstrap/aarch64-macos/amu-full-root.macho'
sha = lambda b: hashlib.sha256(b).hexdigest()
spec = importlib.util.spec_from_file_location('native', amu / 'scripts/seed/check-aiueos-user-macos-native.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
compiler_hash = sha(compiler.read_bytes())
results = {}
# Positive control: this compiler and user-v5 layout can emit a scalar ELF.
(out / 'scalar.kotoba').write_text('(ns scalar (:export [main]))\n(defn main [p :i64 n :i64] :i64 (+ p n))\n')
native.native_run(compiler, out, 'compile', 'scalar.kotoba', '--target', 'x86_64-aiueos-user-v5', '--output', 'scalar.elf')
scalar = (out / 'scalar.elf').read_bytes()
if not scalar.startswith(b'\x7fELF'):
    raise ValueError('positive control is not ELF')
for name, build in builds.items():
    receipt = json.loads((build / 'build-receipt.json').read_text())
    source = (build / 'program.kotoba').read_bytes()
    wasm = (build / 'program.wasm').read_bytes()
    if (sha(source) != receipt['sourceSha256'] or sha(wasm) != receipt['wasmSha256']
            or receipt['compilerSha256'] != compiler_hash):
        raise ValueError(name + ': stale candidate receipt')
    src = name + '.kotoba'
    (out / src).write_bytes(source)
    native.native_run(compiler, out, 'compile', src, '--target', 'x86_64-linux', '--output', name + '.kx64', '--format', 'kx64-v1')
    raw = (out / (name + '.kx64')).read_bytes()
    header, code = raw.split(b'\n\n', 1)
    match = re.fullmatch(rb'KX64V1 x86_64-linux sysv-ctx-v11 ([0-9]+) 0', header)
    if match is None or int(match.group(1)) != len(code) or len(code) <= 4096:
        raise ValueError(name + ': unexpected KX64 header or code size')
    # Measure a complete selfhost x86 image including its Linux runtime. This
    # is a sizing observation only; it is not an AIUEOS-loadable artifact.
    static_name = name + '.linux.elf'
    static = native.native_run(compiler, out, 'compile', src, '--target', 'x86_64-linux',
                               '--output', static_name, '--format', 'static')
    image = (out / static_name).read_bytes()
    if len(image) < 64 or image[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', image, 18)[0] != 62:
        raise ValueError(name + ': invalid ELF64 x86 image')
    phoff = struct.unpack_from('<Q', image, 32)[0]
    entsize, count = struct.unpack_from('<HH', image, 54)
    if entsize != 56 or not 1 <= count <= 16 or phoff + entsize * count > len(image):
        raise ValueError(name + ': malformed program header table')
    segments = []
    for i in range(count):
        typ, flags, offset, addr, _, file_size, mem_size, align = struct.unpack_from('<IIQQQQQQ', image, phoff + i * entsize)
        if typ == 1:
            if file_size > mem_size or offset + file_size > len(image) or flags & 3 == 3:
                raise ValueError(name + ': malformed or writable-executable segment')
            segments.append({'flags': flags, 'fileBytes': file_size, 'memoryBytes': mem_size, 'alignment': align})
    if len(segments) != 2 or [x['flags'] for x in segments] != [5, 6]:
        raise ValueError(name + ': unexpected Linux static load segments')
    refusal = native.native_run(compiler, out, 'compile', src, '--target', 'x86_64-aiueos-user-v5', '--output', name + '.elf', expected=1)
    if b'E2101' not in refusal.stderr or (out / (name + '.elf')).exists():
        raise ValueError(name + ': user-v5 refusal changed')
    results[name] = {'sourceSha256': sha(source), 'wasmSha256': sha(wasm),
                     'kx64Sha256': sha(raw), 'kx64CodeBytes': len(code),
                     'linuxStaticSha256': sha(image), 'linuxStaticBytes': len(image),
                     'linuxStaticLoadSegments': segments, 'linuxStaticCompilerOutput': static.stdout.decode('utf-8').strip(),
                     'v5Stderr': refusal.stderr.decode('utf-8').strip()}
report = {'status': 'PASS_COMPILE_BOUNDARY_ONLY', 'compilerSha256': compiler_hash,
          'observerSha256': sha(Path(__file__).read_bytes()),
          'scalarV5ElfSha256': sha(scalar), 'apps': results,
          'limitations': ['unadapted browser entry; not a QEMU app execution',
                          'KX64 requires its host runtime and context v11',
                          'Linux static runtime uses Linux syscalls and anonymous mappings; ELF segments exclude mapped arenas and do not measure RSS',
                          'v5 4096-byte RX is insufficient for these generated code sizes',
                          'no OS adapter, migration, or release qualification']}
(out / 'receipt.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(report['status'])
