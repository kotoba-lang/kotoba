#!/usr/bin/env python3
"""JUN-555: byte-compare the Kotoba kernel/initramfs identity source generator with its Python oracle.

ORACLE is the inline Python (`PY`, the identity source) that scripts/build-uefi.sh
ran before JUN-555, kept verbatim here as a test oracle only; the build no
longer runs it. Each case runs native/kernel-identity-source.kotoba through
scripts/run-native-generator.sh and requires the same bytes. Cases: the built
KERNEL.ELF and INITRD.IMG when given, SHA-256 padding boundaries (0, 1, 55, 56,
63, 64, 65, 119, 120 bytes), a 262144-byte slice boundary, and random contents and
sizes. A mutant of the generator must be caught. Observation only.
"""

import argparse
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
GENERATOR = HERE.parent / "native/kernel-identity-source.kotoba"
RUNNER = HERE / "run-native-generator.sh"

ORACLE = r'''import hashlib, pathlib, sys
kernel_digest = hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).digest()
initramfs_digest = hashlib.sha256(pathlib.Path(sys.argv[2]).read_bytes()).digest()
def values(digest):
    return ",".join(f"0x{byte:02x}" for byte in digest)
pathlib.Path(sys.argv[3]).write_text(
    "#include <stdint.h>\n"
    "const uint8_t aiueos_expected_kernel_sha256[32]={" + values(kernel_digest) + "};\n"
    "const uint8_t aiueos_expected_initramfs_sha256[32]={" + values(initramfs_digest) + "};\n",
    encoding="ascii")
'''


def run(command, out):
    out.unlink(missing_ok=True)
    result = subprocess.run(command, capture_output=True)
    return result.returncode, out.read_bytes() if out.exists() else None


def oracle(work, kernel, initramfs):
    out = work / "oracle.c"
    return run([sys.executable, "-I", "-c", ORACLE, str(kernel), str(initramfs), str(out)], out)


def native(work, generator, kernel, initramfs):
    out = work / "native.c"
    return run(["sh", str(RUNNER), str(generator), str(out),
                "--seed", "03-source-sha256",
                "--input", f"kernel={kernel}", "--input", f"initramfs={initramfs}",
                "--", "kernel", "@size:kernel", "initramfs", "@size:initramfs"], out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path)
    parser.add_argument("--initramfs", type=Path)
    parser.add_argument("--random", type=int, default=12)
    parser.add_argument("--seed", type=int, default=555)
    args = parser.parse_args()
    if "AIUEOS_AMU_SOURCE" not in os.environ:
        raise SystemExit("error: set AIUEOS_AMU_SOURCE to the pinned Amu checkout")
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
        kernel, initramfs = files[0]
        if native(work, mutant, kernel, initramfs) == oracle(work, kernel, initramfs):
            raise SystemExit("error: the comparison did not catch the mutant")
        print(f"PASS_NATIVE_KERNEL_IDENTITY_SOURCE cases={len(files)} mutant=caught")


if __name__ == "__main__":
    main()
