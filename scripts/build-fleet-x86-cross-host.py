#!/usr/bin/env python3
"""Build synthetic ARM and explicitly admitted x86 fleet test endpoints.

Usage: AMU_DIR CANDIDATE_COMPILER CANDIDATE_SHA256 NEW_OUTPUT
Uses test fixtures and deterministic test keys only. No live fleet or release.
"""
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

if len(sys.argv) != 5:
    raise SystemExit(__doc__)
amu, compiler = (Path(p).resolve(strict=True) for p in sys.argv[1:3])
expected = sys.argv[3]
out = Path(sys.argv[4]).resolve()
root = Path(__file__).resolve().parents[1]
sha = lambda data: hashlib.sha256(data).hexdigest()
if not re.fullmatch(r'[0-9a-f]{64}', expected) or sha(compiler.read_bytes()) != expected:
    raise ValueError('candidate compiler digest mismatch')
base_compiler = amu / 'seed/bootstrap/aarch64-macos/amu-full-root.macho'
subprocess.run([sys.executable, str(root / 'scripts/build-fleet-cross-host.py'), str(amu), str(out), sha(base_compiler.read_bytes())], check=True)
spec = importlib.util.spec_from_file_location('mac', amu / 'scripts/seed/check-aiueos-user-macos-native.py')
mac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mac)
lock = sha((out / 'sources.ksl').read_bytes())
mac.native_run(compiler, out, 'compile', '/src/noise/tcp_demo.kotoba', '--target', 'x86_64-linux',
               '--format', 'kx64-v1', '--source-path', '/src', '--source-lock', 'sources.ksl',
               '--source-lock-sha256', lock, '--output', 'guest-x86.kx64',
               '--project-capabilities', '35,38,43,44,45,46,47')
header, payload = (out / 'guest-x86.kx64').read_bytes().split(b'\n\n', 1)
match = re.fullmatch(rb'KX64V1 x86_64-linux sysv-ctx-v11 ([0-9]+) 0', header)
if not match or len(payload) != int(match[1]) or payload[0] != 0xe9:
    raise ValueError('invalid x86 payload')
(out / 'guest-x86.bin').write_bytes(payload)
mac.native_run(compiler, out, 'compile', 'runner.kotoba', '--target', 'x86_64-linux',
               '--output', 'runner-x86.elf', '--format', 'kx64-runner')
(out / 'runner-x86.elf').chmod(0o700)
result = {'status': 'PASS_SYNTHETIC_FLEET_ARM_X86_BUILD', 'candidateCompilerSha256': expected,
          'sourceLockSha256': lock, 'armBuild': json.loads((out / 'build.json').read_text()),
          'x86Artifacts': {name: sha((out / name).read_bytes()) for name in ('guest-x86.kx64', 'guest-x86.bin', 'runner-x86.elf')},
          'scope': 'Synthetic candidate only; no live fleet, production keys or deployment.'}
(out / 'cross-build.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['status'], flush=True)
