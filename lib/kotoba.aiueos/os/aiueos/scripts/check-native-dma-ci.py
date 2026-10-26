#!/usr/bin/env python3
"""Observe the native guest and a valid-image negative control independently."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(os.environ['RUNNER_TEMP'])
assert platform.system() == 'Linux' and platform.machine() == 'x86_64'
qemu = shutil.which('qemu-system-x86_64')
assert qemu, 'QEMU observation tool unavailable'
firmware = Path('/usr/share/OVMF/OVMF_CODE_4M.fd')
assert firmware.is_file(), 'declared OVMF code image unavailable'
observer = ROOT / '.native-inputs/amu/scripts/seed/check-aiueos-entry-qemu.py'
calls = []
for kind in ['snapshot', 'negative']:
    guest, output = OUT / f'dma-{kind}', OUT / f'qemu-{kind}'
    args = [sys.executable, str(observer), '--kernel', str(guest / 'KERNEL.ELF'),
            '--efi', str(guest / 'BOOTX64.EFI'), '--qemu', qemu, '--firmware', str(firmware),
            '--output', str(output), '--dma-snapshot']
    result = subprocess.run(args, capture_output=True, timeout=180)
    output.mkdir(exist_ok=True)
    (output / 'observer.stdout').write_bytes(result.stdout)
    (output / 'observer.stderr').write_bytes(result.stderr)
    receipt = output / 'entry-qemu.json'
    if kind == 'snapshot':
        assert result.returncode == 0 and receipt.is_file(), result.stderr.decode()
        proof = json.loads(receipt.read_text())
        assert proof['dmaSnapshot']['checks'] == [1]*10
    else:
        # A timeout or tool error is not the expected negative verdict.
        assert result.returncode != 0 and not receipt.exists()
        assert b'assert checks == (1,)*10' in result.stderr, result.stderr.decode()
    calls.append(dict(kind=kind, exit=result.returncode))
proof = dict(status='PASS_NATIVE_X86_DMA_COMPONENT', calls=calls,
             observerSHA256=hashlib.sha256(observer.read_bytes()).hexdigest(),
             nativeCompiler=True, guestEmulation='QEMU TCG', fullKernelRuntime=False,
             liveRuntime=False, nativeController='separate pinned Amu exact-head CI',
             media=False, desktopInput=False, physicalHardware=False)
(OUT / 'native-dma-ci.json').write_text(json.dumps(proof, indent=2)+'\n')
print(proof['status'])
