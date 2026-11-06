#!/usr/bin/env python3
"""Host oracle for the kernel multi-signature image admission (aiueos.imgsig, JUN-813 stage 5a, ADR-0286 amendment 2).

Builds the fw_cfg file the QEMU gate hands to the guest, the expected verdicts, and the generated module of pinned TEST keys.
Every key here is a fixed, public test value (RFC 8032 seeds for Ed25519, byte-pattern seeds for ML-DSA-65); no key here is, or
can become, a production key. Ed25519 signing and verification use the repository's RFC 8032 integer reference; ML-DSA-65 uses
lib/gov.nist.mlDsa/tools/reference.py (ACVP-checked). The expected verdict of each case is computed from those independent
references, not copied from the kernel.

Header (16384 bytes per case, see ADR-0286 amendment 2): 0 "AIUEIMG2", 8 version u64, 16 size u64, 24..31 reserved zero, 32 SHA-256
of the image (bytes 0..63 are the signed manifest); 64 count u32 (1..4), 68..127 zero; then up to 4 entries of 3392 bytes from 128:
0 key id u32, 4..7 zero, 8 Ed25519 signature (64), 72 ML-DSA-65 signature (3309), 3381..3391 zero. Both signatures cover the
64-byte manifest; the ML-DSA message is M' = 0 || 8 || "AIUEIMG2" || manifest (context "AIUEIMG2").
Verdicts: 1 admitted, 2 bad magic, 3 count outside 1..4, 4 fewer than M=2 distinct valid signers, 5 manifest reserved bytes not zero.
"""
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REF = HERE.parents[2].parent / "gov.nist.mlDsa" / "tools"
sys.path.insert(0, str(REF))
import reference as ref  # noqa: E402

N_SLOTS, M_REQ, HDR, ENTRY = 3, 2, 16384, 3392
CTX = b"AIUEIMG2"
ED_SEEDS = [bytes.fromhex(h) for h in (
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
    "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
    "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7")]


