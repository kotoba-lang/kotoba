#!/usr/bin/env python3
"""Stage source bytes and observe the native envelope v1 gates (JUN-23).

No Python crypto, envelope semantics, JVM or JS runtime. The existing native
AES-GCM module owns all cryptography. This checks a bounded compatibility
slice, not key custody, side-channel safety, storage or product readiness.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "lib/kotoba.hata/scripts"))
from native_gate import NativeGate  # noqa: E402

SOURCES = {
    "aes/core.kotoba": "lib/gov.nist.aes/kotoba/aes/core.kotoba",
    "aes/gcm.kotoba": "lib/gov.nist.aes/kotoba/aes/gcm.kotoba",
    "envelope/chunk.kotoba": "lib/kotoba.envelope/kotoba/envelope/chunk.kotoba",
    "envelope/chunk_gate.kotoba": "lib/kotoba.envelope/kotoba/envelope/chunk_gate.kotoba",
}
GROUPS = {"a": 127, "b": 31, "c": 255, "d": 255}
MUTANTS = {
    "nonce-endian": ("envelope/chunk.kotoba", "(u32 (quot index 4294967296)) (u32 (rem index 4294967296))",
                     "(u32 (rem index 4294967296)) (u32 (quot index 4294967296))", "a", 126),
    "object-unbound": ("envelope/chunk.kotoba", '(string-concat object-id\n', '(string-concat "drive:interop"\n', "c", 253),
    "count-unbound": ("envelope/chunk.kotoba", "(string-from-i64 (vector-at ctx 3))", '"1"', "c", 239),
    "tag-bypass": ("aes/gcm.kotoba", "(if (= differ 0) (gctr sched (inc32 j) ct) (vector-i64 -1))",
                   "(gctr sched (inc32 j) ct)", "c", 128),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--compiler-sha256", required=True)
    parser.add_argument("--runner", type=Path)
    parser.add_argument("--packager", type=Path)
    parser.add_argument("--packager-sha256", dest="packager_sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    gate = NativeGate(args)
    files = {name: (ROOT / path).read_bytes() for name, path in SOURCES.items()}
    results = {}

    def build(label, group, sources):
        staged = dict(sources)
        staged["main.kotoba"] = (
            "(ns chunk-entry (:require [envelope.chunk-gate :as g]) (:export [main]))\n"
            f"(defn main [] :i64 (g/group-{group}))\n").encode()
        return gate.build(label, "main.kotoba", staged)

    for group, expected in GROUPS.items():
        image = build("chunk-" + group, group, files)
        gate.run("chunk-" + group + "-run", image, expected)
        results[group] = expected
    controls = {}
    for name, (source, before, after, group, expected) in MUTANTS.items():
        assert files[source].count(before.encode()) == 1, (name, "mutant target drift")
        changed = dict(files)
        changed[source] = files[source].replace(before.encode(), after.encode())
        image = build("chunk-" + name, group, changed)
        # A compile error or arbitrary runtime failure is not a detected mutant.
        # Require the exact executed bitmask with the affected checks absent.
        assert expected != GROUPS[group]
        gate.run("chunk-" + name + "-run", image, expected)
        controls[name] = expected
    gate.finish("PASS_ENVELOPE_CHUNK_NATIVE", groups=results, mutants=controls,
                limits=["no key custody or CSPRNG qualification", "not constant time",
                        "no storage, browser or independent-node qualification"])


if __name__ == "__main__":
    main()
