#!/usr/bin/env python3
"""JUN-555: byte-compare the Kotoba zero-cap embedded-assembly generator with its Python oracle.

The oracle is scripts/make-zero-cap-user-embedded-assembly.py, which the build no
longer runs and which stays in the tree as this test's oracle only. The native
side is what build-uefi.sh now does: the observer verify-kotoba-user-elf.py must
report caps=none, then native/zero-cap-user-embedded-assembly.kotoba runs through
scripts/run-native-generator.sh with the resolved ELF path. Each case requires
the same bytes and stdout, or the same refusal (non-zero exit, no output).
Cases: the pinned fixture ELF with random signatures and keys, an all-zero key,
63/65-byte signatures and keys, a wrong expected digest, a changed ELF, and ELF
paths containing a quote, a backslash or non-ASCII. A mutant must be caught.
Observation only.
"""

import argparse
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
GENERATOR = HERE.parent / "native/zero-cap-user-embedded-assembly.kotoba"
RUNNER = HERE / "run-native-generator.sh"
ORACLE = HERE / "make-zero-cap-user-embedded-assembly.py"
VERIFIER = HERE / "verify-kotoba-user-elf.py"
FIXTURE = HERE.parent / "fixtures/zero-cap-user/scalar.elf"
DIGEST = "7f5a8c0a31b5bdf191410f007973413d16e497a20ae7fe86c734b9fea85808b1"


def oracle(work, elf, digest, signature, key):
    out = work / "oracle.S"
    out.unlink(missing_ok=True)
    result = subprocess.run([sys.executable, "-I", str(ORACLE), str(elf), digest, str(signature),
                             str(key), str(out)], capture_output=True)
    ok = result.returncode == 0
    # On a non-ASCII path the oracle's write_text leaves an empty file behind before it fails;
    # a refusal is compared as a refusal, and the native side must leave nothing.
    return ok, out.read_bytes() if ok and out.exists() else None, result.stdout if ok else b""


def native(work, generator, elf, digest, signature, key):
    out = work / "native.S"
    out.unlink(missing_ok=True)
    verified = subprocess.run([sys.executable, "-I", str(VERIFIER), str(elf), digest], capture_output=True)
    if verified.returncode != 0 or b"caps=none" not in verified.stdout or elf.is_symlink():
        return False, None, b""
    result = subprocess.run(["sh", str(RUNNER), str(generator), str(out), "--seed", "03-source-sha256",
                             "--input", f"elf={elf}", "--input", f"signature={signature}",
                             "--input", f"key={key}", "--", "elf", "@size:elf", digest,
                             "signature", "@size:signature", "key", "@size:key", str(elf.resolve())],
                            capture_output=True)
    ok = result.returncode == 0
    return ok, out.read_bytes() if out.exists() else None, result.stdout if ok else b""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--random", type=int, default=12)
    parser.add_argument("--seed", type=int, default=555)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp).resolve()

        def blob(size, fill=None):
            path = work / f"blob-{rng.randrange(1 << 40)}"
            path.write_bytes(bytes(fill if fill is not None else rng.randrange(256) for _ in range(size)))
            return path

        changed = work / "changed.elf"
        raw = bytearray(FIXTURE.read_bytes())
        raw[-1] ^= 1
        changed.write_bytes(raw)
        odd = []
        for name in ('q"uote', "back\\slash", "na\u00efve"):
            directory = work / name
            directory.mkdir()
            shutil.copyfile(FIXTURE, directory / "scalar.elf")
            odd.append(directory / "scalar.elf")
        cases = [(FIXTURE, DIGEST, blob(64), blob(64)), (FIXTURE, DIGEST, blob(64), blob(64, 0)),
                 (FIXTURE, DIGEST, blob(63), blob(64)), (FIXTURE, DIGEST, blob(65), blob(64)),
                 (FIXTURE, DIGEST, blob(64), blob(63)), (FIXTURE, DIGEST, blob(64), blob(65)),
                 (FIXTURE, DIGEST, blob(0), blob(0)), (FIXTURE, "0" * 64, blob(64), blob(64)),
                 (FIXTURE, DIGEST.upper(), blob(64), blob(64)), (changed, DIGEST, blob(64), blob(64)),
                 (FIXTURE, DIGEST, blob(64, 0), blob(64, 255))]
        cases += [(path, DIGEST, blob(64), blob(64)) for path in odd]
        cases += [(FIXTURE, DIGEST, blob(64), blob(64)) for _ in range(args.random)]
        accepted = refused = 0
        for case in cases:
            expected = oracle(work, *case)
            if native(work, GENERATOR, *case) != expected:
                raise SystemExit(f"MISMATCH {case!r}: oracle accepted={expected[0]}")
            accepted, refused = (accepted + 1, refused) if expected[0] else (accepted, refused + 1)
        source = GENERATOR.read_text()
        mutant = work / "mutant.kotoba"
        mutant.write_text(source.replace("(zc-cat \".byte \" (zc-byte-list key) \"\\n\")",
                                         "(zc-cat \".byte \" (zc-byte-list S) \"\\n\")", 1))
        if mutant.read_text() == source:
            raise SystemExit("error: mutant did not apply")
        if native(work, mutant, *cases[0]) == oracle(work, *cases[0]):
            raise SystemExit("error: the comparison did not catch the mutant")
        print(f"PASS_NATIVE_ZERO_CAP_USER_EMBED accepted={accepted} refused={refused} mutant=caught")


if __name__ == "__main__":
    main()
