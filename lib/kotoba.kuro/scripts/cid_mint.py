#!/usr/bin/env python3
"""Independent CIDv1 / raw (0x55) / sha2-256 mint, multibase base32-lower no-pad.

The README's `kuro.host.opfs` section claims the CID math is parity-locked
against "an independent Python mint." This is that mint — written fresh from
the multihash / multibase / CIDv1 specs (not ported from `kuro.host.cid`), so
the two implementations can disagree independently. It exists so the claim is
a claim that *runs*, not a claim nobody checks.

Algorithm pinned by `test/kuro/host/opfs_test.cljk` (#cid-py-mint): for the
same bytes, this must print exactly what `kuro.host.cid/sha256-raw-cid`
produces. CIDv1 + raw codec 0x55 + sha2-256 (multihash 0x12, length 0x20),
36 bytes header+digest, multicodec prefix renders as the `bafkrei` that IPFS
`ipfs add --raw-leaves` gives.

Usage:
    python3 scripts/cid_mint.py hello
    python3 scripts/cid_mint.py 104:101:108:108:111   # bytes, colon-separated
"""
import hashlib
import sys

B32 = "abcdefghijklmnopqrstuvwxyz234567"


def base32_lower_no_pad(data: bytes) -> str:
    """CIDv1 base32-lower (multibase 'b'), no padding.

    Drain bytes MSB-first into 5-bit groups; the final partial group is
    left-padded with trailing zero bits — the same rule a base32 RFC 4648,
    no-pad, lower encoder uses. Ported independently from the spec text, not
    from `kuro.host.cid`.
    """
    bits = 0
    acc = 0
    out = []
    for b in data:
        acc = (acc << 8) | b
        bits += 8
        while bits >= 5:
            bits -= 5
            out.append(B32[(acc >> bits) & 0x1F])
    if bits:
        out.append(B32[(acc << (5 - bits)) & 0x1F])
    return "".join(out)


def sha256_raw_cid(data: bytes) -> str:
    """CIDv1 / raw / sha2-256 of `data`, multibase base32-lower-no-pad."""
    digest = hashlib.sha256(data).digest()
    header = bytes([0x01, 0x55, 0x12, 0x20])
    return "b" + base32_lower_no_pad(header + digest)


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "hello"
    if ":" in arg:
        data = bytes(int(x, 10) for x in arg.split(":"))
    else:
        data = arg.encode("utf-8")
    print(sha256_raw_cid(data))


if __name__ == "__main__":
    main()