#!/usr/bin/env python3
"""JUN-555: byte-compare the Kotoba model-identity header generator with its Python oracle.

ORACLE is the inline Python (PYMODEL) that scripts/build-uefi.sh ran before
JUN-555, kept verbatim here as a test oracle only; the build no longer runs it.
Each case runs native/model-identity-header.kotoba through
scripts/run-native-generator.sh. Where the generator writes a header it must be
the oracle's bytes. Where it refuses, the oracle must refuse too, or the digest
must be outside the generator's one deliberate tightening: exactly 64
hexadecimal digits (the oracle reads only the first 64 characters, through
int(pair, 16), so it also took a longer digest or pairs like " a" and "+a").
A mutant of the generator must be caught. Observation only.
"""

import argparse
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
GENERATOR = HERE.parent / "native/model-identity-header.kotoba"
RUNNER = HERE / "run-native-generator.sh"
DIGEST = re.compile(r"[0-9a-fA-F]{64}\Z")

ORACLE = r'''from pathlib import Path
import sys

(out, total, part0, part1, part2, digest, minimum, maximum, parts, name,
 prefix) = sys.argv[1:]
values = ",".join(f"0x{int(digest[i:i+2], 16):02x}" for i in range(0, 64, 2))
Path(out).write_text(
    "#ifndef AIUEOS_MODEL_IDENTITY_H\n#define AIUEOS_MODEL_IDENTITY_H\n"
    "#include <stdint.h>\n"
    f"#define AIUEOS_MODEL_TOTAL_BYTES {total}ULL\n"
    f"#define AIUEOS_MODEL_PART0_BYTES {part0}ULL\n"
    f"#define AIUEOS_MODEL_PART1_BYTES {part1}ULL\n"
    f"#define AIUEOS_MODEL_PART2_BYTES {part2}ULL\n"
    f"#define AIUEOS_MODEL_PART_COUNT {parts}U\n"
    f'#define AIUEOS_MODEL_PARTS_TEXT "{parts}"\n'
    f'#define AIUEOS_MODEL_NAME "{name}"\n'
    f'#define AIUEOS_MODEL_PART0_PATH u"\\\\EFI\\\\AIUEOS\\\\{prefix}0.BIN"\n'
    f'#define AIUEOS_MODEL_PART1_PATH u"\\\\EFI\\\\AIUEOS\\\\{prefix}1.BIN"\n'
    f'#define AIUEOS_MODEL_PART2_PATH u"\\\\EFI\\\\AIUEOS\\\\{prefix}2.BIN"\n'
    f"#define AIUEOS_MODEL_MIN_ADDRESS {minimum}ULL\n"
    f"#define AIUEOS_MODEL_MAX_ADDRESS {maximum}ULL\n"
    "#ifndef AIUEOS_MODEL_IDENTITY_MACROS_ONLY\n"
    "static const uint8_t aiueos_expected_model_sha256[32]={" + values + "};\n"
    "#endif\n"
    "#endif\n", encoding="ascii")
'''

QWEN38 = ("10934860704", "4000000000", "4000000000", "2934860704",
          "c0b7c3038681ed2e3040456c1dd45f9858b6c2290bed172c70388a94874f3eee",
          "4294967296", "68719476735", "3", "qwen38-27b", "Q38P")
BONSAI2 = ("5946648928", "4000000000", "1946648928", "0",
           "53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3",
           "4294967296", "68719476735", "2", "bonsai2-27b", "B2P")


def run(command, out):
    out.unlink(missing_ok=True)
    result = subprocess.run(command, capture_output=True)
    data = out.read_bytes() if out.exists() else None
    return result.returncode, data


def oracle(work, args):
    out = work / "oracle.h"
    return run([sys.executable, "-I", "-c", ORACLE, str(out), *args], out)


def native(work, generator, args):
    out = work / "native.h"
    return run(["sh", str(RUNNER), str(generator), str(out), "--", *args], out)


def with_field(base, index, value):
    values = list(base)
    values[index] = value
    return tuple(values)


def cases(seed, count):
    d = QWEN38[4]
    fixed = [QWEN38, BONSAI2,
             with_field(QWEN38, 4, d.upper()), with_field(QWEN38, 4, "0" * 64),
             with_field(QWEN38, 4, "f" * 64), with_field(QWEN38, 4, d[:63]),
             with_field(QWEN38, 4, d + "0"), with_field(QWEN38, 4, " " + d[1:]),
             with_field(QWEN38, 4, "+" + d[1:]), with_field(QWEN38, 4, "g" + d[1:]),
             with_field(QWEN38, 4, ""), with_field(QWEN38, 0, ""),
             with_field(QWEN38, 0, "1"), with_field(QWEN38, 7, "0"),
             with_field(QWEN38, 8, ""), with_field(QWEN38, 8, "q\\\"x"),
             with_field(QWEN38, 9, ""), with_field(QWEN38, 9, "é"),
             with_field(QWEN38, 8, "名前"), with_field(QWEN38, 5, "18446744073709551615")]
    rng = random.Random(seed)
    text = "0123456789abcdefABCDEF-_. \"\\xyz"
    out = list(fixed)
    for _ in range(count):
        values = []
        for index in range(10):
            if index == 4:
                n = rng.choice((64, 64, 64, 63, 65, 0))
                values.append("".join(rng.choice("0123456789abcdefABCDEF" + ("g " if rng.random() < 0.2 else ""))
                                      for _ in range(n)))
            elif index in (8, 9):
                values.append("".join(rng.choice(text) for _ in range(rng.randrange(0, 12))))
            else:
                values.append(str(rng.randrange(0, 1 << rng.choice((1, 8, 32, 40, 64)))))
        out.append(tuple(values))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--random", type=int, default=40)
    parser.add_argument("--seed", type=int, default=555)
    args = parser.parse_args()
    if "AIUEOS_AMU_SOURCE" not in os.environ:
        raise SystemExit("error: set AIUEOS_AMU_SOURCE to the pinned Amu checkout")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        counts = {"accepted": 0, "refused": 0, "tightened": 0}
        for case in cases(args.seed, args.random):
            o_status, o_bytes = oracle(work, case)
            n_status, n_bytes = native(work, GENERATOR, case)
            if n_status == 0:
                if o_status != 0 or o_bytes != n_bytes:
                    raise SystemExit(f"MISMATCH {case!r}: oracle={o_status}")
                counts["accepted"] += 1
            elif n_bytes is not None:
                raise SystemExit(f"refusal left output {case!r}")
            elif o_status != 0:
                counts["refused"] += 1
            elif not DIGEST.match(case[4]):
                counts["tightened"] += 1
            else:
                raise SystemExit(f"MISMATCH {case!r}: native refused, oracle accepted")
        source = GENERATOR.read_text()
        mutant = work / "mutant.kotoba"
        mutant.write_text(source.replace('"#define AIUEOS_MODEL_PART2_BYTES "',
                                         '"#define AIUEOS_MODEL_PART2_BYTES  "', 1))
        if mutant.read_text() == source:
            raise SystemExit("error: mutant did not apply")
        if native(work, mutant, QWEN38) == oracle(work, QWEN38):
            raise SystemExit("error: the comparison did not catch the mutant")
        print("PASS_NATIVE_MODEL_IDENTITY_HEADER "
              + " ".join(f"{k}={v}" for k, v in counts.items()) + " mutant=caught")


if __name__ == "__main__":
    main()
