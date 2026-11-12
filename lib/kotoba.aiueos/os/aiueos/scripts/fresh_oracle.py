#!/usr/bin/env python3
"""Host oracle for the AIUEFRS1 freshness-record admission and the RTC decoder of native/update.kotoba (JUN-813, ADR-0286 amendment 6).

Builds the fw_cfg files the QEMU gate hands to the guest and the verdict the kernel must reach, independently of the kernel:
  opt/aiueos/fresh  [count][per case: mode (0 = pinned TEST keys, 1 = production signer set), 16384 header bytes]
  opt/aiueos/clock  [n][n rows of 8 bytes: seconds, minutes, hours, day, month, year, century, register B]   (the RTC decoder)
Keys, signing and the Ed25519 / ML-DSA-65 references come from imgsig_oracle (public TEST keys; RFC 8032 integer Ed25519, ACVP-checked
ML-DSA-65 reference). The verdict is computed here from the byte layout of ADR-0286 amendment 6, never copied from the kernel; every case
also states the verdict it was MEANT to produce, and the oracle refuses to build when the two differ.

Layout (amendment 6). Header: the AIUEIMG2 signature block (16384 bytes): manifest 0..63, signature count u32 at 64 (1..4), 68..127 zero, up to
four 3392-byte entries from 128 (key id u32, 4 zero, Ed25519 64, ML-DSA-65 3309, 11 zero), the tail ignored. There is no body.
Manifest (64 bytes, signed): 0 "AIUEFRS1", 8 latest version u64 (1..2^63-1), 16 issued-at u64 (UTC seconds), 24 valid-until u64, 32 channel
u32 (1 = the update image channel), 36..63 zero. Both signatures cover the manifest; the ML-DSA message is M' = 0 || 8 || "AIUEFRS1" || manifest.
Structure: 1 <= issued-at < 2^63, issued-at < valid-until < 2^63, valid-until - issued-at <= 30 days (2592000 s), channel = 1.
Result codes of update.kotoba (word 180): 15 record verified; 1 fewer than two distinct valid signers; 2 bad magic (including the image and
catalog magics); 3 signature count / layout bytes, or the structure above; 4 version below 1; 5 manifest reserved bytes 36..63 not zero; 8 retired
(no production signer set pinned until amendment 7). Freshness verdict (word 273, only when the result is 15), against the RTC reading `now`: 1 fresh
(issued-at <= now + 86400 and now <= valid-until), 2 expired (now > valid-until), 3 the clock is more than a day behind issued-at
(issued-at > now + 86400), 4 no usable clock. The case word is result | counted mask << 8 | verdict << 16.
"""
import calendar
import datetime
import hashlib
import struct

import imgsig_oracle as o

ref = o.ref
CTX = b"AIUEFRS1"
MAGIC = CTX
DAY = 86400
LIFETIME_MAX = 30 * DAY
SKEW = DAY
TOP = 1 << 63
BUILD_FLOOR = calendar.timegm((2026, 11, 6, 0, 0, 0))   # update.kotoba's rtc-now refuses anything earlier
_SIGS = {}


def sign(slot, man, ctx=CTX):
    key = (slot, man, ctx)
    if key not in _SIGS:
        _SIGS[key] = o.sign_entry(slot, man, ctx)
    return _SIGS[key]


def manifest(version=7, issued=0, until=0, chan=1, magic=MAGIC, reserved=bytes(28)):
    m = magic + struct.pack("<QQQI", version, issued, until, chan) + reserved
    assert len(m) == 64
    return m


def two_of_three(man, slots=(0, 1), ctx=CTX):
    return [o.entry(s, *sign(s, man, ctx)) for s in slots]


def ml_valid(slot, man, sig, ks="test"):
    return o.ml_valid(slot, man, sig, ks, CTX)


