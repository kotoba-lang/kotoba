#!/usr/bin/env python3
"""Ensure synthetic QEMU SHA checks detect compiled digest and alias mutants."""
import hashlib, json, shutil, struct, subprocess, sys
from pathlib import Path
if len(sys.argv) != 7:
    raise SystemExit('usage: script AMU COMPILER COMPILER_SHA QEMU FIRMWARE NEW_OUTPUT')
root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[6]).resolve()
if out.exists():
    raise ValueError('output must be new')
out.mkdir(parents=True, mode=0o700)
sha_path = Path('lib/kotoba.aiueos/os/aiueos/kotoba/aiueos/sha256.kotoba')
fixture_path = Path('lib/kotoba.aiueos/test/aiueos/office_sha64_qemu_test.kotoba')
runner_path = Path('scripts/check-office-sha64-qemu.py')
cases = [('digest-bit', '(kernel-load-u8-64k input 65536 global)', '(bit-xor (kernel-load-u8-64k input 65536 global) 1)', 2),
         ('alias-bypass', '(not (disjoint-64k? input 65536 output 32))', 'false', 1)]
results = []
for name, old, new, index in cases:
    base = out / name / 'source'
    for p in (sha_path, fixture_path, runner_path):
        (base / p).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / p, base / p)
    source = (base / sha_path).read_text()
    if source.count(old) != 1:
        raise ValueError('mutation target must be unique: ' + name)
    (base / sha_path).write_text(source.replace(old, new))
    run = subprocess.run([sys.executable, str(base / runner_path), *sys.argv[1:6], str(out / name / 'run')], capture_output=True, text=True)
    (out / name / 'output.txt').write_text(run.stdout + run.stderr)
    final = out / name / 'run/boot/final.bin'
    if run.returncode == 0 or not final.exists() or 'refusal or legacy parity failed' not in run.stderr:
        raise ValueError('mutant did not reach and fail the QEMU observer: ' + name)
    flags = struct.unpack_from('<3Q', final.read_bytes(), 8)
    if flags[index] != 0:
        raise ValueError('unexpected mutant flags: ' + name + ' ' + repr(flags))
    results.append({'mutation': name, 'flags': flags, 'sourceSha256': hashlib.sha256((base / sha_path).read_bytes()).hexdigest()})
report = {'status': 'PASS_OFFICE_SHA64_MUTATIONS', 'observerSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'mutants': results}
(out / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['status'])
