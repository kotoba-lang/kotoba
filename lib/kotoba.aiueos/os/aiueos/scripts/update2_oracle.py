#!/usr/bin/env python3
"""Host oracle for the AIUEIMG2 path of native/update.kotoba (JUN-813 stage 5b, ADR-0286 amendment 2).

Builds the fw_cfg file opt/aiueos/update2 the QEMU gate hands to the guest: [count][per case: mode (0 = pinned TEST keys, 1 =
production signer set), 16384 header bytes, 5000 image bytes], and the verdict the kernel must reach for each case. Keys, signing and
the admission rule come from imgsig_oracle (public TEST keys; RFC 8032 integer Ed25519 and the ACVP-checked ML-DSA-65 reference). The
verdict here is computed independently of the kernel: header structure, then the counted signers (imgsig_oracle.verdict), then the
manifest's size and version, then the SHA-256 of the image bytes that follow.

Result codes of update.kotoba: 15 image verified, 1 fewer than two distinct valid signers, 2 bad magic, 3 count/layout or size,
4 version below 1, 5 manifest reserved bytes not zero, 7 digest differs, 8 no production signer set pinned.
"""
import hashlib
import struct

import imgsig_oracle as o

IMG_LEN = 5000


def image():
    """The same 5000-byte fixture image as update.kotoba's AIUEIMG1 self-test: byte i = (31 i + 7 (i >> 8) + 1) mod 256."""
    return bytes((31 * i + 7 * (i >> 8) + 1) & 255 for i in range(IMG_LEN))


def manifest(version=5, size=IMG_LEN, img=None, **kw):
    m = o.manifest(version=version, size=size, **kw)
    return m[:32] + hashlib.sha256(image() if img is None else img).digest()


def expected(hdr, mode, img):
    """(result, mask) the kernel must report for this case."""
    v, mask = o.verdict(hdr)
    if v in (2, 5, 3):
        return v, 0
    if mode == 1:
        return 8, 0
    if v == 4:
        return 1, mask
    version, size = struct.unpack_from("<QQ", hdr, 8)
    if not 1 <= size <= 33554432:
        return 3, mask
    if version < 1:
        return 4, mask
    return (15 if hashlib.sha256(img).digest() == hdr[32:64] and len(img) == size else 7), mask


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
