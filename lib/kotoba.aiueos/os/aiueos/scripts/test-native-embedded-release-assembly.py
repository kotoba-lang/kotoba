#!/usr/bin/env python3
"""JUN-555: byte-compare the Kotoba embedded-release assembly generator with its Python oracle.

ORACLE is the inline Python (PYEMBED, EMBEDDED_RELEASE only) that
scripts/build-uefi.sh ran before JUN-555, kept verbatim here as a test oracle
only; the build no longer runs it. The .incbin paths are the inputs' resolved
absolute paths, passed as build-uefi.sh passes them. Each case runs
native/embedded-release-assembly.kotoba through
scripts/run-native-generator.sh and requires the same bytes. Cases: the built
KERNEL.ELF and INITRD.IMG when given, SHA-256 padding boundaries (0, 1, 55, 56,
63, 64, 65, 119, 120 bytes), a 262144-byte slice boundary, and random contents and
sizes. A mutant of the generator must be caught. Observation only.
"""

import argparse
from pathlib import Path
import random
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
GENERATOR = HERE.parent / "native/embedded-release-assembly.kotoba"
RUNNER = HERE / "run-native-generator.sh"

ORACLE = r'''from pathlib import Path
import hashlib
import sys

kernel_path = Path(sys.argv[1]).resolve()
initramfs_path = Path(sys.argv[2]).resolve()
kernel = kernel_path.as_posix()
initramfs = initramfs_path.as_posix()
kernel_sha256 = hashlib.sha256(kernel_path.read_bytes()).hexdigest()
initramfs_sha256 = hashlib.sha256(initramfs_path.read_bytes()).hexdigest()
Path(sys.argv[3]).write_text(
    f'# aiueos-embedded-kernel-sha256={kernel_sha256}\n'
    f'# aiueos-embedded-initramfs-sha256={initramfs_sha256}\n'
    '.section .rdata,"dr"\n'
    '.balign 16\n'
    '.globl aiueos_embedded_kernel_start\n'
    'aiueos_embedded_kernel_start:\n'
    f'.incbin "{kernel}"\n'
    '.globl aiueos_embedded_kernel_end\n'
    'aiueos_embedded_kernel_end:\n'
    '.balign 16\n'
    '.globl aiueos_embedded_initramfs_start\n'
    'aiueos_embedded_initramfs_start:\n'
    f'.incbin "{initramfs}"\n'
    '.globl aiueos_embedded_initramfs_end\n'
    'aiueos_embedded_initramfs_end:\n',
    encoding='ascii')
'''


def run(command, out):
    out.unlink(missing_ok=True)
    result = subprocess.run(command, capture_output=True)
    return result.returncode, out.read_bytes() if out.exists() else None


def oracle(work, kernel, initramfs):
    out = work / "oracle.S"
    return run([sys.executable, "-I", "-c", ORACLE, str(kernel), str(initramfs), str(out)], out)


def native(work, generator, kernel, initramfs):
    out = work / "native.S"
    return run(["sh", str(RUNNER), str(generator), str(out),
                "--seed", "03-source-sha256",
                "--input", f"kernel={kernel}", "--input", f"initramfs={initramfs}",
                "--", "kernel", "@size:kernel", str(Path(kernel).resolve()),
                "initramfs", "@size:initramfs", str(Path(initramfs).resolve())], out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path)
    parser.add_argument("--initramfs", type=Path)
    parser.add_argument("--random", type=int, default=12)
    parser.add_argument("--seed", type=int, default=555)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        files = []
        if args.kernel and args.initramfs:
            files.append((args.kernel, args.initramfs))
        sizes = [0, 1, 55, 56, 63, 64, 65, 119, 120, 262143, 262144, 262145]
        sizes += [rng.randrange(0, 1 << rng.choice((8, 12, 16, 20))) for _ in range(args.random)]
        for index, size in enumerate(sizes):
            path = work / f"input-{index}"
            path.write_bytes(bytes(rng.randrange(256) for _ in range(size)))
            files.append((path, files[-1][0] if files else path))
        for kernel, initramfs in files:
            expected = oracle(work, kernel, initramfs)
            if expected[0] != 0 or native(work, GENERATOR, kernel, initramfs) != expected:
                raise SystemExit(f"MISMATCH kernel={kernel} initramfs={initramfs}")
        source = GENERATOR.read_text()
        mutant = work / "mutant.kotoba"
        mutant.write_text(source.replace("(vector-at B (+ i 5))", "(vector-at B (+ i 4))", 1))
        if mutant.read_text() == source:
            raise SystemExit("error: mutant did not apply")
        # The first pair with a non-empty kernel: an empty input never reaches
        # the mutated byte, so the control must use one that does.
        kernel, initramfs = next(p for p in files if Path(p[0]).stat().st_size > 64)
        if native(work, mutant, kernel, initramfs) == oracle(work, kernel, initramfs):
            raise SystemExit("error: the comparison did not catch the mutant")
        print(f"PASS_NATIVE_EMBEDDED_RELEASE_ASSEMBLY cases={len(files)} mutant=caught")


if __name__ == "__main__":
    main()
