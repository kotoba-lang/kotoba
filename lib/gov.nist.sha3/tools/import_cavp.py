#!/usr/bin/env python3
"""Turn NIST CAVP SHA-3 / SHAKE .rsp files into portable test data (.cljk).

Dev tool, not part of the library or of any gate. Standard library only.

    python3 -I tools/import_cavp.py <dir with the extracted .rsp files> <out dir>

The .rsp files come from NIST's Cryptographic Algorithm Validation Program:
  sha-3bytetestvectors.zip   (SHA3_224/256/384/512 ShortMsg, LongMsg, Monte)
  shakebytetestvectors.zip   (SHAKE128/256 ShortMsg, LongMsg, VariableOut, Monte)
See test/cavp/PROVENANCE.md for the URLs and the SHA-256 of both archives.

What is kept, and why (the full files are 4-5 MB each):
  ShortMsg    all entries. They cover every message length from 0 up past one full
              rate block of the function, so every padding boundary is hit.
  LongMsg     the first 5 entries.
  VariableOut every 4th entry whose output length is a whole number of bytes. These
              squeeze across the rate boundary, which is what ML-KEM and ML-DSA do.
  Monte       SHA-3 only: the Seed and the first 3 checkpoints (3000 chained hashes).

Len is in bits; every kept entry is byte-oriented, and the message is the first
Len/8 bytes of Msg (the file writes Msg = 00 for Len = 0).
"""
import os
import re
import sys


def parse_blocks(path):
    """Yield dicts of 'Key = value' lines, one dict per blank-line separated block."""
    cur = {}
    with open(path, encoding="ascii") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                if cur:
                    yield cur
                    cur = {}
                continue
            if line.startswith("["):
                m = re.match(r"\[(.+?)\s*=\s*(.+)\]", line)
                if m:
                    if cur:
                        yield cur
                        cur = {}
                    yield {"_param": m.group(1), "value": m.group(2)}
                continue
            k, _, v = line.partition("=")
            cur[k.strip()] = v.strip()
    if cur:
        yield cur


def msg_hex(block):
    n = int(block["Len"]) // 8
    return block["Msg"][: 2 * n]


def write_ns(out_dir, ns_name, doc, body):
    path = os.path.join(out_dir, ns_name.replace("sha3.cavp.", "").replace("-", "_") + ".cljk")
    with open(path, "w", encoding="ascii") as f:
        f.write(f'(ns {ns_name}\n  "{doc}")\n\n')
        f.write(body)
    return path


def vectors_literal(rows):
    out = ["(def vectors\n  ["]
    for r in rows:
        out.append("   [" + " ".join(r) + "]")
    out.append("])\n")
    return "\n".join(out)


def main(src, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    sha3 = ["224", "256", "384", "512"]
    shake = ["128", "256"]
    made = []
    for n in sha3:
        base = f"SHA3_{n}"
        short = [b for b in parse_blocks(os.path.join(src, f"{base}ShortMsg.rsp")) if "Len" in b]
        rows = [[b["Len"], f'"{msg_hex(b)}"', f'"{b["MD"]}"'] for b in short]
        made.append(write_ns(out_dir, f"sha3.cavp.sha3-{n}-short",
                             f"CAVP {base}ShortMsg.rsp: [len-bits msg-hex md-hex], all {len(rows)} entries.",
                             vectors_literal(rows)))
        long_ = [b for b in parse_blocks(os.path.join(src, f"{base}LongMsg.rsp")) if "Len" in b][:5]
        rows = [[b["Len"], f'"{msg_hex(b)}"', f'"{b["MD"]}"'] for b in long_]
        made.append(write_ns(out_dir, f"sha3.cavp.sha3-{n}-long",
                             f"CAVP {base}LongMsg.rsp: first {len(rows)} entries.",
                             vectors_literal(rows)))
        seed, mds = None, []
        for b in parse_blocks(os.path.join(src, f"{base}Monte.rsp")):
            if "Seed" in b:
                seed = b["Seed"]
            elif "MD" in b and len(mds) < 3:
                mds.append(b["MD"])
        body = f'(def seed "{seed}")\n(def checkpoints ["' + '"\n  "'.join(mds) + '"])\n'
        made.append(write_ns(out_dir, f"sha3.cavp.sha3-{n}-monte",
                             f"CAVP {base}Monte.rsp: the seed and its first {len(mds)} checkpoints.",
                             body))
    for n in shake:
        base = f"SHAKE{n}"
        short = [b for b in parse_blocks(os.path.join(src, f"{base}ShortMsg.rsp")) if "Len" in b]
        rows = [[b["Len"], f'"{msg_hex(b)}"', f'"{b["Output"]}"'] for b in short]
        made.append(write_ns(out_dir, f"sha3.cavp.shake{n}-short",
                             f"CAVP {base}ShortMsg.rsp: [len-bits msg-hex output-hex], all {len(rows)} entries (fixed output length).",
                             vectors_literal(rows)))
        long_ = [b for b in parse_blocks(os.path.join(src, f"{base}LongMsg.rsp")) if "Len" in b][:5]
        rows = [[b["Len"], f'"{msg_hex(b)}"', f'"{b["Output"]}"'] for b in long_]
        made.append(write_ns(out_dir, f"sha3.cavp.shake{n}-long",
                             f"CAVP {base}LongMsg.rsp: first {len(rows)} entries.",
                             vectors_literal(rows)))
        var = [b for b in parse_blocks(os.path.join(src, f"{base}VariableOut.rsp")) if "Outputlen" in b]
        var = [b for i, b in enumerate(var) if i % 4 == 0 and int(b["Outputlen"]) % 8 == 0]
        rows = [[b["Outputlen"], f'"{b["Msg"]}"', f'"{b["Output"]}"'] for b in var]
        made.append(write_ns(out_dir, f"sha3.cavp.shake{n}-variable",
                             f"CAVP {base}VariableOut.rsp: [outputlen-bits msg-hex output-hex], {len(rows)} entries (every 4th, whole bytes only).",
                             vectors_literal(rows)))
    total = 0
    for p in made:
        sz = os.path.getsize(p)
        total += sz
        print(f"{sz:8d}  {p}")
    print(f"{total:8d}  total, {len(made)} files")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
