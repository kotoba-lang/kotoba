#!/usr/bin/env python3
"""Stage actual Amu receipt bytes as inputs to a native Kotoba test project.

This script only copies bytes and generates literal fixtures and a KSL1 lock.
The generated Kotoba program, compiled by Amu, owns the pass/fail decision.
The receipt's observed stack field is used as the expected stack to exercise
the parser across the corpus; this is not an independent admission decision.
"""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--receipt-dir", type=Path, required=True)
    ap.add_argument("--validator", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    corpus = args.receipt_dir.resolve(strict=True)
    source = args.validator.resolve(strict=True)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = out / "src"
    module = root / "kototama"
    module.mkdir(parents=True)
    validator = module / "pure_i64_receipt.kotoba"
    entry = module / "pure_i64_receipt_gate.kotoba"
    shutil.copyfile(source, validator)

    report = json.loads((corpus / "report.json").read_text())
    rows = [row for row in report["cases"]
            if row["compileExit"] == 0 and row["outputBytes"] == 64]
    if not rows:
        raise ValueError("receipt corpus has no emitted 64-byte outputs")

    parts = ["(ns kototama.pure-i64-receipt-gate (:export [main]) "
             "(:require [kototama.pure-i64-receipt :as r]))\n"]
    for start in range(0, len(rows), 8):
        terms = []
        for row in rows[start:start + 8]:
            index = row["index"]
            budget = row["budget"]
            exit_code = row["guestExit"]
            if (not isinstance(index, int) or index < 0 or index > 999999
                    or not isinstance(budget, int) or not isinstance(exit_code, int)):
                raise ValueError("invalid case metadata")
            data = (corpus / f"{index:03d}-guest.stdout").read_bytes()
            if len(data) != 64:
                raise ValueError(f"case {index} does not contain 64 bytes")
            stack = int.from_bytes(data[56:64], "little", signed=True)
            vector = "[" + " ".join(str(byte) for byte in data) + "]"
            call = f"{exit_code} {budget} {stack}"
            terms.append(f"(r/valid? {vector} {call})")
            terms.append(f"(not (r/valid? (vector-assoc! {vector} 0 0) {call}))")
        parts.append(f"(defn- group-{start // 8} [] :bool (and\n"
                     + "\n".join(terms) + "))\n")
    groups = " ".join(f"(group-{i})" for i in range((len(rows) + 7) // 8))
    parts.append(f"(defn main [] :i64 (if (and {groups}) 42 0))\n")
    entry.write_text("".join(parts))
    lock = out / "project.ksl"
    lock.write_text("KSL1\nentry " + str(entry) + "\nroot " + str(root) + "\n"
                    + "".join(f"file {digest(path)} {path}\n"
                              for path in sorted((entry, validator))))
    print(json.dumps({"stagedReceipts": len(rows), "magicTamperControls": len(rows),
                      "entrySHA256": digest(entry), "validatorSHA256": digest(validator),
                      "lockSHA256": digest(lock)}, sort_keys=True))


if __name__ == "__main__":
    main()
