#!/usr/bin/env python3
"""The kernel object verifier's declared-extern contract (amu JUN-556 D1, ADR 0380).

fixtures/kernel-object-externs.o is the object a native Amu compiler wrote for
  (defn- extern-sink_a [a b] ..) (defn- extern-sink_b [a] ..)
  (defn f [x] (+ (extern-sink_a x 7) (+ (extern-sink_b x) (extern-sink_a 1 2))))
(amu scripts/seed/check-aiueos-object-externs.py, Mac F2 compiler). The test
checks that it passes with its declared list and that every tamper below is refused.
"""

import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
VERIFY = HERE.parent / "scripts" / "verify-kotoba-kernel-object.py"
SOURCE = (HERE / "fixtures" / "kernel-object-externs.o").read_bytes()


def run(blob, exports="f", externs="sink_a,sink_b"):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "t.o"
        path.write_bytes(blob)
        args = [sys.executable, "-I", str(VERIFY), str(path), "", exports]
        if externs is not None:
            args.append(externs)
        result = subprocess.run(args, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr).strip()


def layout(blob):
    shoff, = struct.unpack_from("<Q", blob, 40)
    shnum, shstr = struct.unpack_from("<HH", blob, 60)
    secs = [struct.unpack_from("<IIQQQQIIQQ", blob, shoff + 64 * i) for i in range(shnum)]
    table = secs[shstr][4]
    name = lambda o: blob[table + o:blob.index(b"\0", table + o)].decode()
    by = {name(s[0]): s for s in secs}
    return by[".text"][4], by[".rela.text"][4]


def main():
    text, rela = layout(SOURCE)
    rels = [struct.unpack_from("<QQq", SOURCE, rela + 24 * i) for i in range(4)]
    call = rels[1][0]
    code, out = run(SOURCE)
    assert code == 0 and "imports=2 relocations=4" in out, out
    for label, args in (("no list", dict(externs=None)), ("short list", dict(externs="sink_a")),
                        ("extern named like an export", dict(externs="f,sink_a,sink_b"))):
        code, out = run(SOURCE, **args)
        assert code != 0, label
    def tamper(label, edit):
        blob = bytearray(SOURCE)
        edit(blob)
        code, out = run(bytes(blob))
        assert code != 0, f"{label} was accepted"
    tamper("tail byte", lambda b: b.__setitem__(text + call + 4, b[text + call + 4] ^ 1))
    tamper("displacement", lambda b: b.__setitem__(text + call, 1))
    tamper("call opcode", lambda b: b.__setitem__(text + call - 1, 0x90))
    tamper("addend", lambda b: struct.pack_into("<q", b, rela + 24 + 16, 0))
    tamper("type PC32", lambda b: struct.pack_into("<Q", b, rela + 24 + 8, (rels[1][1] & ~0xFFFFFFFF) | 2))
    tamper("names the context", lambda b: struct.pack_into("<Q", b, rela + 24 + 8, (1 << 32) | 4))
    print("PASS_KERNEL_OBJECT_EXTERNS 1 accepted, 9 refused")


if __name__ == "__main__":
    main()
