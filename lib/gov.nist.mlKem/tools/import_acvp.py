#!/usr/bin/env python3
"""Turn the NIST ACVP ML-KEM-768 test vectors into portable test data (.cljk).

Dev tool, not part of the library. Standard library only.

    python3 -I tools/import_acvp.py <keyGen internalProjection.json> \
                                    <encapDecap internalProjection.json> <out dir>

Source: usnistgov/ACVP-Server, gen-val/json-files/ML-KEM-keyGen-FIPS203 and
ML-KEM-encapDecap-FIPS203 (see test/acvp/PROVENANCE.md). Only the ML-KEM-768 groups
are kept; every test of those groups is kept. Hex is lowercased.
"""
import json
import os
import sys


def lit(s):
    return '"' + s.lower() + '"'


def write(out_dir, name, doc, rows):
    path = os.path.join(out_dir, name.replace("-", "_") + ".cljk")
    with open(path, "w", encoding="ascii") as f:
        f.write(f'(ns mlkem.acvp.{name}\n  "{doc}")\n\n(def vectors\n  [\n')
        for r in rows:
            f.write("   [" + " ".join(r) + "]\n")
        f.write("])\n")
    return path, len(rows)


def main(keygen_json, encdec_json, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    kg = json.load(open(keygen_json))
    ed = json.load(open(encdec_json))
    made = []
    g = [g for g in kg["testGroups"] if g["parameterSet"] == "ML-KEM-768"]
    assert len(g) == 1
    rows = [[str(t["tcId"]), lit(t["d"]), lit(t["z"]), lit(t["ek"]), lit(t["dk"])] for t in g[0]["tests"]]
    made.append(write(out_dir, "keygen",
                      "ACVP ML-KEM keyGen, ML-KEM-768: [tc-id d z ek dk].", rows))
    groups = [g for g in ed["testGroups"] if g["parameterSet"] == "ML-KEM-768"]
    def by(fn):
        gs = [g for g in groups if g.get("function") == fn]
        assert len(gs) == 1, fn
        return gs[0]["tests"]
    rows = [[str(t["tcId"]), lit(t["ek"]), lit(t["m"]), lit(t["c"]), lit(t["k"])] for t in by("encapsulation")]
    made.append(write(out_dir, "encaps",
                      "ACVP ML-KEM encapsulation AFT, ML-KEM-768: [tc-id ek m c k].", rows))
    rows = [[str(t["tcId"]), lit(t["dk"]), lit(t["c"]), lit(t["k"]), '"' + t["reason"] + '"'] for t in by("decapsulation")]
    made.append(write(out_dir, "decaps",
                      "ACVP ML-KEM decapsulation VAL, ML-KEM-768: [tc-id dk c k reason]. 'modified ciphertext' cases test implicit rejection.", rows))
    rows = [[str(t["tcId"]), lit(t["dk"]), "true" if t["testPassed"] else "false", '"' + t["reason"] + '"'] for t in by("decapsulationKeyCheck")]
    made.append(write(out_dir, "dk-check",
                      "ACVP ML-KEM decapsulationKeyCheck VAL, ML-KEM-768: [tc-id dk passed? reason].", rows))
    rows = [[str(t["tcId"]), lit(t["ek"]), "true" if t["testPassed"] else "false", '"' + t["reason"] + '"'] for t in by("encapsulationKeyCheck")]
    made.append(write(out_dir, "ek-check",
                      "ACVP ML-KEM encapsulationKeyCheck VAL, ML-KEM-768: [tc-id ek passed? reason].", rows))
    for p, n in made:
        print(f"{os.path.getsize(p):8d}  {n:3d} vectors  {p}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
