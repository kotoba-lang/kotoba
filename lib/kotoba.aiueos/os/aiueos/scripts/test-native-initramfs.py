#!/usr/bin/env python3
"""JUN-555: byte-compare the Kotoba newc initramfs generator with its Python oracle.

The oracle is scripts/make-initramfs.py, which the build no longer runs and
which stays in the tree as this test's oracle only. Each case runs
native/initramfs.kotoba through scripts/run-native-generator.sh and requires
the same archive bytes, or the same refusal (non-zero exit, no output). Cases:
the build's five entries (when --aiueos is given, as build-uefi.sh lists them),
empty and 4-byte-alignment-boundary files and names, a 262144-byte slice
boundary, invalid names, and random entry lists. A mutant must be caught.
Observation only.
"""

import argparse
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
GENERATOR = HERE.parent / "native/initramfs.kotoba"
RUNNER = HERE / "run-native-generator.sh"
ORACLE = HERE / "make-initramfs.py"


def run(command, out):
    out.unlink(missing_ok=True)
    result = subprocess.run(command, capture_output=True)
    return result.returncode == 0, out.read_bytes() if out.exists() else None


def oracle(work, entries):
    out = work / "oracle.img"
    command = [sys.executable, "-I", str(ORACLE), "--output", str(out)]
    for name, path in entries:
        command.append(f"--entry={name},{path}")
    return run(command, out)


def native(work, generator, entries):
    out = work / "native.img"
    command = ["sh", str(RUNNER), str(generator), str(out)]
    tail = []
    for index, (name, path) in enumerate(entries):
        command += ["--input", f"e{index}={path}"]
        tail += [name, f"e{index}", f"@size:e{index}"]
    return run(command + ["--"] + tail, out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aiueos", type=Path, help="os/aiueos, for the build's own entries")
    parser.add_argument("--random", type=int, default=12)
    parser.add_argument("--seed", type=int, default=555)
    args = parser.parse_args()
    if "AIUEOS_AMU_SOURCE" not in os.environ:
        raise SystemExit("error: set AIUEOS_AMU_SOURCE to the pinned Amu checkout")
    rng = random.Random(args.seed)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)

        def blob(size):
            path = work / f"blob-{size}-{rng.randrange(1 << 30)}"
            path.write_bytes(bytes(rng.randrange(256) for _ in range(size)))
            return path

        sets = []
        if args.aiueos:
            a = args.aiueos
            sets.append([("recovery/user-smoke.elf", a / "kotoba/user-smoke.elf"),
                         ("recovery/user-smoke.sig", a / "kotoba/user-smoke.sig"),
                         ("recovery/app-catalog.sig", a / "kotoba/app-catalog.sig"),
                         ("font/aiueos-16.fnt", a / "fonts/aiueos-16.fnt"),
                         ("ime/aiueos-kanji.dic", a / "ime/aiueos-kanji.dic")])
        sets += [[("a", blob(0))], [("ab", blob(1)), ("abc", blob(2)), ("abcd", blob(3))],
                 [("x" * n, blob(n)) for n in range(1, 9)],
                 [("slice", blob(262143)), ("slice2", blob(262144)), ("slice3", blob(262145))],
                 [("dir/a b.txt", blob(5)), ("TRAILER!!!", blob(4))]]
        for _ in range(args.random):
            sets.append([("".join(rng.choice("abcxyz/._-019") for _ in range(rng.randrange(1, 40))),
                          blob(rng.randrange(0, 1 << rng.choice((4, 9, 14)))))
                         for _ in range(rng.randrange(1, 7))])
        refusals = [[("", blob(3))], [("naïve", blob(3))]]
        accepted = refused = 0
        for entries in sets + refusals:
            expected = oracle(work, entries)
            if native(work, GENERATOR, entries) != expected:
                raise SystemExit(f"MISMATCH {[name for name, _ in entries]!r}: oracle accepted={expected[0]}")
            accepted, refused = (accepted + 1, refused) if expected[0] else (accepted, refused + 1)
        if refused != len(refusals):
            raise SystemExit("error: a refusal case was accepted by both")
        source = GENERATOR.read_text()
        mutant = work / "mutant.kotoba"
        mutant.write_text(source.replace("(ini-header D at \"TRAILER!!!\" 0 0 0)",
                                         "(ini-header D at \"TRAILER!!!\" 1 0 0)", 1))
        if mutant.read_text() == source:
            raise SystemExit("error: mutant did not apply")
        if native(work, mutant, sets[0]) == oracle(work, sets[0]):
            raise SystemExit("error: the comparison did not catch the mutant")
        print(f"PASS_NATIVE_INITRAMFS accepted={accepted} refused={refused} mutant=caught")


if __name__ == "__main__":
    main()
