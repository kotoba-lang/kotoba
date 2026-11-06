#!/usr/bin/env python3
"""Host oracle for the production signer set gate (JUN-813, ADR-0286 amendment 7).

The kernel's production mode (test = 0) pins the three PUBLIC keys of fixtures/signers/prod-pubkeys.json (module aiueos.imgsig-prodkeys). The
private seeds are not in the repository, so CI cannot sign anything with them. This oracle therefore works from ONE set of golden fixtures that
were signed once with the real slots (fixtures/signers/golden/: an AIUEIMG2 header, an AIUECAT1 header and an AIUEFRS1 header, public data; the
image and the catalog body they cover are regenerated here from fixed rules, see `golden_inputs`) and derives every refused case from them on the
host by editing public bytes only (dropping an entry, flipping a byte, presenting one kind as another) or by signing with the public TEST keys.
Every verdict is computed from the independent references under the production PUBLIC keys: imgsig_oracle (RFC 8032 integer Ed25519 and the
ACVP-checked ML-DSA-65 reference), update2_oracle / cat_oracle / fresh_oracle (the admission rules of amendments 2, 4, 5 and 6); each case also
states the verdict it was MEANT to produce and the oracle refuses to build when the two differ.

Files for the QEMU guest (all in production mode, mode byte 1, unless the name says test mode, mode byte 0):
  opt/aiueos/update2  [count][per case: mode, 16384 header bytes, 5000 image bytes]            result word 236 + k / 2, two cases per word
  opt/aiueos/cat1     [count][per case: mode, 16384 header bytes, 8192 body bytes]              result word 300 + k
  opt/aiueos/fresh    [count][per case: mode, 16384 header bytes]                               result word 400 + k
Result codes (update.kotoba): 15 verified, 1 fewer than two distinct valid signers (also: a header whose magic ends in '1' is judged by
the AIUEIMG1 branch of `admit`, whose signature check comes first), 2 bad magic, 7 digest differs. Freshness verdict 1 = fresh.
"""
import calendar
import hashlib
import json
import struct
import sys
from pathlib import Path

import cat_oracle as cat
import fresh_oracle as frs
import imgsig_oracle as o
import update2_oracle as upd

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parent / "fixtures" / "signers" / "golden"
FILES = {"image": "aiueimg2.header", "catalog": "aiuecat1.header", "fresh": "aiuefrs1.header"}
SLOTS = {"image": (0, 1), "catalog": (1, 2), "fresh": (0, 2)}   # which two slots signed each golden fixture
IMAGE_VERSION, CATALOG_VERSION, FRESH_VERSION = 5, 7, 7        # the update2 gates provision a version floor of 4
FRESH_ISSUED = calendar.timegm((2026, 11, 6, 0, 0, 0))         # 2026-11-06T00:00:00Z, the kernel's clock build floor
FRESH_UNTIL = FRESH_ISSUED + 30 * 86400
CLOCK_BASE = calendar.timegm((2026, 11, 6, 12, 0, 0))         # the QEMU RTC of the gate: inside the record's validity
TEST_SLOTS = (0, 1)


def golden_inputs():
    """The image, the catalog body and the freshness parameters the golden headers cover (fixed rules, no secret)."""
    body = b"".join(cat.app(d, b"App %d" % d) for d in (19, 20, cat.DOCK_MAX))
    return dict(image=upd.image(), catalog=body,
                fresh=dict(version=FRESH_VERSION, issued=FRESH_ISSUED, until=FRESH_UNTIL, chan=1))


def golden_manifests():
    g = golden_inputs()
    return dict(image=upd.manifest(version=IMAGE_VERSION),
                catalog=cat.manifest(g["catalog"], version=CATALOG_VERSION),
                fresh=frs.manifest(FRESH_VERSION, FRESH_ISSUED, FRESH_UNTIL, 1))


def golden_header(kind):
    raw = (GOLDEN / FILES[kind]).read_bytes()
    assert len(raw) == 128 + 2 * o.ENTRY, (kind, len(raw))      # stored without the zero tail of the 16384-byte header
    return raw.ljust(o.HDR, b"\0")


# ---- header edits that need no key -----------------------------------------------------------------------------------------------
def entries_of(hdr):
    n = struct.unpack_from("<I", hdr, 64)[0]
    return [hdr[128 + i * o.ENTRY:128 + (i + 1) * o.ENTRY] for i in range(n)]


def one_signer(hdr):
    return o.header(hdr[:64], entries_of(hdr)[:1])


