#!/usr/bin/env python3
"""Host oracle for the AIUECAT1 catalog admission of native/update.kotoba (JUN-813 stage 6, ADR-0286 amendment 5).

Builds the fw_cfg file opt/aiueos/cat1 the QEMU gate hands to the guest: [count][per case: mode (0 = pinned TEST keys, 1 =
production signer set), 16384 header bytes, 8192 body bytes (the catalog body padded with zeros; only `size` of them are streamed)],
and the verdict the kernel must reach for each case. Keys, signing and the Ed25519 / ML-DSA-65 references come from imgsig_oracle (public
TEST keys; RFC 8032 integer Ed25519 and the ACVP-checked ML-DSA-65 reference). The verdict is computed here, independently of the
kernel, from the byte layout of ADR-0286 amendment 5 and the independent signature references; every case also states the verdict it
was MEANT to produce, and the oracle refuses to build when the two differ.

Layout (amendment 5). Header, 16384 bytes, the AIUEIMG2 signature block: manifest 0..63, signature count u32 at 64 (1..4), 68..127 zero,
up to four 3392-byte entries from 128 (key id u32, 4 zero, Ed25519 64, ML-DSA-65 3309, 11 zero), the tail ignored. Manifest: 0 "AIUECAT1",
8 version u64 (>= 1), 16 body length u64 (= 128 * count), 24 catalog entry count u32 (1..64), 28..31 zero, 32 SHA-256 of the body. Both
signatures cover the 64-byte manifest; the ML-DSA message is M' = 0 || 8 || "AIUECAT1" || manifest. The body (128 * count bytes)
follows the header at byte 16384. Body entry (128 bytes): 0 dock id u32 (19..82), 4 title (32 bytes: 1..31 printable ASCII 0x20..0x7e, a NUL,
then zeros), 36 manifest CID (36), 72 bundle CID (36), 108 size u32 (1..33554432), 112..127 zero. A CID is the binary CIDv1 envelope of
aiueos.cid-v1-admit: 01, codec (55, 70 or 71), 12, 20, then a 32-byte digest.

Result codes of update.kotoba: 15 catalog verified; 16 the body hash matches but an entry is refused (flags: 1 dock id outside 19..82, 2
duplicate dock id, 4 reserved bytes not zero, 8 bad title, 16 bad CID, 32 size outside 1..2^25); 7 body hash differs; 1 fewer than two
distinct valid signers; 2 bad magic; 3 signature count/layout, or entry count/length; 4 version below 1; 5 manifest reserved not zero;
8 no production signer set pinned.
"""
import hashlib
import struct
import sys

import imgsig_oracle as o

ref = o.ref
CTX = b"AIUECAT1"
IMG_CTX = b"AIUEIMG2"
ENT, SLOT = 128, 8192
DOCK_MIN, DOCK_MAX = 19, 82
SIZE_MAX = 33554432
CODECS = (0x55, 0x70, 0x71)

_SIGS = {}


def sign(slot, man, ctx=CTX):
    key = (slot, man, ctx)
    if key not in _SIGS:
        _SIGS[key] = o.sign_entry(slot, man, ctx)
    return _SIGS[key]


def cid(seed=0, codec=0x55):
    return bytes([1, codec, 0x12, 0x20]) + hashlib.sha256(b"cat fixture cid %d" % seed).digest()


def app(dock, title=b"Zuhyo", seed=None, mcid=None, bcid=None, size=4096, reserved=bytes(16)):
    t = title if len(title) == 32 else title + bytes(32 - len(title))
    assert len(t) == 32 and len(reserved) == 16
    s = dock if seed is None else seed
    mcid = cid(2 * s) if mcid is None else mcid
    bcid = cid(2 * s + 1, 0x70) if bcid is None else bcid
    assert len(mcid) == 36 and len(bcid) == 36
    return struct.pack("<I", dock) + t + mcid + bcid + struct.pack("<I", size) + reserved


def manifest(body, version=7, count=None, length=None, reserved=bytes(4), magic=CTX, digest=None):
    count = len(body) // ENT if count is None else count
    length = len(body) if length is None else length
    return magic + struct.pack("<QQI", version, length, count) + reserved + (hashlib.sha256(body).digest() if digest is None else digest)


def two_of_three(man, slots=(0, 1), ctx=CTX):
    return [o.entry(s, *sign(s, man, ctx)) for s in slots]


# ---- the independent verdict -------------------------------------------------------------------------------------------------------
def ml_valid(slot, man, sig):
    pk = o.keys()[slot][2]
    return ref.verify_mu(pk, ref.mu_of(pk, o.mprime(man, CTX)), sig)


