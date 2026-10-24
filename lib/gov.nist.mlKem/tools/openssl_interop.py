#!/usr/bin/env python3
"""Interoperate with OpenSSL's ML-KEM-768 (an independent implementation).

Dev tool, not part of the library. Needs `openssl` with ML-KEM (3.5 or later) and
`kbb`. Run from the repo root, with ../org-nist-sha3 checked out beside it:

    python3 -I tools/openssl_interop.py <scratch dir>

For three fresh OpenSSL keys it checks, with throwaway keys only:
  1. keygen from the OpenSSL key's 64-byte seed gives OpenSSL's decapsulation key;
  2. decaps of a ciphertext that OpenSSL produced gives OpenSSL's shared secret;
  3. decaps of a MODIFIED ciphertext gives the same rejection key as OpenSSL
     (implicit rejection, J(z || c));
  4. OpenSSL decapsulates a ciphertext that this library produced to the same key.
"""
import os
import re
import subprocess
import sys


def run(*a, **kw):
    return subprocess.run(a, capture_output=True, check=True, **kw)


def hexblock(text, name):
    m = re.search(name + r":\n((?:\s+[0-9a-f:]+\n)+)", text)
    return re.sub(r"[\s:]", "", m.group(1))


def main(work):
    os.makedirs(work, exist_ok=True)
    os.chdir(work)
    cases = []
    for n in range(3):
        run("openssl", "genpkey", "-algorithm", "ML-KEM-768", "-out", f"k{n}.pem")
        run("openssl", "pkey", "-in", f"k{n}.pem", "-pubout", "-out", f"p{n}.pem")
        txt = run("openssl", "pkey", "-in", f"k{n}.pem", "-text", "-noout").stdout.decode()
        run("openssl", "pkeyutl", "-encap", "-pubin", "-inkey", f"p{n}.pem",
            "-out", f"ct{n}.bin", "-secret", f"ss{n}.bin")
        ct = open(f"ct{n}.bin", "rb").read()
        bad = bytearray(ct)
        bad[500] ^= 1
        open(f"bad{n}.bin", "wb").write(bad)
        run("openssl", "pkeyutl", "-decap", "-inkey", f"k{n}.pem", "-in", f"bad{n}.bin",
            "-secret", f"badss{n}.bin")
        cases.append((hexblock(txt, "seed"), hexblock(txt, "dk"), ct.hex(),
                      open(f"ss{n}.bin", "rb").read().hex(), bytes(bad).hex(),
                      open(f"badss{n}.bin", "rb").read().hex()))
    with open("cases.cljk", "w") as f:
        f.write("(ns cases)\n(def cases [\n")
        for seed, dk, ct, ss, bad, badss in cases:
            f.write(f'  {{:seed "{seed}" :dk "{dk}" :ct "{ct}" :ss "{ss}" :bad "{bad}" :badss "{badss}"}}\n')
        f.write("])\n")
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    work_abs = os.getcwd()
    with open("interop.cljk", "w") as f:
        f.write("""(require '[mlkem.core :as m] '[mlkem.test-util :as tu :refer [hex->bytes bytes->hex]] '[cases :as c])
(doseq [[i {:keys [seed dk ct ss bad badss]}] (map-indexed vector c/cases)]
  (let [s (hex->bytes seed)
        r (m/keygen (subvec s 0 32) (subvec s 32 64))
        mine (m/encaps (:ek r) (tu/seed 40))]
    (println (str "key " i
                  " | keygen = OpenSSL dk: " (= dk (bytes->hex (:dk r)))
                  " | decaps(OpenSSL ct) = OpenSSL secret: " (= ss (bytes->hex (m/decaps (:dk r) (hex->bytes ct))))
                  " | decaps(modified ct) = OpenSSL rejection key: " (= badss (bytes->hex (m/decaps (:dk r) (hex->bytes bad))))))
    (spit (str "mine" i ".hex") (str (bytes->hex (:c mine)) "\\n" (bytes->hex (:k mine)) "\\n"))))
""")
    cp = f"{root}/src:{root}/test:{root}/../org-nist-sha3/src:{work_abs}"
    print(subprocess.run(["kbb", "--backend", "sci", "--classpath", cp, "interop.cljk"],
                         capture_output=True, check=True).stdout.decode(), end="")
    ok = True
    for n in range(3):
        ct, k = open(f"mine{n}.hex").read().split()
        open(f"mine_ct{n}.bin", "wb").write(bytes.fromhex(ct))
        run("openssl", "pkeyutl", "-decap", "-inkey", f"k{n}.pem", "-in", f"mine_ct{n}.bin",
            "-secret", f"mine_ss{n}.bin")
        same = open(f"mine_ss{n}.bin", "rb").read().hex() == k
        ok &= same
        print(f"key {n} | OpenSSL decaps(this library's ciphertext) = this library's key: {same}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
