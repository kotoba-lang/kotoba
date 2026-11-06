#!/usr/bin/env python3
"""Host oracle for the AIUEIMG2 path of native/update.kotoba (JUN-813 stage 5b, ADR-0286 amendment 2).

Builds the fw_cfg file opt/aiueos/update2 the QEMU gate hands to the guest: [count][per case: mode (0 = pinned TEST keys, 1 =
production signer set, 2 = TEST keys with the header stream broken before the piece that would pass byte 7200), 16384 header
bytes, 5000 image bytes], and the verdict the kernel must reach for each case. Keys, signing and
the admission rule come from imgsig_oracle (public TEST keys; RFC 8032 integer Ed25519 and the ACVP-checked ML-DSA-65 reference). The
verdict here is computed independently of the kernel: header structure, then the counted signers (imgsig_oracle.verdict), then the
manifest's size and version, then the SHA-256 of the image bytes that follow.

JUN-813 stage 5c (ADR-0286 amendment 4): the guest reads a per-channel version FLOOR from its update journal (OSMETA.BIN, provisioned by
the gate with floor FLOOR = 4). An admitted header whose version is not strictly above it is refused with 9 before any image byte is taken, and an
unreadable journal is 10 (fail closed). The floor rule is applied here independently: it comes after the signers and the version >= 1 / size
checks and before the image digest. Cases with AIUEIMG1 headers (the 128-byte header, one Ed25519 signature under the RFC 8032 test-1 key, padded
with zeros to 16384 bytes so the case file keeps its shape) cover the other format.

Result codes of update.kotoba: 9 version not above the floor, 10 version floor unreadable, 21 stream broke (mode 2 only; the entries completed before the break still count), 15 image verified, 1 fewer than two distinct valid signers, 2 bad magic, 3 count/layout or size,
4 version below 1, 5 manifest reserved bytes not zero, 7 digest differs, 8 no production signer set pinned.
"""
import hashlib
import struct

import imgsig_oracle as o

IMG_LEN = 5000
FLOOR = 4  # the floor the gate provisions into OSMETA.BIN (update.kotoba hook request 4)


def image():
    """The same 5000-byte fixture image as update.kotoba's AIUEIMG1 self-test: byte i = (31 i + 7 (i >> 8) + 1) mod 256."""
    return bytes((31 * i + 7 * (i >> 8) + 1) & 255 for i in range(IMG_LEN))


def manifest(version=5, size=IMG_LEN, img=None, **kw):
    m = o.manifest(version=version, size=size, **kw)
    return m[:32] + hashlib.sha256(image() if img is None else img).digest()


CUT = 7200  # mode 2: the stream breaks before the piece that would pass this byte; pieces end on 1 KiB lines


def entry_counts(hdr, i):
    """Independent check of entry i of a header: does it count (pinned id, zero reserved/padding, both signatures valid)?"""
    e = hdr[128 + i * o.ENTRY:128 + (i + 1) * o.ENTRY]
    kid = struct.unpack_from("<I", e, 0)[0]
    return (kid < o.N_SLOTS and e[4:8] == bytes(4) and e[3381:] == bytes(11)
            and o.ed_valid(kid, hdr[:64], e[8:72]) and o.ml_valid(kid, hdr[:64], e[72:3381])), kid