def counted(hdr):
    """Mask of the pinned slots whose entry counts: pinned id not seen, zero reserved/padding, Ed25519 and ML-DSA-65 valid."""
    man, seen, mask = hdr[:64], set(), 0
    for i in range(struct.unpack_from("<I", hdr, 64)[0]):
        e = hdr[128 + i * o.ENTRY:128 + (i + 1) * o.ENTRY]
        kid = struct.unpack_from("<I", e, 0)[0]
        if kid >= o.N_SLOTS or kid in seen or e[4:8] != bytes(4) or e[3381:] != bytes(11):
            continue
        if o.ed_valid(kid, man, e[8:72]) and ml_valid(kid, man, e[72:3381]):
            seen.add(kid); mask |= 1 << kid
    return mask


def title_ok(t):
    n = t.find(b"\0")
    return n >= 1 and all(0x20 <= c <= 0x7e for c in t[:n]) and t[n:] == bytes(len(t) - n)


def cid_ok(c):
    return c[0] == 1 and c[1] in CODECS and c[2] == 0x12 and c[3] == 0x20


def entry_flags(e, seen):
    dock = struct.unpack_from("<I", e, 0)[0]
    f = 0
    if not DOCK_MIN <= dock <= DOCK_MAX:
        f |= 1
    elif dock in seen:
        f |= 2
    else:
        seen.add(dock)
    if e[112:] != bytes(16): f |= 4
    if not title_ok(e[4:36]): f |= 8
    if not (cid_ok(e[36:72]) and cid_ok(e[72:108])): f |= 16
    if not 1 <= struct.unpack_from("<I", e, 108)[0] <= SIZE_MAX: f |= 32
    return f


def verdict(hdr, body, mode):
    """(result, counted mask, flags) the kernel must report; flags only when the result is 16."""
    if hdr[:8] != CTX:
        return 2, 0, 0
    if hdr[28:32] != bytes(4):
        return 5, 0, 0
    sigs = struct.unpack_from("<I", hdr, 64)[0]
    if not 1 <= sigs <= 4 or hdr[68:128] != bytes(60):
        return 3, 0, 0
    if mode == 1:
        return 8, 0, 0
    mask = counted(hdr)
    if bin(mask).count("1") < 2:
        return 1, mask, 0
    version, length, count = struct.unpack_from("<QQI", hdr, 8)
    if not 1 <= count <= 64 or length != ENT * count:
        return 3, mask, 0
    if version < 1:
        return 4, mask, 0
    body = body[:length]
    if len(body) != length or hashlib.sha256(body).digest() != hdr[32:64]:
        return 7, mask, 0
    seen, flags = set(), 0
    for i in range(count):
        flags |= entry_flags(body[i * ENT:(i + 1) * ENT], seen)
    return (16, mask, flags) if flags else (15, mask, 0)


