#!/usr/bin/env python3
"""JUN-555: byte-compare the Kotoba build-identity header generator with its Python oracle.

ORACLE is the inline Python (PYBUILD) that scripts/build-uefi.sh ran before
JUN-555, kept verbatim here as a test oracle only; the build no longer runs it.
Each case runs native/build-identity-header.kotoba through
scripts/run-native-generator.sh and requires the same bytes, or the same
refusal (non-zero exit, no output). A mutant of the generator must be caught.
Observation only: this script writes nothing the image uses.
"""

import argparse
from pathlib import Path
import random
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
GENERATOR = HERE.parent / "native/build-identity-header.kotoba"
RUNNER = HERE / "run-native-generator.sh"

ORACLE = r'''from pathlib import Path
import re
import sys

out, version, commit, dirty = sys.argv[1:]
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?", version):
    raise SystemExit("error: os/aiueos/VERSION must be a bounded SemVer string")
if not re.fullmatch(r"[0-9a-f]{40}", commit):
    raise SystemExit("error: AIUEOS source commit must be a full lowercase git hash")
suffix = "-DIRTY" if dirty == "true" else ""
Path(out).write_text(
    "#ifndef AIUEOS_BUILD_IDENTITY_H\n#define AIUEOS_BUILD_IDENTITY_H\n"
    f'#define AIUEOS_BUILD_VERSION "{version}"\n'
    f'#define AIUEOS_BUILD_SOURCE_HASH "{commit[:12]}"\n'
    f'#define AIUEOS_BUILD_DIRTY_SUFFIX "{suffix}"\n'
    "#endif\n", encoding="ascii")
'''


def oracle(work, args):
    out = work / "oracle.h"
    out.unlink(missing_ok=True)
    result = subprocess.run([sys.executable, "-I", "-c", ORACLE, str(out), *args],
                            capture_output=True)
    return result.returncode, out.read_bytes() if out.exists() else None


def native(work, generator, args):
    out = work / "native.h"
    out.unlink(missing_ok=True)
    result = subprocess.run(["sh", str(RUNNER), str(generator), str(out), "--", *args],
                            capture_output=True)
    return result.returncode, out.read_bytes() if out.exists() else None


def cases(seed, count):
    head = subprocess.run(["git", "-C", str(HERE), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()
    version = (HERE.parent / "VERSION").read_text().strip()
    commit = "0123456789abcdef" * 2 + "01234567"
    fixed = [
        (version, head, "false"), (version, head, "true"),
        ("0.0.0", commit, "true"), ("10.20.30-rc.1-x.Y.z", commit, "false"),
        ("1.2.3-.", commit, "TRUE"), ("1.2.3--", commit, ""),
        ("1.2", commit, "false"), ("1.2.3-", commit, "false"), ("1.2.3.4", commit, "false"),
        ("v1.2.3", commit, "false"), ("1..3", commit, "false"), ("", commit, "false"),
        ("1.2.3+b", commit, "false"), ("1.2.3 ", commit, "false"), ("1.2.3\n", commit, "false"),
        ("１.2.3", commit, "false"), ("1.2.3-é", commit, "false"),
        ("1.2.3", commit[:39], "false"), ("1.2.3", commit + "0", "false"),
        ("1.2.3", commit.upper(), "false"), ("1.2.3", "g" + commit[1:], "false"),
        ("1.2.3", "", "false"), ("1.2.3", commit, "true "), ("1.2.3", commit, "é"),
    ]
    rng = random.Random(seed)
    alphabet = "0123456789abcdefABCXYZ.-+_ "
    out = list(fixed)
    for _ in range(count):
        if rng.random() < 0.5:
            parts = [str(rng.randrange(0, 100000)) for _ in range(3)]
            v = ".".join(parts)
            if rng.random() < 0.6:
                v += "-" + "".join(rng.choice(alphabet[:-3] + "-.") for _ in range(rng.randrange(0, 12)))
        else:
            v = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 16)))
        c = "".join(rng.choice("0123456789abcdef" + ("G" if rng.random() < 0.2 else ""))
                    for _ in range(rng.choice((40, 40, 40, 39, 41))))
        d = rng.choice(("true", "false", "", "True", "1"))
        out.append((v, c, d))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--random", type=int, default=40)
    parser.add_argument("--seed", type=int, default=555)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        accepted = refused = 0
        for case in cases(args.seed, args.random):
            o_status, o_bytes = oracle(work, case)
            n_status, n_bytes = native(work, GENERATOR, case)
            if (o_status == 0) != (n_status == 0) or o_bytes != n_bytes:
                raise SystemExit(f"MISMATCH {case!r}: oracle={o_status} native={n_status}")
            if o_status == 0:
                accepted += 1
            else:
                refused += 1
        source = GENERATOR.read_text()
        mutant = work / "mutant.kotoba"
        mutant.write_text(source.replace('(string-substring commit 0 12)',
                                         '(string-substring commit 0 11)', 1))
        if mutant.read_text() == source:
            raise SystemExit("error: mutant did not apply")
        case = cases(args.seed, 0)[0]
        if native(work, mutant, case) == oracle(work, case):
            raise SystemExit("error: the comparison did not catch the mutant")
        print(f"PASS_NATIVE_BUILD_IDENTITY_HEADER accepted={accepted} refused={refused} mutant=caught")


if __name__ == "__main__":
    main()