def counted(hdr, ks="test"):
    """Mask of the pinned slots whose entry counts: pinned id not seen, zero reserved/padding, Ed25519 and ML-DSA-65 valid."""
    man, seen, mask = hdr[:64], set(), 0
    for i in range(struct.unpack_from("<I", hdr, 64)[0]):
        e = hdr[128 + i * o.ENTRY:128 + (i + 1) * o.ENTRY]
        kid = struct.unpack_from("<I", e, 0)[0]
        if kid >= o.N_SLOTS or kid in seen or e[4:8] != bytes(4) or e[3381:] != bytes(11):
            continue
        if o.ed_valid(kid, man, e[8:72], ks) and ml_valid(kid, man, e[72:3381], ks):
            seen.add(kid); mask |= 1 << kid
    return mask


def state(issued, until, now):
    """Freshness verdict for a clock reading `now` (None: no usable clock)."""
    if now is None:
        return 4
    if issued > now + SKEW:
        return 3
    return 2 if now > until else 1


def verdict(hdr, mode, now):
    """(result, counted mask, freshness verdict) for a clock reading `now`."""
    if hdr[:8] != MAGIC:
        return 2, 0, 0
    if hdr[36:64] != bytes(28):
        return 5, 0, 0
    sigs = struct.unpack_from("<I", hdr, 64)[0]
    if not 1 <= sigs <= 4 or hdr[68:128] != bytes(60):
        return 3, 0, 0
    mask = counted(hdr, "prod" if mode == 1 else "test")   # mode 1: the production signer set's PUBLIC keys (amendment 7)
    if bin(mask).count("1") < 2:
        return 1, mask, 0
    version, issued, until, chan = struct.unpack_from("<QQQI", hdr, 8)
    if not (1 <= issued < TOP and issued < until < TOP and until - issued <= LIFETIME_MAX and chan == 1):
        return 3, mask, 0
    if not 1 <= version < TOP:
        return 4, mask, 0
    return 15, mask, state(issued, until, now)