# ---- the cases ---------------------------------------------------------------------------------------------------------------------
def cases():
    good = b"".join(app(d, b"App %d" % d) for d in (19, 20, DOCK_MAX))
    man = manifest(good)
    full = b"".join(app(d, b"Full %d" % d) for d in range(DOCK_MIN, DOCK_MAX + 1))
    assert len(full) == SLOT

    def hdr_for(body, slots=(0, 1), **kw):
        m = manifest(body, **kw)
        return o.header(m, two_of_three(m, slots)), body

    def with_entries(*apps, **kw):
        return hdr_for(b"".join(apps), **kw)

    def one(k, **kw): return app(19, **kw) + app(20) if k == 0 else app(19) + app(20, **kw)

    rows = []

    def add(name, hdr_body, want, mode=0):
        hdr, body = hdr_body
        rows.append((name, mode, hdr, body, want))

    add("two-of-three-0-1", hdr_for(good), (15, 3, 0))
    add("two-of-three-2-0", hdr_for(good, slots=(2, 0)), (15, 5, 0))
    add("three-signers", hdr_for(good, slots=(0, 1, 2)), (15, 7, 0))
    add("full-64-entries", hdr_for(full), (15, 3, 0))
    add("one-signer", hdr_for(good, slots=(0,)), (1, 1, 0))
    add("duplicate-signer", (o.header(man, two_of_three(man, (0, 0))), good), (1, 1, 0))
    # signatures made for another object type
    add("header-signed-under-image-context", (o.header(man, two_of_three(man, (0, 1), IMG_CTX)), good), (1, 0, 0))
    add("one-signer-under-image-context", (o.header(man, [o.entry(0, *sign(0, man, IMG_CTX)), o.entry(1, *sign(1, man))]), good), (1, 2, 0))
    img_man = manifest(good, magic=IMG_CTX)
    add("image-magic-signed-as-image", (o.header(img_man, two_of_three(img_man, (0, 1), IMG_CTX)), good), (2, 0, 0))
    add("image-magic-signed-as-catalog", (o.header(img_man, two_of_three(img_man)), good), (2, 0, 0))
    add("production-mode", hdr_for(good), (8, 0, 0), mode=1)
    # manifest and header structure
    add("manifest-tamper", (o.header(o.flip(man, 40), two_of_three(man)), good), (1, 0, 0))
    add("manifest-reserved", (o.header(o.flip(man, 28), two_of_three(man)), good), (5, 0, 0))
    add("layout-68", (o.header(man, two_of_three(man), layout=(68, 1)), good), (3, 0, 0))
    add("signature-count-five", (o.header(man, two_of_three(man), count=5), good), (3, 0, 0))
    # entry count and length (signed, so only the count/length rule refuses them)
    add("count-zero", hdr_for(b"", count=0, length=0), (3, 3, 0))
    sixty5 = b"".join(app(19 + (i % 64), b"X%d" % i, seed=i) for i in range(65))
    add("count-65", hdr_for(sixty5), (3, 3, 0))
    add("length-not-count-times-128", hdr_for(good, length=len(good) - 128), (3, 3, 0))
    add("version-zero", hdr_for(good, version=0), (4, 3, 0))
    # the body hash
    add("body-hash-tamper", (o.header(man, two_of_three(man)), o.flip(good, 130)), (7, 3, 0))
    add("body-last-byte-tamper", (o.header(man, two_of_three(man)), o.flip(good, len(good) - 1)), (7, 3, 0))
    add("body-hash-and-entry-bad", (o.header(man, two_of_three(man)), app(18) + good[ENT:]), (7, 3, 0))
    # entries (re-signed over a matching body hash, one defect each)
    add("duplicate-dock-id", with_entries(app(19), app(20), app(19, seed=9)), (16, 3, 2))
    add("dock-id-18", with_entries(app(19), app(18)), (16, 3, 1))
    add("dock-id-0", with_entries(app(0)), (16, 3, 1))
    add("dock-id-83", with_entries(app(DOCK_MAX), app(DOCK_MAX + 1)), (16, 3, 1))
    add("dock-id-2-pow-32-minus-1", with_entries(app(0xffffffff)), (16, 3, 1))
    add("bad-title-non-ascii", with_entries(app(19), app(20, title=b"Zu\xc3\xa9")), (16, 3, 8))
    add("bad-title-unterminated", with_entries(app(19, title=b"A" * 32)), (16, 3, 8))
    add("bad-title-empty", with_entries(app(19, title=bytes(32))), (16, 3, 8))
    add("bad-title-junk-after-nul", with_entries(app(19, title=b"Ab\0C" + bytes(28))), (16, 3, 8))
    add("bad-title-control", with_entries(app(19, title=b"A\x07b")), (16, 3, 8))
    add("bad-title-del", with_entries(app(19, title=b"A\x7fb")), (16, 3, 8))
    add("title-31-chars-ok", with_entries(app(19, title=b"T" * 31)), (15, 3, 0))
    add("reserved-first", with_entries(app(19), app(20, reserved=b"\1" + bytes(15))), (16, 3, 4))
    add("reserved-last", with_entries(app(19, reserved=bytes(15) + b"\x80")), (16, 3, 4))
    add("manifest-cid-is-a-string", with_entries(app(19, mcid=b"bafkreihdwdcefgh4dqkjv67uzcmw7ojee6x")), (16, 3, 16))
    add("bundle-cid-bad-codec", with_entries(app(19, bcid=bytes([1, 0x99, 0x12, 0x20]) + bytes(32))), (16, 3, 16))
    add("bundle-cid-bad-hash-code", with_entries(app(19, bcid=bytes([1, 0x55, 0x13, 0x20]) + bytes(32))), (16, 3, 16))
    add("bundle-cid-version-0", with_entries(app(19, bcid=bytes([0, 0x55, 0x12, 0x20]) + bytes(32))), (16, 3, 16))
    add("size-zero", with_entries(app(19, size=0)), (16, 3, 32))
    add("size-too-big", with_entries(app(19, size=SIZE_MAX + 1)), (16, 3, 32))
    add("size-max-ok", with_entries(app(19, size=SIZE_MAX)), (15, 3, 0))
    add("several-defects-or-together", with_entries(app(18, title=b"\xff" + bytes(31), reserved=b"\1" + bytes(15), size=0)), (16, 3, 1 | 4 | 8 | 32))

    out = []
    for name, mode, hdr, body, want in rows:
        assert len(hdr) == o.HDR, name
        got = verdict(hdr, body, mode)
        assert got == want, (name, got, want)
        out.append(dict(name=name, mode=mode, hdr=hdr, body=body[:SLOT].ljust(SLOT, b"\0"), code=want[0], mask=want[1], flags=want[2]))
    assert len(out) <= 64
    return out


def fw_file(chosen=None):
    out = cases() if chosen is None else [c for c in cases() if c["name"] in chosen]
    return bytes([len(out)]) + b"".join(bytes([c["mode"]]) + c["hdr"] + c["body"] for c in out), out


if __name__ == "__main__":
    blob, out = fw_file()
    print(len(blob), [(c["name"], c["code"], c["mask"], c["flags"]) for c in out])
