#!/usr/bin/env python3
"""Verify an RSA-2048 PKCS#1 v1.5 SHA-256 signature over a release receipt.

Standard-library only: the signing key never enters the repository or the
image builder; signing happens offline (or with an ephemeral CI key in the
smoke). This verifier performs only the public-key operation, mirroring the
in-kernel Kotoba RSA admission used for the application catalog.
"""

import argparse
import base64
import hashlib
from pathlib import Path

SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")
RSA_2048_BYTES = 256


def der_read(data, offset):
    """Read one DER TLV; return (tag, value, next_offset)."""
    tag = data[offset]
    length = data[offset + 1]
    offset += 2
    if length & 0x80:
        count = length & 0x7F
        if count == 0 or count > 4:
            raise ValueError("unsupported DER length")
        length = int.from_bytes(data[offset:offset + count], "big")
        offset += count
    return tag, data[offset:offset + length], offset + length


def parse_public_key(path):
    """Return (modulus, exponent) from a PEM/DER SubjectPublicKeyInfo or
    PKCS#1 RSAPublicKey."""
    raw = Path(path).read_bytes()
    if b"-----BEGIN" in raw:
        body = b"".join(line for line in raw.splitlines()
                        if line and not line.startswith(b"-----"))
        raw = base64.b64decode(body)
    tag, outer, _ = der_read(raw, 0)
    if tag != 0x30:
        raise ValueError("public key is not a DER sequence")
    tag, first, next_offset = der_read(outer, 0)
    if tag == 0x30:  # SubjectPublicKeyInfo: algorithm sequence, then BIT STRING
        tag, bitstring, _ = der_read(outer, next_offset)
        if tag != 0x03 or bitstring[0] != 0:
            raise ValueError("invalid SubjectPublicKeyInfo bit string")
        tag, rsa, _ = der_read(bitstring, 1)
        if tag != 0x30:
            raise ValueError("invalid RSAPublicKey sequence")
        outer, next_offset = rsa, 0
        tag, first, next_offset = der_read(outer, next_offset)
    if tag != 0x02:
        raise ValueError("missing RSA modulus")
    modulus = int.from_bytes(first, "big")
    tag, exponent_bytes, _ = der_read(outer, next_offset)
    if tag != 0x02:
        raise ValueError("missing RSA exponent")
    exponent = int.from_bytes(exponent_bytes, "big")
    if modulus.bit_length() != 2048:
        raise ValueError("release signing policy requires RSA-2048, got %d bits"
                         % modulus.bit_length())
    return modulus, exponent


def verify(receipt_path, signature_path, public_key_path):
    modulus, exponent = parse_public_key(public_key_path)
    signature = Path(signature_path).read_bytes()
    if len(signature) != RSA_2048_BYTES:
        raise ValueError("signature must be exactly %d bytes" % RSA_2048_BYTES)
    decrypted = pow(int.from_bytes(signature, "big"), exponent, modulus)
    encoded = decrypted.to_bytes(RSA_2048_BYTES, "big")
    digest = hashlib.sha256(Path(receipt_path).read_bytes()).digest()
    expected = (b"\x00\x01" +
                b"\xff" * (RSA_2048_BYTES - 3 - len(SHA256_DIGEST_INFO) - len(digest)) +
                b"\x00" + SHA256_DIGEST_INFO + digest)
    # Fixed-work comparison over the full encoded message.
    difference = 0
    for a, b in zip(encoded, expected):
        difference |= a ^ b
    if difference:
        raise ValueError("release signature does not verify")


def key_fingerprint(public_key_path):
    """SHA-256 over the DER public-key bytes; the revocation list names these."""
    return hashlib.sha256(Path(public_key_path).read_bytes()).hexdigest()


def check_revoked(public_key_path, revoked_path):
    """Refuse a signer whose fingerprint is listed in the revocation file."""
    if revoked_path is None:
        return
    fingerprint = key_fingerprint(public_key_path)
    for line in Path(revoked_path).read_text().splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry and entry.lower() == fingerprint.lower():
            raise ValueError("release signer is revoked: %s" % fingerprint)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--signature", required=True)
    parser.add_argument("--public-key", required=True)
    parser.add_argument("--revoked-keys", default=None,
                        help="file of revoked key fingerprints (SHA-256 of the DER public key, one per line)")
    args = parser.parse_args()
    check_revoked(args.public_key, args.revoked_keys)
    verify(args.receipt, args.signature, args.public_key)
    print("AIUEOS_RELEASE_SIGNATURE_OK rsa2048-pkcs1-sha256")


if __name__ == "__main__":
    main()