def rows(base):
    """The cases for a gate whose QEMU RTC starts at `base` (unix seconds) and is read at most WINDOW seconds later: the verdict of every case
    must be the same for every clock reading in [base, base + WINDOW]; a case whose verdict depends on where in the window the reading falls is a
    bug of the case list, and `cases` refuses to build it."""
    b = base
    out = []

    def add(name, hdr, want, mode=0):
        out.append((name, mode, hdr, want))

    def good(version=7, issued=b - 10 * DAY, until=b + 20 * DAY, **kw):
        m = manifest(version, issued, until, **kw)
        return m, o.header(m, two_of_three(m))

    m, h = good()
    add("two-of-three-0-1", h, (15, 3, 1))
    m23 = manifest(7, b - 10 * DAY, b + 20 * DAY)
    add("two-of-three-2-0", o.header(m23, two_of_three(m23, (2, 0))), (15, 5, 1))
    add("three-signers", o.header(m23, two_of_three(m23, (0, 1, 2))), (15, 7, 1))
    # the clock decides
    me = manifest(7, b - 30 * DAY - 3600, b - 3600)
    add("expired-one-hour-ago-30-day-lifetime", o.header(me, two_of_three(me)), (15, 3, 2))
    me = manifest(7, b - 90 * DAY, b - 60 * DAY)
    add("expired-two-months-ago", o.header(me, two_of_three(me)), (15, 3, 2))
    me = manifest(7, b - DAY, b + 3 * 3600)
    add("fresh-three-hours-left", o.header(me, two_of_three(me)), (15, 3, 1))
    me = manifest(7, b + 23 * 3600, b + 23 * 3600 + 10 * DAY)
    add("issued-23-hours-ahead-within-skew", o.header(me, two_of_three(me)), (15, 3, 1))
    me = manifest(7, b + 2 * DAY, b + 12 * DAY)
    add("issued-two-days-ahead-clock-behind", o.header(me, two_of_three(me)), (15, 3, 3))
    me = manifest(7, b - DAY, b - DAY + LIFETIME_MAX)
    add("lifetime-exactly-30-days", o.header(me, two_of_three(me)), (15, 3, 1))
    me = manifest(1, b - DAY, b + DAY)
    add("version-one", o.header(me, two_of_three(me)), (15, 3, 1))
    me = manifest(TOP - 1, b - DAY, b + DAY)
    add("version-max-signed", o.header(me, two_of_three(me)), (15, 3, 1))
    # the manifest's structure (signed, so only the structure rule refuses them)
    for name, kw in (("lifetime-30-days-plus-1s", dict(issued=b - DAY, until=b - DAY + LIFETIME_MAX + 1)),
                     ("lifetime-zero", dict(issued=b - DAY, until=b - DAY)),
                     ("valid-until-before-issued", dict(issued=b, until=b - 1)),
                     ("issued-zero", dict(issued=0, until=b)),
                     ("issued-top-bit", dict(issued=TOP, until=TOP + 100)),
                     ("valid-until-top-bit", dict(issued=b, until=TOP + 100)),
                     ("channel-0", dict(issued=b - DAY, until=b + DAY, chan=0)),
                     ("channel-2", dict(issued=b - DAY, until=b + DAY, chan=2)),
                     ("channel-high-bit", dict(issued=b - DAY, until=b + DAY, chan=0x80000001))):
        mm = manifest(7, **kw)
        add(name, o.header(mm, two_of_three(mm)), (3, 3, 0))
    mv = manifest(0, b - DAY, b + DAY)
    add("version-zero", o.header(mv, two_of_three(mv)), (4, 3, 0))
    mv = manifest(TOP, b - DAY, b + DAY)
    add("version-top-bit", o.header(mv, two_of_three(mv)), (4, 3, 0))
    # signatures
    add("one-signer", o.header(m, two_of_three(m, (0,))), (1, 1, 0))
    add("duplicate-signer", o.header(m, two_of_three(m, (0, 0))), (1, 1, 0))
    add("unknown-id", o.header(m, [o.entry(7, *sign(0, m)), o.entry(0, *sign(0, m))]), (1, 1, 0))
    add("ml-half-bad", o.header(m, [o.entry(0, sign(0, m)[0], o.flip(sign(0, m)[1], 100, 0x10)), o.entry(1, *sign(1, m))]), (1, 2, 0))
    add("ed-half-bad", o.header(m, [o.entry(0, o.flip(sign(0, m)[0], 5), sign(0, m)[1]), o.entry(1, *sign(1, m))]), (1, 2, 0))
    add("pad-nonzero-first", o.header(m, [o.entry(0, *sign(0, m), pad=b"\1" + bytes(10)), o.entry(1, *sign(1, m))]), (1, 2, 0))
    add("manifest-tamper-after-signing", o.header(o.flip(m, 20), two_of_three(m)), (1, 0, 0))
    add("expiry-extended-after-signing", o.header(o.flip(m, 26), two_of_three(m)), (1, 0, 0))
    # signatures made for another object type must not admit a freshness record (ML-DSA context separation)
    add("header-signed-under-image-context", o.header(m, two_of_three(m, (0, 1), b"AIUEIMG2")), (1, 0, 0))
    add("header-signed-under-catalog-context", o.header(m, two_of_three(m, (0, 1), b"AIUECAT1")), (1, 0, 0))
    add("one-signer-under-image-context", o.header(m, [o.entry(0, *sign(0, m, b"AIUEIMG2")), o.entry(1, *sign(1, m))]), (1, 2, 0))
    # magics of the other kinds, structure of the header
    mi = manifest(7, b - 10 * DAY, b + 20 * DAY, magic=b"AIUEIMG2")
    add("image-magic-signed-as-image", o.header(mi, two_of_three(mi, (0, 1), b"AIUEIMG2")), (2, 0, 0))
    add("image-magic-signed-as-record", o.header(mi, two_of_three(mi)), (2, 0, 0))
    mc = manifest(7, b - 10 * DAY, b + 20 * DAY, magic=b"AIUECAT1")
    add("catalog-magic-signed-as-record", o.header(mc, two_of_three(mc)), (2, 0, 0))
    add("manifest-reserved-first", o.header(o.flip(m, 36), two_of_three(m)), (5, 0, 0))
    add("manifest-reserved-last", o.header(o.flip(m, 63, 0x80), two_of_three(m)), (5, 0, 0))
    add("layout-68", o.header(m, two_of_three(m), layout=(68, 1)), (3, 0, 0))
    add("signature-count-five", o.header(m, two_of_three(m), count=5), (3, 0, 0))
    add("signature-count-zero", o.header(m, two_of_three(m), count=0), (3, 0, 0))
    add("production-mode", o.header(m, two_of_three(m)), (1, 0, 0), mode=1)
    return out


