#!/usr/bin/env python3
"""Convert OpenSSL P-256 DER output to the bounded AIUEOS kernel ABI."""

import argparse
import pathlib


def der_length(blob, offset):
    if offset >= len(blob):
        raise ValueError("truncated DER length")
    first = blob[offset]
    if first < 128:
        return first, offset + 1
    count = first & 127
    if not count or count > 2 or offset + 1 + count > len(blob):
        raise ValueError("invalid DER length")
    value = int.from_bytes(blob[offset + 1:offset + 1 + count], "big")
    return value, offset + 1 + count


def der_integer(blob, offset):
    if offset >= len(blob) or blob[offset] != 2:
        raise ValueError("ECDSA signature integer is missing")
    length, start = der_length(blob, offset + 1)
    end = start + length
    if not length or end > len(blob):
        raise ValueError("truncated ECDSA signature integer")
    value = blob[start:end]
    if value[0] == 0:
        value = value[1:]
    if not value or len(value) > 32:
        raise ValueError("ECDSA signature integer is outside P-256")
    return value.rjust(32, b"\0"), end


def raw_signature(blob):
    if not blob or blob[0] != 0x30:
        raise ValueError("ECDSA signature is not a DER sequence")
    length, offset = der_length(blob, 1)
    if offset + length != len(blob):
        raise ValueError("ECDSA signature has trailing or truncated bytes")
    r, offset = der_integer(blob, offset)
    s, offset = der_integer(blob, offset)
    if offset != len(blob):
        raise ValueError("ECDSA signature has extra fields")
    return r + s


def raw_public_key(blob):
    # OpenSSL's prime256v1 SubjectPublicKeyInfo ends in the uncompressed SEC1
    # point. Validate the algorithm identifiers so an arbitrary 65-byte tail
    # cannot be relabelled as a P-256 key.
    ec_public_key_oid = bytes.fromhex("06072a8648ce3d0201")
    prime256v1_oid = bytes.fromhex("06082a8648ce3d030107")
    if ec_public_key_oid not in blob or prime256v1_oid not in blob or \
            len(blob) < 68 or blob[-68:-65] != b"\x03\x42\x00" or blob[-65] != 4:
        raise ValueError("public key is not uncompressed P-256 SubjectPublicKeyInfo")
    point = blob[-64:]
    if not any(point):
        raise ValueError("P-256 public key is zero")
    return point


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("signature_der", type=pathlib.Path)
    parser.add_argument("public_key_der", type=pathlib.Path)
    parser.add_argument("signature_raw", type=pathlib.Path)
    parser.add_argument("public_key_raw", type=pathlib.Path)
    args = parser.parse_args()
    args.signature_raw.write_bytes(raw_signature(args.signature_der.read_bytes()))
    args.public_key_raw.write_bytes(raw_public_key(args.public_key_der.read_bytes()))
    print("AIUEOS_PLC_SIGNATURE_MATERIAL_OK scheme=ecdsa-p256-sha256")


if __name__ == "__main__":
    main()
