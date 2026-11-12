#!/usr/bin/env python3
"""Host oracle for the kernel ML-DSA-65 verifier (aiueos.mldsa-verify, JUN-813 stage 4).

Builds the fw_cfg file the QEMU gate hands to the guest and the expected results. Keys and signatures come from the independent
Python reference lib/gov.nist.mlDsa/tools/reference.py (written from FIPS 204 and checked against the ACVP keyGen, sigGen and
sigVer ML-DSA-65 groups before the .kotoba port; its files are pinned in the gate report). The expected code mirrors the kernel's:
1 valid, 0 c-tilde differs, 2 malformed hint, 3 ||z|| out of bound. File layout: [count:1] [pk:1952], then per case
[signature:3309] [len(M'):1] [M':100]. No key here is a real key; the seed is a fixed test value.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REF = HERE.parents[2].parent / "gov.nist.mlDsa" / "tools"
sys.path.insert(0, str(REF))
import reference as ref  # noqa: E402

MP_MAX = 100


def parse_hint(hb):
    """The kernel's Algorithm 21 check; True when well formed."""
    idx = 0
    for i in range(ref.K):
        lim = hb[ref.OMEGA + i]
        if lim < idx or lim > ref.OMEGA:
            return False
        first = idx
        while idx < lim:
            if idx > first and hb[idx - 1] >= hb[idx]:
                return False
            idx += 1
    return all(hb[p] == 0 for p in range(idx, ref.OMEGA))


def z_of(sig):
    return [[(ref.G1 - x) % ref.Q for x in ref.unpack(sig, 48 + 640 * i, 20)] for i in range(ref.L)]


def expected(pk, mp, sig):
    mu = ref.mu_of(pk, mp)
    if not parse_hint(sig[3248:]):
        return 2, mu
    if ref.inf(z_of(sig)) >= ref.G1 - ref.BETA:
        return 3, mu
    return (1 if ref.verify_mu(pk, mu, sig) else 0), mu


def sign_z_over(sk, mu, rnd):
    """The first candidate that fails only the ||z|| test (same construction as lib/gov.nist.mlDsa/tools/gen_gate.py)."""
    rho, key, tr, s1, s2, t0 = ref.sk_decode(sk)
    s1h = [ref.ntt(x) for x in s1]; s2h = [ref.ntt(x) for x in s2]; t0h = [ref.ntt(x) for x in t0]; A = ref.expand_a(rho)
    rpp = ref.shake256(list(key) + list(rnd) + list(mu), 64); kap = 0
    while True:
        y = [[(ref.G1 - x) % ref.Q for x in ref.unpack(ref.shake256(list(rpp) + [(kap + r) & 255, (kap + r) >> 8], 640), 0, 20)] for r in range(ref.L)]
        w = [ref.intt(p) for p in ref.matvec(A, [ref.ntt(p) for p in y])]
        ct = ref.shake256(list(mu) + sum((ref.pack([ref.high(x) for x in p], 4) for p in w), []), 48)
        ch = ref.ntt(ref.sample_in_ball(ct))
        z = [ref.padd(a, ref.intt(ref.pmul(ch, x))) for a, x in zip(y, s1h)]
        wm = [ref.psub(a, ref.intt(ref.pmul(ch, x))) for a, x in zip(w, s2h)]
        kap += ref.L
        if ref.inf(z) < ref.G1 - ref.BETA or max(abs(ref.low(x)) for p in wm for x in p) >= ref.G2 - ref.BETA:
            continue
        ct0 = [ref.intt(ref.pmul(ch, x)) for x in t0h]
        h = [[int(ref.high(a) != ref.high((a + b) % ref.Q)) for a, b in zip(pa, pb)] for pa, pb in zip(wm, ct0)]
        if ref.inf(ct0) >= ref.G2 or sum(map(sum, h)) > ref.OMEGA:
            continue
        hb = [0] * (ref.OMEGA + ref.K); idx = 0
        for i in range(ref.K):
            for jj in range(256):
                if h[i][jj]:
                    hb[idx] = jj; idx += 1
            hb[ref.OMEGA + i] = idx
        return bytes(list(ct) + sum((ref.pack([(ref.G1 - ref.cent(x, ref.Q)) for x in p], 20) for p in z), []) + hb)


def flip(sig, at, mask=1):
    b = bytearray(sig); b[at] ^= mask
    return bytes(b)


def cases():
    pk, sk = ref.keygen(bytes(range(32)))
    mp_a = bytes([0, 0]) + b"aiueos image A"
    mp_b = bytes([0, 0]) + b"aiueos image B"
    sig_a = ref.sign_mu(sk, ref.mu_of(pk, mp_a), bytes(32))
    sig_b = ref.sign_mu(sk, ref.mu_of(pk, mp_b), bytes([7]) * 32)
    hb = list(sig_a[3248:])
    idx = 0
    for i in range(ref.K):
        if hb[ref.OMEGA + i] - idx >= 2:
            hb[idx], hb[idx + 1] = hb[idx + 1], hb[idx]; break
        idx = hb[ref.OMEGA + i]
    else:
        raise AssertionError("no row with two hints")
    hint_order = sig_a[:3248] + bytes(hb)
    count = sig_a[3248 + ref.OMEGA + ref.K - 1]
    assert count < ref.OMEGA
    hint_pad = flip(sig_a, 3248 + count, 1)
    hint_limit = flip(sig_a, 3248 + ref.OMEGA, 0)  # replaced below
    hb2 = bytearray(sig_a[3248:]); hb2[ref.OMEGA] = ref.OMEGA + 1
    hint_limit = sig_a[:3248] + bytes(hb2)
    z_over = sign_z_over(sk, ref.mu_of(pk, mp_a), bytes(32))
    rows = [("valid-a", sig_a, mp_a), ("valid-b", sig_b, mp_b), ("wrong-message", sig_a, mp_b),
            ("flip-ctilde", flip(sig_a, 3), mp_a), ("flip-z", flip(sig_a, 100, 0x10), mp_a),
            ("hint-order", hint_order, mp_a), ("hint-padding", hint_pad, mp_a), ("hint-limit", hint_limit, mp_a),
            ("z-over-bound", z_over, mp_a)]
    out = []
    for name, sig, mp in rows:
        code, mu = expected(pk, mp, sig)
        out.append(dict(name=name, sig=sig, mp=mp, code=code, mu=mu))
    want = {"valid-a": 1, "valid-b": 1, "wrong-message": 0, "flip-ctilde": 0, "hint-order": 2, "hint-padding": 2, "hint-limit": 2,
            "z-over-bound": 3}
    for c in out:
        if c["name"] in want:
            assert c["code"] == want[c["name"]], (c["name"], c["code"])
    return pk, out


def fw_file():
    pk, out = cases()
    data = bytearray([len(out)]) + pk
    for c in out:
        assert len(c["mp"]) <= MP_MAX and len(c["sig"]) == 3309
        data += c["sig"] + bytes([len(c["mp"])]) + c["mp"].ljust(MP_MAX, b"\0")
    return bytes(data), out


if __name__ == "__main__":
    blob, out = fw_file()
    print(len(blob), [(c["name"], c["code"]) for c in out])