def test_signed(kind, man):
    """The same manifest signed by two TEST slots (public test seeds): what production mode must not accept."""
    ctx = {"image": b"AIUEIMG2", "catalog": b"AIUECAT1", "fresh": b"AIUEFRS1"}[kind]
    return o.header(man, [o.entry(s, *o.sign_entry(s, man, ctx)) for s in TEST_SLOTS])


def img_pad(b, n):
    return b.ljust(n, b"\0")


AIUEIMG1_SOURCE = HERE.parent / "native" / "update.kotoba"


def aiueimg1_key(mode):
    """The single Ed25519 key of the AIUEIMG1 branch, read as DATA from update.kotoba's key tables (not logic): mode 0 the RFC 8032 test-1 key
    (`test-key-byte`), mode 1 the production one (`key-byte`). `admit` dispatches on header byte 7 alone: anything that is not '2' goes down this branch."""
    import re
    src = AIUEIMG1_SOURCE.read_text()
    name = "(defn test-key-byte [i]" if mode == 0 else "(defn key-byte [i]"
    row = src[src.index(name):].split("\n", 2)[1 if mode == 0 else 1]
    words = [int(w) for w in re.search(r"\(case \(quot i 4\) (.*?) 0\)", row).group(1).split()[1::2]]
    assert len(words) == 8, words
    return b"".join(struct.pack("<I", w) for w in words)


def image_expected(hdr, mode, img):
    """upd.expected, plus the dispatch of `admit` on byte 7: a header whose byte 7 is not '2' (an AIUECAT1 or AIUEFRS1 header, magics ending in '1')
    is judged as AIUEIMG1 (Ed25519 over the first 64 bytes, signature at 64..127, signature checked FIRST): refused with 1 unless that signature verifies
    under the AIUEIMG1 key, which for these headers it cannot (bytes 64..127 are a count and zeros)."""
    if hdr[7:8] != b"2":
        if not o.edr.ed_verify(aiueimg1_key(mode), hdr[:64], hdr[64:128]):
            return 1, 0
        raise AssertionError("an AIUEIMG1-dispatched header with a valid signature is outside this oracle")
    return upd.expected(hdr, mode, img)


# ---- cases -------------------------------------------------------------------------------------------------------------------------
def image_cases():
    g = golden_inputs()
    img, man = g["image"], golden_manifests()["image"]
    gi, gc, gf = golden_header("image"), golden_header("catalog"), golden_header("fresh")
    ml0 = 128 + 72 + 100            # inside entry 0's ML-DSA-65 signature
    ed1 = 128 + o.ENTRY + 8 + 5     # inside entry 1's Ed25519 signature
    rows = [
        # name, mode, header, image, meant (result, counted mask)
        ("golden-image-production", 1, gi, img, (15, 3)),
        ("image-one-signer", 1, one_signer(gi), img, (1, 1)),
        ("image-test-keys-header", 1, test_signed("image", man), img, (1, 0)),
        ("image-flipped-ml-signature-byte", 1, o.flip(gi, ml0, 0x10), img, (1, 2)),
        ("image-flipped-ed-signature-byte", 1, o.flip(gi, ed1), img, (1, 1)),
        ("image-flipped-manifest-byte", 1, o.flip(gi, 40), img, (1, 0)),
        ("image-flipped-image-byte", 1, gi, o.flip(img, 4097), (7, 3)),
        ("catalog-presented-as-image", 1, gc, img, (1, 0)),
        ("freshness-presented-as-image", 1, gf, img, (1, 0)),
        ("golden-image-under-test-keys", 0, gi, img, (1, 0)),
        ("test-keys-header-under-test-keys", 0, test_signed("image", man), img, (15, 3)),
    ]
    out = []
    for name, mode, hdr, im, want in rows:
        assert len(hdr) == o.HDR and len(im) == upd.IMG_LEN, name
        got = image_expected(hdr, mode, im)
        assert got == want, (name, got, want)
        out.append(dict(name=name, mode=mode, hdr=hdr, img=im, code=got[0], mask=got[1]))
    return out


