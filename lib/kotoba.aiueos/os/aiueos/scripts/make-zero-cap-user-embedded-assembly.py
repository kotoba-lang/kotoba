#!/usr/bin/env python3
"""Embed one pinned Amu selfhost ELF for the test-only signed CPL3 smoke."""

import argparse
import hashlib
import pathlib
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("elf", type=pathlib.Path)
    parser.add_argument("expected_sha256")
    parser.add_argument("signature", type=pathlib.Path)
    parser.add_argument("public_key", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    args = parser.parse_args()
    blob = args.elf.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != args.expected_sha256 or len(blob) > 98304:
        raise SystemExit("error: zero-cap ELF digest or size mismatch")
    verifier = pathlib.Path(__file__).with_name("verify-kotoba-user-elf.py")
    verified = subprocess.run(
        [sys.executable, str(verifier), str(args.elf), digest],
        check=True, text=True, capture_output=True)
    if "caps=none" not in verified.stdout:
        raise SystemExit("error: zero-cap smoke requires a capability-free ELF")
    signature = args.signature.read_bytes()
    public_key = args.public_key.read_bytes()
    if len(signature) != 64 or len(public_key) != 64 or not any(public_key):
        raise SystemExit("error: raw P-256 signature and public key are required")
    path = str(args.elf.resolve())
    if any(character in path for character in ('"', '\\', '\n', '\r')):
        raise SystemExit("error: ELF path cannot be represented in assembly")

    def byte_list(data):
        return ",".join(f"0x{value:02x}" for value in data)

    args.output.write_text(
        '.section .rodata.zero_cap_user,"a",@progbits\n'
        '.balign 16\n'
        '.global aiueos_zero_cap_elf_start\n'
        '.global aiueos_zero_cap_elf_end\n'
        'aiueos_zero_cap_elf_start:\n'
        f'.incbin "{path}"\n'
        'aiueos_zero_cap_elf_end:\n'
        '.balign 16\n'
        '.global aiueos_zero_cap_elf_sha256\n'
        'aiueos_zero_cap_elf_sha256:\n'
        f'.byte {byte_list(bytes.fromhex(digest))}\n'
        '.balign 16\n'
        '.global aiueos_zero_cap_signature\n'
        'aiueos_zero_cap_signature:\n'
        f'.byte {byte_list(signature)}\n'
        '.balign 16\n'
        '.global aiueos_zero_cap_public_key\n'
        'aiueos_zero_cap_public_key:\n'
        f'.byte {byte_list(public_key)}\n', encoding="ascii")
    print("AIUEOS_ZERO_CAP_USER_EMBED_OK sha256=" + digest)


if __name__ == "__main__":
    main()