def _edref():
    spec = importlib.util.spec_from_file_location("ed_integer_reference", HERE / "check-native-consent-qemu.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


edr = _edref()


def ed_sign(seed, msg):
    expanded = bytearray(hashlib.sha512(seed).digest())
    scalar = bytearray(expanded[:32]); scalar[0] &= 248; scalar[31] &= 127; scalar[31] |= 64
    a = int.from_bytes(scalar, "little"); pub = edr._enc(edr._mul(a, edr._B))
    r = int.from_bytes(hashlib.sha512(bytes(expanded[32:]) + msg).digest(), "little") % edr._L
    rr = edr._enc(edr._mul(r, edr._B))
    k = int.from_bytes(hashlib.sha512(rr + pub + msg).digest(), "little") % edr._L
    return pub, rr + ((r + k * a) % edr._L).to_bytes(32, "little")


_KEYS = None


def keys():
    """[(ed_seed, ed_pk, ml_pk, ml_sk)] for the three pinned test signers."""
    global _KEYS
    if _KEYS is None:
        _KEYS = []
        for i in range(N_SLOTS):
            pk, sk = ref.keygen(bytes([0x10 + i]) * 32)
            _KEYS.append((ED_SEEDS[i], ed_sign(ED_SEEDS[i], b"")[0], pk, sk))
    return _KEYS


def manifest(version=5, size=5000, reserved=bytes(8), magic=b"AIUEIMG2"):
    return magic + struct.pack("<QQ", version, size) + reserved + hashlib.sha256(b"imgsig fixture image").digest()


def mprime(man, ctx=CTX):
    return bytes([0, len(ctx)]) + ctx + man


def sign_entry(slot, man, ctx=CTX):
    seed, _pk, mpk, msk = keys()[slot]
    ed = ed_sign(seed, man)[1]
    ml = ref.sign_mu(msk, ref.mu_of(mpk, mprime(man, ctx)), bytes([slot + 1]) * 32)
    return ed, ml


def entry(kid, ed, ml, reserved=bytes(4), pad=bytes(11)):
    assert len(ed) == 64 and len(ml) == 3309 and len(reserved) == 4 and len(pad) == 11
    return struct.pack("<I", kid) + reserved + ed + ml + pad


def flip(b, at, mask=1):
    x = bytearray(b); x[at] ^= mask
    return bytes(x)


def header(man, entries, count=None, layout=None):
    """layout: optional (offset, byte) written into the must-be-zero bytes 68..127."""
    body = man + struct.pack("<I", len(entries) if count is None else count)
    body = body.ljust(128, b"\0")
    if layout is not None:
        body = flip(body, layout[0], layout[1])
    body += b"".join(entries)
    assert len(body) <= HDR
    return body.ljust(HDR, b"\0")


PROD_PUBKEYS = HERE.parent / "fixtures" / "signers" / "prod-pubkeys.json"
_PUBS = {}


def pubkeys(ks="test"):
    """[(ed_pk, ml_pk)] of the three pinned slots: ks 'test' the TEST keys, 'prod' the production PUBLIC keys read from
    fixtures/signers/prod-pubkeys.json (public data; the private seeds are not in the repository). JUN-813, ADR-0286 amendment 7."""
    if ks not in _PUBS:
        if ks == "test":
            _PUBS[ks] = [(k[1], k[2]) for k in keys()]
        else:
            assert ks == "prod", ks
            j = json.loads(PROD_PUBKEYS.read_text())
            assert j["schema"] == "aiueos.imgsig-prodkeys.v1" and [s["id"] for s in j["slots"]] == list(range(N_SLOTS))
            _PUBS[ks] = [(bytes.fromhex(s["ed25519"]), bytes.fromhex(s["mldsa65"])) for s in j["slots"]]
    return _PUBS[ks]


def ed_valid(slot, man, sig, ks="test"):
    return edr.ed_verify(pubkeys(ks)[slot][0], man, sig)


def ml_valid(slot, man, sig, ks="test", ctx=CTX):
    pk = pubkeys(ks)[slot][1]
    return ref.verify_mu(pk, ref.mu_of(pk, mprime(man, ctx)), sig)


def verdict(hdr, ks="test"):
    """Independent reference of the admission rule: (verdict, mask of the slots that counted) under the key set ks."""
    if hdr[:8] != CTX:
        return 2, 0
    if hdr[24:32] != bytes(8):
        return 5, 0
    count = struct.unpack_from("<I", hdr, 64)[0]
    if not 1 <= count <= 4 or hdr[68:128] != bytes(60):
        return 3, 0
    man, seen = hdr[:64], set()
    for i in range(count):
        e = hdr[128 + i * ENTRY:128 + (i + 1) * ENTRY]
        kid = struct.unpack_from("<I", e, 0)[0]
        if kid >= N_SLOTS or kid in seen or e[4:8] != bytes(4) or e[3381:] != bytes(11):
            continue
        if ed_valid(kid, man, e[8:72], ks) and ml_valid(kid, man, e[72:3381], ks):
            seen.add(kid)
    return (1 if len(seen) >= M_REQ else 4), sum(1 << i for i in seen)


def cases():
    man = manifest()
    sg = {s: sign_entry(s, man) for s in range(N_SLOTS)}
    e = lambda s: entry(s, *sg[s])
    bad_ctx = sign_entry(0, man, b"AIUEIMG1")
    rows = [
        ("two-signers", header(man, [e(0), e(1)]), 1),
        ("three-signers", header(man, [e(0), e(1), e(2)]), 1),
        ("order-2-0", header(man, [e(2), e(0)]), 1),
        ("one-signer", header(man, [e(0)]), 4),
        ("duplicate-id", header(man, [e(0), e(0)]), 4),
        ("unknown-id", header(man, [entry(7, *sg[0]), e(0)]), 4),
        ("ed-half-bad", header(man, [entry(0, flip(sg[0][0], 5), sg[0][1]), e(1)]), 4),
        ("ml-half-bad", header(man, [entry(0, sg[0][0], flip(sg[0][1], 100, 0x10)), e(1)]), 4),
        ("ed25519-only", header(man, [entry(0, sg[0][0], bytes(3309)), entry(1, sg[1][0], bytes(3309))]), 4),
        ("mldsa-only", header(man, [entry(0, bytes(64), sg[0][1]), entry(1, bytes(64), sg[1][1])]), 4),
        ("manifest-tamper", header(flip(man, 8), [e(0), e(1)]), 4),
        ("wrong-context", header(man, [entry(0, sg[0][0], bad_ctx[1]), e(1)]), 4),
        ("bad-magic", header(flip(man, 0), [e(0), e(1)]), 2),
        ("count-zero", header(man, [e(0), e(1)], count=0), 3),
        ("count-five", header(man, [e(0), e(1)], count=5), 3),
        ("manifest-reserved", header(flip(man, 24), [e(0), e(1)]), 5),
        # review hardening (JUN-813): every must-be-zero byte group, the largest header, and key ids with a high byte set
        ("pad-nonzero-first", header(man, [entry(0, *sg[0], pad=b"\1" + bytes(10)), e(1)]), 4),
        ("pad-nonzero-last", header(man, [entry(0, *sg[0], pad=bytes(10) + b"\x80"), e(1)]), 4),
        ("entry-reserved-4", header(man, [entry(0, *sg[0], reserved=b"\1\0\0\0"), e(1)]), 4),
        ("entry-reserved-7", header(man, [entry(0, *sg[0], reserved=b"\0\0\0\x80"), e(1)]), 4),
        ("layout-68", header(man, [e(0), e(1)], layout=(68, 1)), 3),
        ("layout-127", header(man, [e(0), e(1)], layout=(127, 0x80)), 3),
        ("count-four-dup", header(man, [e(0), e(1), e(2), e(1)]), 1),
        ("count-four-last-counts", header(man, [e(0), entry(7, *sg[1]), e(0), e(1)]), 1),
        ("id-256", header(man, [entry(256, *sg[0]), e(1)]), 4),
        ("id-65536", header(man, [entry(65536, *sg[0]), e(1)]), 4),
        ("id-16777216", header(man, [entry(0x01000000, *sg[0]), e(1)]), 4),
    ]
    out = []
    for name, h, want in rows:
        got, mask = verdict(h)
        assert got == want, (name, got, want)
        out.append(dict(name=name, hdr=h, code=want, mask=mask))
    return out


def fw_file():
    out = cases()
    return bytes([len(out)]) + b"".join(c["hdr"] for c in out), out


def u32le(b):
    return [struct.unpack_from("<I", b, i)[0] for i in range(0, len(b), 4)]


def emit_keys_module_from(ks, ns, comments):
    """Generated Kotoba module of pinned public keys (words, little endian) for ks = [(_, ed_pk, ml_pk, _)] in namespace ns."""
    L = ["(ns %s (:export [ims-ed-word ims-ml-word]))" % ns] + [";; " + c for c in comments]
    for i, (_s, edpk, mlpk, _sk) in enumerate(ks):
        L.append("(defn- ed%d [w] (case w %s 0))" % (i, " ".join("%d %d" % (j, v) for j, v in enumerate(u32le(edpk)))))
        L.append("(defn- ml%d [w] (case w %s 0))" % (i, " ".join("%d %d" % (j, v) for j, v in enumerate(u32le(mlpk)))))
    L.append("(defn ims-ed-word [id w] (case id 0 (ed0 w) 1 (ed1 w) 2 (ed2 w) 0))")
    L.append("(defn ims-ml-word [id w] (case id 0 (ml0 w) 1 (ml1 w) 2 (ml2 w) 0))")
    return "\n".join(L) + "\n"


def emit_keys_module():
    """Generated Kotoba module of the pinned TEST public keys (words, little endian)."""
    return emit_keys_module_from(
        keys(), "aiueos.imgsig-testkeys",
        ["GENERATED by scripts/imgsig_oracle.py --emit-keys. Pinned TEST public keys for the stage 5a gate: Ed25519 from the RFC 8032",
         "seeds, ML-DSA-65 from fixed byte-pattern seeds. They prove the code path; none is a production key (ADR-0286 amendment 2)."])


if __name__ == "__main__":
    if "--emit-keys" in sys.argv:
        sys.stdout.write(emit_keys_module())
    else:
        blob, out = fw_file()
        print(len(blob), [(c["name"], c["code"], c["mask"]) for c in out])