WINDOW = 7200


def cases(base, clock=None):
    """Cases (signed relative to `base`) and their verdicts for an RTC that starts at `clock` (default: `base`) and is read at most WINDOW
    seconds later. clock = 'none': no usable clock (an RTC before the build floor)."""
    out = []
    for name, mode, hdr, want in rows(base):
        assert len(hdr) == o.HDR, name
        if clock == "none":
            got = verdict(hdr, mode, None)
        else:
            c0 = base if clock is None else clock
            got = verdict(hdr, mode, c0)
            late = verdict(hdr, mode, c0 + WINDOW)   # the reading may fall anywhere in [c0, c0 + WINDOW]
            assert late == got, ("verdict depends on the reading inside the window", name, got, late)
        if clock is None:
            assert got == want, (name, got, want)
        out.append(dict(name=name, mode=mode, hdr=hdr, code=got[0], mask=got[1], state=got[2]))
    assert len(out) <= 64
    return out


def fw_file(base, chosen=None, clock=None):
    out = cases(base, clock)
    if chosen is not None:
        out = [c for c in out if c["name"] in chosen]
    return bytes([len(out)]) + b"".join(bytes([c["mode"]]) + c["hdr"] for c in out), out


# ---- the RTC decoder, independent of the kernel (datetime, not the era algorithm) ---------------------------------------------------------
def rtc_unix(row):
    """row = (seconds, minutes, hours, day, month, year, century, register B) as read from the CMOS; the unix time or 0 when a field is invalid."""
    s, mi, h, d, mo, y, c, b = row
    binary, h24 = bool(b & 4), bool(b & 2)

    def dec(v):
        if binary:
            return v
        return (v >> 4) * 10 + (v & 15) if (v >> 4) <= 9 and (v & 15) <= 9 else None

    pm = bool(h & 0x80)
    parts = [dec(s), dec(mi), dec(h & 0x7f), dec(d), dec(mo), dec(y)]
    if None in parts:
        return 0
    s, mi, hr, d, mo, y = parts
    cc = dec(c)
    century = cc if cc is not None and 19 <= cc <= 21 else 20
    if h24:
        hour = hr
        if hour > 23:
            return 0
    else:
        if not 1 <= hr <= 12:
            return 0
        hour = hr % 12 + (12 if pm else 0)
    if s > 59 or mi > 59:
        return 0
    try:
        return int(datetime.datetime(century * 100 + y, mo, d, hour, mi, s, tzinfo=datetime.timezone.utc).timestamp())
    except ValueError:
        return 0


