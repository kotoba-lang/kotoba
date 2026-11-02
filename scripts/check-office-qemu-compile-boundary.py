#!/usr/bin/env python3
"""Observe current office source compilation boundaries; this is not OS execution.

Usage: python3 scripts/check-office-qemu-compile-boundary.py AMU BUNSHO_BUILD HYOKEISAN_BUILD ZUHYO_BUILD OUT
All build inputs must be existing candidate directories with matching receipts.
"""
import hashlib
import importlib.util
import json
import re
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
    refusal = native.native_run(compiler, out, 'compile', src, '--target', 'x86_64-aiueos-user-v5', '--output', name + '.elf', expected=1)
    if b'E2101' not in refusal.stderr or (out / (name + '.elf')).exists():
        raise ValueError(name + ': user-v5 refusal changed')
    results[name] = {'sourceSha256': sha(source), 'wasmSha256': sha(wasm),
                     'kx64Sha256': sha(raw), 'kx64CodeBytes': len(code),
                     'v5Stderr': refusal.stderr.decode('utf-8').strip()}
report = {'status': 'PASS_COMPILE_BOUNDARY_ONLY', 'compilerSha256': compiler_hash,
          'observerSha256': sha(Path(__file__).read_bytes()),
          'scalarV5ElfSha256': sha(scalar), 'apps': results,
          'limitations': ['unadapted browser entry; not a QEMU app execution',
                          'KX64 requires its host runtime and context v11',
                          'v5 4096-byte RX is insufficient for these generated code sizes',
                          'no OS adapter, migration, or release qualification']}
(out / 'receipt.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(report['status'])