def catalog_cases():
    g = golden_inputs()
    body, man = g["catalog"], golden_manifests()["catalog"]
    gi, gc, gf = golden_header("image"), golden_header("catalog"), golden_header("fresh")
    ml0 = 128 + 72 + 100
    rows = [
        ("golden-catalog-production", 1, gc, body, (15, 6, 0)),
        ("catalog-one-signer", 1, one_signer(gc), body, (1, 2, 0)),
        ("catalog-test-keys-header", 1, test_signed("catalog", man), body, (1, 0, 0)),
        ("catalog-flipped-ml-signature-byte", 1, o.flip(gc, ml0, 0x10), body, (1, 4, 0)),
        ("catalog-flipped-manifest-byte", 1, o.flip(gc, 40), body, (1, 0, 0)),
        ("catalog-flipped-body-byte", 1, gc, o.flip(body, 7), (7, 6, 0)),
        ("image-presented-as-catalog", 1, gi, body, (2, 0, 0)),
        ("freshness-presented-as-catalog", 1, gf, body, (2, 0, 0)),
        ("golden-catalog-under-test-keys", 0, gc, body, (1, 0, 0)),
        ("test-keys-header-under-test-keys", 0, test_signed("catalog", man), body, (15, 3, 0)),
    ]
    out = []
    for name, mode, hdr, bd, want in rows:
        assert len(hdr) == o.HDR, name
        got = cat.verdict(hdr, bd, mode)
        assert got == want, (name, got, want)
        out.append(dict(name=name, mode=mode, hdr=hdr, body=bd[:cat.SLOT].ljust(cat.SLOT, b"\0"), code=got[0], mask=got[1], flags=got[2]))
    return out


def fresh_cases():
    man = golden_manifests()["fresh"]
    gi, gc, gf = golden_header("image"), golden_header("catalog"), golden_header("fresh")
    ml0 = 128 + 72 + 100
    rows = [
        ("golden-freshness-production", 1, gf, (15, 5, 1)),
        ("freshness-one-signer", 1, one_signer(gf), (1, 1, 0)),
        ("freshness-test-keys-header", 1, test_signed("fresh", man), (1, 0, 0)),
        ("freshness-flipped-ml-signature-byte", 1, o.flip(gf, ml0, 0x10), (1, 4, 0)),
        ("freshness-flipped-expiry-byte", 1, o.flip(gf, 26), (1, 0, 0)),
        ("image-presented-as-freshness", 1, gi, (2, 0, 0)),
        ("catalog-presented-as-freshness", 1, gc, (2, 0, 0)),
        ("golden-freshness-under-test-keys", 0, gf, (1, 0, 0)),
        ("test-keys-header-under-test-keys", 0, test_signed("fresh", man), (15, 3, 1)),
    ]
    out = []
    for name, mode, hdr, want in rows:
        assert len(hdr) == o.HDR, name
        got = frs.verdict(hdr, mode, CLOCK_BASE)
        late = frs.verdict(hdr, mode, CLOCK_BASE + frs.WINDOW)
        assert got == late == want, (name, got, late, want)
        out.append(dict(name=name, mode=mode, hdr=hdr, code=got[0], mask=got[1], state=got[2]))
    return out


def fw_image(cs):
    return bytes([len(cs)]) + b"".join(bytes([c["mode"]]) + c["hdr"] + c["img"] for c in cs)


def fw_catalog(cs):
    return bytes([len(cs)]) + b"".join(bytes([c["mode"]]) + c["hdr"] + c["body"] for c in cs)


def fw_fresh(cs):
    return bytes([len(cs)]) + b"".join(bytes([c["mode"]]) + c["hdr"] for c in cs)


def golden_manifest_record():
    """The public record committed beside the golden headers: what each header covers and which slots signed it."""
    g, m = golden_inputs(), golden_manifests()
    rec = {}
    for kind in FILES:
        raw = (GOLDEN / FILES[kind]).read_bytes()
        rec[kind] = dict(file=FILES[kind], bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), slots=list(SLOTS[kind]),
                         manifestSha256=hashlib.sha256(m[kind]).hexdigest())
    rec["image"]["coversSha256"] = hashlib.sha256(g["image"]).hexdigest()
    rec["catalog"]["coversSha256"] = hashlib.sha256(g["catalog"]).hexdigest()
    return rec


if __name__ == "__main__":
    if sys.argv[1:2] == ["inputs"]:        # write the inputs the signer tool signs: oracle inputs OUTDIR
        out = Path(sys.argv[2])
        g = golden_inputs()
        (out / "golden-image.bin").write_bytes(g["image"])
        (out / "golden-catalog.body").write_bytes(g["catalog"])
        print(json.dumps(dict(imageVersion=IMAGE_VERSION, catalogVersion=CATALOG_VERSION, freshVersion=FRESH_VERSION,
                              issued=FRESH_ISSUED, validUntil=FRESH_UNTIL, slots=SLOTS)))
    else:
        for name, fn in (("update2", image_cases), ("cat1", catalog_cases), ("fresh", fresh_cases)):
            cs = fn()
            print(name, [(c["name"], c["code"], c["mask"]) for c in cs])
