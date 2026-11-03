#!/usr/bin/env python3
"""JUN-555: byte-compare the Kotoba SSH authorized-key header generator with its Python oracle.

The oracle is scripts/write-ssh-authorized-key-header.py, which the build no
longer runs and which stays in the tree as this test's oracle only. Each case
runs native/ssh-authorized-key-header.kotoba through
scripts/run-native-generator.sh and requires the same bytes, or the same
refusal (non-zero exit, no output). Cases: the gate's fixed key from
kernel/pci.c, case and Unicode-whitespace forms, lengths 127/129, non-hex and
random keys. A mutant of the generator must be caught. Observation only.
"""

import argparse
from pathlib import Path
import random
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
GENERATOR = HERE.parent / "native/ssh-authorized-key-header.kotoba"
RUNNER = HERE / "run-native-generator.sh"
ORACLE = HERE / "write-ssh-authorized-key-header.py"
GATE_KEY = ("46870e7ce79bcbc6014714618f3543dc1e6d67cbc5da378d91c8d71711af1abf"
            "04aed0995946fb244e15109ee276c579fa0b14405bf9507522eee26568d2c0f3")
SPACES = ["\t", "\n", "\x0b", "\x0c", "\r", "\x1c", "\x1f", " ", "\x85", "\xa0",
          " ", " ", " ", " ", " ", " ", " ", "　"]


def run(command, out):
    out.unlink(missing_ok=True)
    result = subprocess.run(command, capture_output=True)
    return result.returncode == 0, out.read_bytes() if out.exists() else None


def oracle(work, key):
    out = work / "oracle.h"
    return run([sys.executable, "-I", str(ORACLE), key, str(out)], out)


def native(work, generator, key):
    out = work / "native.h"
    return run(["sh", str(RUNNER), str(generator), str(out), "--", key], out)


def cases(seed, count):
    rng = random.Random(seed)
    fixed = [GATE_KEY, GATE_KEY.upper(), GATE_KEY[:64].upper() + GATE_KEY[64:],
             " " + GATE_KEY + " ", GATE_KEY[:127], GATE_KEY + "0", "", "   ",
             "g" + GATE_KEY[1:], GATE_KEY[:64] + " " + GATE_KEY[64:],
             "​" + GATE_KEY, GATE_KEY + "é", "0x" + GATE_KEY[2:]]
    fixed += [space + GATE_KEY + space for space in SPACES]
    out = list(fixed)
    for _ in range(count):
        key = "".join(rng.choice("0123456789abcdefABCDEF") for _ in range(rng.choice((128, 128, 128, 127, 129))))
        if rng.random() < 0.3:
            key = rng.choice(SPACES) * rng.randrange(1, 3) + key + rng.choice(SPACES + [""])
        if rng.random() < 0.1:
            i = rng.randrange(len(key))
            key = key[:i] + rng.choice("gz-+ é") + key[i + 1:]
        out.append(key)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--random", type=int, default=40)
    parser.add_argument("--seed", type=int, default=555)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        accepted = refused = 0
        for key in cases(args.seed, args.random):
            expected = oracle(work, key)
            if native(work, GENERATOR, key) != expected:
                raise SystemExit(f"MISMATCH {key!r}: oracle accepted={expected[0]}")
            accepted, refused = (accepted + 1, refused) if expected[0] else (accepted, refused + 1)
        source = GENERATOR.read_text()
        mutant = work / "mutant.kotoba"
        mutant.write_text(source.replace("(ssh-init key (+ at 64))", "(ssh-init key (+ at 62))", 1))
        if mutant.read_text() == source:
            raise SystemExit("error: mutant did not apply")
        if native(work, mutant, GATE_KEY) == oracle(work, GATE_KEY):
            raise SystemExit("error: the comparison did not catch the mutant")
        print(f"PASS_NATIVE_SSH_AUTHORIZED_KEY_HEADER accepted={accepted} refused={refused} mutant=caught")


if __name__ == "__main__":
    main()