def expected(hdr, mode, img, floor=FLOOR):
    """(result, mask) the kernel must report for this case."""
    if hdr[:8] == b"AIUEIMG1":
        return expected_v1(hdr, mode, img, floor)
    v, mask = o.verdict(hdr)
    if v in (2, 5, 3):
        return v, 0
    if mode == 2:
        # entries whose last byte lies below the last whole piece consumed before the break
        consumed, mask2, seen = (CUT // 1024) * 1024, 0, set()
        for i in range(struct.unpack_from("<I", hdr, 64)[0]):
            if 128 + (i + 1) * o.ENTRY <= consumed:
                ok, kid = entry_counts(hdr, i)
                if ok and kid not in seen:
                    seen.add(kid); mask2 |= 1 << kid
        return 21, mask2
    if mode == 1:
        return 8, 0
    if v == 4:
        return 1, mask
    version, size = struct.unpack_from("<QQ", hdr, 8)
    if not 1 <= size <= 33554432:
        return 3, mask
    if version < 1:
        return 4, mask
    if version <= floor:
        return 9, mask
    return (15 if hashlib.sha256(img).digest() == hdr[32:64] and len(img) == size else 7), mask


def v1_header(version):
    """An AIUEIMG1 header (manifest 64 + Ed25519 signature 64 under the RFC 8032 test-1 seed), padded to the case file's 16384 bytes."""
    man = manifest(version=version, magic=b"AIUEIMG1")
    return (man + o.ed_sign(o.ED_SEEDS[0], man)[1]).ljust(o.HDR, b"\0")


def expected_v1(hdr, mode, img, floor):
    """AIUEIMG1: signature (1), magic (2), reserved (5), size (3), version >= 1 (4), then the floor (9), then the digest. Counted mask is 0."""
    version, size = struct.unpack_from("<QQ", hdr, 8)
    if not (1 <= size <= 33554432):
        return 3, 0
    if version < 1:
        return 4, 0
    if version <= floor:
        return 9, 0
    return (15 if hashlib.sha256(img).digest() == hdr[32:64] and len(img) == size else 7), 0


def cases():
    man = manifest()
    sg = {s: o.sign_entry(s, man) for s in range(o.N_SLOTS)}
    e = lambda s: o.entry(s, *sg[s])
    img = image()
    bad_img = o.flip(img, 4097)
    man0 = manifest(version=0)
    sg0 = {s: o.sign_entry(s, man0) for s in range(2)}
    big = manifest(size=40 << 20)
    sgb = {s: o.sign_entry(s, big) for s in range(2)}
    bad_ctx = o.sign_entry(0, man, b"AIUEIMG1")
    cat_sg = {s: o.sign_entry(s, man, b"AIUECAT1") for s in range(2)}
    man6, man4, man3 = manifest(version=6), manifest(version=4), manifest(version=3)
    sg6, sg4, sg3 = ({s: o.sign_entry(s, m) for s in range(2)} for m in (man6, man4, man3))
    rows = [
        ("two-of-three-0-1", 0, o.header(man, [e(0), e(1)]), img),
        ("two-of-three-2-0", 0, o.header(man, [e(2), e(0)]), img),
        ("three-signers", 0, o.header(man, [e(0), e(1), e(2)]), img),
        ("one-signer", 0, o.header(man, [e(0)]), img),
        ("ml-half-bad", 0, o.header(man, [o.entry(0, sg[0][0], o.flip(sg[0][1], 100, 0x10)), e(1)]), img),
        ("ed-half-bad", 0, o.header(man, [o.entry(0, o.flip(sg[0][0], 5), sg[0][1]), e(1)]), img),
        ("tampered-image", 0, o.header(man, [e(0), e(1)]), bad_img),
        ("tampered-manifest", 0, o.header(o.flip(man, 40), [e(0), e(1)]), img),
        ("duplicate-id", 0, o.header(man, [e(0), e(0)]), img),
        ("unknown-id", 0, o.header(man, [o.entry(7, *sg[0]), e(0)]), img),
        ("production-mode", 1, o.header(man, [e(0), e(1)]), img),
        ("bad-magic", 0, o.header(o.flip(man, 0), [e(0), e(1)]), img),
        ("count-zero", 0, o.header(man, [e(0), e(1)], count=0), img),
        ("manifest-reserved", 0, o.header(o.flip(man, 24), [e(0), e(1)]), img),
        ("version-zero", 0, o.header(man0, [o.entry(s, *sg0[s]) for s in range(2)]), img),
        ("size-too-big", 0, o.header(big, [o.entry(s, *sgb[s]) for s in range(2)]), img),
        # review hardening (JUN-813): every must-be-zero byte group, counts 4 and 5, key ids with a high byte, the wrong context
        ("entry-reserved-4", 0, o.header(man, [o.entry(0, *sg[0], reserved=b"\1\0\0\0"), e(1)]), img),
        ("entry-reserved-7", 0, o.header(man, [o.entry(0, *sg[0], reserved=b"\0\0\0\x80"), e(1)]), img),
        ("pad-nonzero-first", 0, o.header(man, [o.entry(0, *sg[0], pad=b"\1" + bytes(10)), e(1)]), img),
        ("pad-nonzero-last", 0, o.header(man, [o.entry(0, *sg[0], pad=bytes(10) + b"\x80"), e(1)]), img),
        ("layout-68", 0, o.header(man, [e(0), e(1)], layout=(68, 1)), img),
        ("layout-127", 0, o.header(man, [e(0), e(1)], layout=(127, 0x80)), img),
        ("count-five", 0, o.header(man, [e(0), e(1)], count=5), img),
        ("count-four-dup", 0, o.header(man, [e(0), e(1), e(2), e(1)]), img),
        ("count-four-last-counts", 0, o.header(man, [e(0), o.entry(7, *sg[1]), e(0), e(1)]), img),
        ("id-256", 0, o.header(man, [o.entry(256, *sg[0]), e(1)]), img),
        ("id-65536", 0, o.header(man, [o.entry(65536, *sg[0]), e(1)]), img),
        ("id-16777216", 0, o.header(man, [o.entry(0x01000000, *sg[0]), e(1)]), img),
        ("wrong-context", 0, o.header(man, [o.entry(0, sg[0][0], bad_ctx[1]), e(1)]), img),
        # JUN-813 stage 5c: the version floor (FLOOR = 4). Version 5 above is every case above; these are the boundary and AIUEIMG1.
        ("floor-above", 0, o.header(man6, [o.entry(s, *sg6[s]) for s in range(2)]), img),
        ("floor-equal", 0, o.header(man4, [o.entry(s, *sg4[s]) for s in range(2)]), img),
        ("floor-below", 0, o.header(man3, [o.entry(s, *sg3[s]) for s in range(2)]), img),
        ("v1-above-floor", 0, v1_header(5), img),
        ("v1-equal-floor", 0, v1_header(FLOOR), img),
        ("v1-below-floor", 0, v1_header(FLOOR - 1), img),
        # JUN-813 stage 6: signatures made for another object type (ML-DSA context "AIUECAT1", the catalog's) must not admit an image
        ("catalog-context-both", 0, o.header(man, [o.entry(s, *cat_sg[s]) for s in range(2)]), img),
        ("catalog-context-one", 0, o.header(man, [o.entry(0, sg[0][0], cat_sg[0][1]), e(1)]), img),
        # last: the stream breaks after entries 0 and 1 were verified; the storage driver must still work afterwards (JUN-813 finding B)
        ("stream-broken-after-verify", 2, o.header(man, [e(0), e(1), e(2)]), img),
    ]
    out = []
    for name, mode, hdr, im in rows:
        assert len(hdr) == o.HDR and len(im) == IMG_LEN
        res, mask = expected(hdr, mode, im)
        out.append(dict(name=name, mode=mode, hdr=hdr, img=im, code=res, mask=mask))
    return out


def fw_file(chosen=None):
    out = cases() if chosen is None else [c for c in cases() if c["name"] in chosen]
    return bytes([len(out)]) + b"".join(bytes([c["mode"]]) + c["hdr"] + c["img"] for c in out), out


if __name__ == "__main__":
    blob, out = fw_file()
    print(len(blob), [(c["name"], c["code"], c["mask"]) for c in out])