def bcd(v):
    return ((v // 10) << 4) | (v % 10)


def clock_rows():
    """Synthetic CMOS rows (and a name for each) that exercise the decoder: BCD / binary, 24 / 12 hour, centuries, leap days, invalid fields."""
    R = []

    def add(name, row):
        R.append((name, row))

    def row(s, mi, h, d, mo, y, c, b=0x02, *, enc=True):
        return (bcd(s) if enc and not b & 4 else s, bcd(mi) if enc and not b & 4 else mi, h, bcd(d) if enc and not b & 4 else d,
                bcd(mo) if enc and not b & 4 else mo, bcd(y) if enc and not b & 4 else y, c, b)

    add("bcd-24h-2026-11-06T12:34:56", row(56, 34, 0x12, 6, 11, 26, 0x20))
    add("binary-24h-2026-11-06T12:34:56", row(56, 34, 12, 6, 11, 26, 20, 0x06))
    add("bcd-12h-am-12", (0x00, 0x30, 0x12, 0x06, 0x11, 0x26, 0x20, 0x00))
    add("bcd-12h-pm-12", (0x00, 0x30, 0x92, 0x06, 0x11, 0x26, 0x20, 0x00))
    add("bcd-12h-pm-1", (0x00, 0x30, 0x81, 0x06, 0x11, 0x26, 0x20, 0x00))
    add("bcd-12h-pm-11", (0x59, 0x59, 0x91, 0x06, 0x11, 0x26, 0x20, 0x00))
    add("binary-12h-pm-12", (0, 30, 0x8c, 6, 11, 26, 20, 0x04))
    add("binary-12h-am-12", (0, 30, 12, 6, 11, 26, 20, 0x04))
    add("binary-12h-pm-1", (0, 30, 0x81, 6, 11, 26, 20, 0x04))
    add("leap-day-2028", row(50, 59, 0x23, 29, 2, 28, 0x20))
    add("leap-day-2000-century-400", row(0, 0, 0, 29, 2, 0, 0x20))
    add("not-leap-2026-02-29", row(0, 0, 0, 29, 2, 26, 0x20))
    add("not-leap-2100-02-29", row(0, 0, 0, 29, 2, 0, 0x21))
    add("2100-03-01", row(0, 0, 0, 1, 3, 0, 0x21))
    add("end-of-2099", row(59, 59, 0x23, 31, 12, 99, 0x20))
    add("2038-01-19T03:14:08", row(8, 14, 3, 19, 1, 38, 0x20))
    add("century-register-zero-assumes-20", row(0, 0, 0, 6, 11, 26, 0x00))
    add("century-register-ff-assumes-20", row(0, 0, 0, 6, 11, 26, 0xff))
    add("century-register-22-assumes-20", row(0, 0, 0, 6, 11, 26, 0x22))
    add("century-19", row(0, 0, 0, 31, 12, 99, 0x19))
    add("epoch-is-zero", row(0, 0, 0, 1, 1, 70, 0x19))
    add("sec-bcd-5a", (0x5a, 0x00, 0x00, 0x06, 0x11, 0x26, 0x20, 0x02))
    add("sec-binary-90", (90, 0, 0, 6, 11, 26, 20, 0x06))
    add("sec-60", (0x60, 0x00, 0x00, 0x06, 0x11, 0x26, 0x20, 0x02))
    add("min-60", (0x00, 0x60, 0x00, 0x06, 0x11, 0x26, 0x20, 0x02))
    add("hour-24-in-24h", (0x00, 0x00, 0x24, 0x06, 0x11, 0x26, 0x20, 0x02))
    add("hour-0-in-12h", (0x00, 0x00, 0x00, 0x06, 0x11, 0x26, 0x20, 0x00))
    add("hour-13-in-12h", (0x00, 0x00, 0x13, 0x06, 0x11, 0x26, 0x20, 0x00))
    add("month-0", (0x00, 0x00, 0x00, 0x06, 0x00, 0x26, 0x20, 0x02))
    add("month-13", (0x00, 0x00, 0x00, 0x06, 0x13, 0x26, 0x20, 0x02))
    add("day-0", (0x00, 0x00, 0x00, 0x00, 0x11, 0x26, 0x20, 0x02))
    add("day-31-in-november", (0x00, 0x00, 0x00, 0x31, 0x11, 0x26, 0x20, 0x02))
    add("all-ff-dead-rtc", (0xff,) * 8)
    add("all-zero", (0,) * 8)
    return R


def clock_fw_file():
    rs = clock_rows()
    assert len(rs) <= 40
    return bytes([len(rs)]) + b"".join(bytes(r) for _n, r in rs), [(n, r, rtc_unix(r)) for n, r in rs]


if __name__ == "__main__":
    base = calendar.timegm((2026, 11, 6, 12, 0, 0))
    blob, out = fw_file(base)
    print(len(blob), [(c["name"], c["code"], c["mask"], c["state"]) for c in out])
    _b, rows_ = clock_fw_file()
    print([(n, u) for n, _r, u in rows_])
