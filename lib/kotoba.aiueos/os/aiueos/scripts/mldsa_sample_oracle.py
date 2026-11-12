#!/usr/bin/env python3
"""Host oracle for the kernel ML-DSA-65 sampling and packing module (aiueos.mldsa-sample, JUN-813 stage 3).

Written from FIPS 204: Algorithm 30 (RejNTTPoly), Algorithm 29 (SampleInBall, tau = 49), Algorithm 21 (HintBitUnpack for
omega = 55, k = 6), SimpleBitPack/SimpleBitUnpack and the BitUnpack offset. SHAKE comes from hashlib: it is the oracle, not the
kernel. The QEMU gate compares the guest's slots and byte ranges with these values.
"""
import hashlib

Q = 8380417


def rho():
    return bytes((i * 11 + 5) & 255 for i in range(32))


def ctilde():
    return bytes((i * 13 + 1) & 255 for i in range(48))


def source():
    return bytes((i * 37 + 11) & 255 for i in range(640))


def rej_ntt_poly(seed):
    """Algorithm 30 over a long SHAKE128 prefix (prefix-consistent), returns 256 coefficients."""
    buf = hashlib.shake_128(seed).digest(168 * 12)
    out, pos = [], 0
    while len(out) < 256:
        x = buf[pos] + 256 * buf[pos + 1] + 65536 * (buf[pos + 2] & 127)
        pos += 3
        if x < Q:
            out.append(x)
    return out


def expand_a(s, r):
    return rej_ntt_poly(rho() + bytes([s, r]))


def sample_in_ball(ct):
    buf = hashlib.shake_256(ct).digest(8 + 1024)
    signs = int.from_bytes(buf[:8], "little")
    c, pos = [0] * 256, 8
    for i in range(207, 256):
        while buf[pos] > i:
            pos += 1
        j = buf[pos]
        pos += 1
        c[i] = c[j]
        c[j] = 1 if (signs >> (i - 207)) & 1 == 0 else Q - 1
    return c


def hint_unpack(hb):
    """Algorithm 21: returns the 1536-bit list, or None when malformed."""
    h, idx = [0] * 1536, 0
    for i in range(6):
        lim = hb[55 + i]
        if lim < idx or lim > 55:
            return None
        first = idx
        while idx < lim:
            if idx > first and hb[idx - 1] >= hb[idx]:
                return None
            h[256 * i + hb[idx]] = 1
            idx += 1
    if any(hb[p] != 0 for p in range(idx, 55)):
        return None
    return h


def bitmap(h):
    out = bytearray(192)
    for n, bit in enumerate(h):
        if bit:
            out[n // 8] |= 1 << (n % 8)
    return bytes(out)


def unpack(data, bits):
    """SimpleBitUnpack of 256 values, little-endian bit order."""
    n = int.from_bytes(data[: 32 * bits], "little")
    return [(n >> (t * bits)) & ((1 << bits) - 1) for t in range(256)]


def pack(poly, bits):
    assert all(0 <= c < (1 << bits) for c in poly)
    n = 0
    for t, c in enumerate(poly):
        n |= c << (t * bits)
    return n.to_bytes(32 * bits, "little")


def rsub(poly, top):
    return [(top - c) % Q for c in poly]


def hint_cases():
    """(name, 61 hint bytes, expected bitmap or None)."""
    good = bytearray(61)
    for p, pos in enumerate([3, 9, 200, 7, 8, 255, 0, 100]):
        good[p] = pos
    good[55:61] = bytes([3, 3, 4, 6, 6, 8])  # rows: 3 | none | 1 | 2 | none | 2
    cases = [("valid", bytes(good))]
    bad_order = bytearray(good); bad_order[1] = 3          # row 0 not strictly increasing
    cases.append(("not-increasing", bytes(bad_order)))
    bad_pad = bytearray(good); bad_pad[20] = 1              # a non-zero byte after the last hint
    cases.append(("bad-padding", bytes(bad_pad)))
    bad_lim = bytearray(good); bad_lim[57] = 2              # a row limit below the previous one
    cases.append(("limit-decreases", bytes(bad_lim)))
    return [(n, hb, hint_unpack(hb)) for n, hb in cases]


def checksum(values):
    return sum(c * (i + 1) for i, c in enumerate(values))


def records():
    """The guest's records in order: (name, first 8 values, 40-bit checksum)."""
    src = source()
    a00, a54 = expand_a(0, 0), expand_a(4, 5)
    ball = sample_in_ball(ctilde())
    u10 = unpack(src, 10)
    u20 = unpack(src, 20)
    z = rsub(u20, 524288)
    u4 = unpack(src, 4)
    rows = [("expand-a-0-0", a00), ("expand-a-5-4", a54), ("sample-in-ball", ball), ("unpack10", u10), ("unpack20", u20),
            ("rsub20", z), ("unpack4", u4), ("pack4", list(pack(u4, 4))), ("pack10", list(pack(u10, 10)))]
    good = hint_cases()[0]
    rows.append(("hint-bitmap", list(bitmap(hint_unpack(good[1])))))
    return rows


if __name__ == "__main__":
    for name, vals in records():
        print(name, vals[:4], checksum(vals))
    for name, hb, h in hint_cases():
        print("hint", name, "ok" if h else "refused")
    ball = sample_in_ball(ctilde())
    assert sum(1 for c in ball if c) == 49 and all(c in (0, 1, Q - 1) for c in ball)
    assert pack(unpack(source(), 10), 10) == source()[:320] and pack(unpack(source(), 4), 4) == source()[:128]
