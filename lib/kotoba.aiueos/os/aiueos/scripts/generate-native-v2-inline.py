#!/usr/bin/env python3
"""Render exact Amu user-v2 segment bytes as a locked diagnostic Kotoba module.

This is a host-side source generator for the single-payload desktop profile.
It is not a release app loader or a replacement for signed admission.
"""

import argparse
import hashlib
from pathlib import Path
import struct


ELF_SHA256 = "d1cd47b63ec90df52f6763f63c9410d2a032266412be3dd49238db8ecdf61248"


def signed(value):
    return value if value < 1 << 63 else value - (1 << 64)


def cases(name, data):
    words = struct.unpack("<" + "Q" * (len(data) // 8), data[:len(data) // 8 * 8])
    rows = "\n".join(f"    {index} {signed(value)}" for index, value in enumerate(words))
    return f"(defn- {name} [index :i64] :i64\n  (case index\n{rows} 0))\n"


def render(raw):
    if len(raw) != 8280 or hashlib.sha256(raw).hexdigest() != ELF_SHA256:
        raise ValueError("pinned Amu user-v2 ELF digest/size mismatch")
    if struct.unpack_from("<Q", raw, 24)[0] != 0x220000:
        raise ValueError("user-v2 entry mismatch")
    rx = struct.unpack_from("<IIQQQQQQ", raw, 64)
    rw = struct.unpack_from("<IIQQQQQQ", raw, 120)
    if rx != (1, 5, 4096, 0x220000, 0x220000, 330, 330, 4096):
        raise ValueError("user-v2 RX segment mismatch")
    if rw != (1, 6, 8192, 0x221000, 0x221000, 88, 320, 4096):
        raise ValueError("user-v2 RW segment mismatch")
    code = raw[4096:4426]
    context = raw[8192:8280]
    return """(ns aiueos.native.user-v2-inline (:export [stage]))
;; Generated from pinned Amu user-v2 ELF SHA-256 """ + ELF_SHA256 + """.
;; Diagnostic single-payload profile: the EFI payload is the native font.
;; This source-bound byte copy is not signed or generic application admission.
""" + cases("code-word", code) + cases("context-word", context) + f"""
(defn- copy-code [page :i64 index :i64] :bool
  (if (= index 41)
    (do (kernel-store-u8-4k page 4096 328 {code[328]})
        (kernel-store-u8-4k page 4096 329 {code[329]})
        (and (= (kernel-load-u8-4k page 4096 328) {code[328]})
             (= (kernel-load-u8-4k page 4096 329) {code[329]})))
    (let [value (code-word index)]
      (do (kernel-store-u64-4k page 4096 (* index 8) value)
          (and (= (kernel-load-u64-4k page 4096 (* index 8)) value)
               (copy-code page (+ index 1)))))))
(defn- copy-context [page :i64 index :i64] :bool
  (if (= index 11) true
    (let [value (context-word index)]
      (do (kernel-store-u64-4k page 4096 (* index 8) value)
          (and (= (kernel-load-u64-4k page 4096 (* index 8)) value)
               (copy-context page (+ index 1)))))))
(defn stage [code :i64 request :i64] :bool
  (and (copy-code code 0) (copy-context request 0)))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.elf.is_symlink() or not args.elf.is_file():
        raise ValueError("ELF must be a regular file")
    source = render(args.elf.read_bytes())
    if args.check:
        if args.output.read_text() != source:
            raise ValueError("inline Kotoba source differs from pinned ELF")
        print("INLINE_USER_V2_SOURCE_MATCH", hashlib.sha256(source.encode()).hexdigest())
    else:
        with args.output.open("x") as target:
            target.write(source)
        print("INLINE_USER_V2_SOURCE_WRITTEN", hashlib.sha256(source.encode()).hexdigest())


if __name__ == "__main__":
    main()
