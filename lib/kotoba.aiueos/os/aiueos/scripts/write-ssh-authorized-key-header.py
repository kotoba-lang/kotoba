#!/usr/bin/env python3
"""Write a public-only P-256 SSH authorization header for the kernel build."""

import re
import sys
from pathlib import Path


def initializer(payload: bytes) -> str:
    return "{" + ",".join(f"0x{byte:02x}" for byte in payload) + "}"


if len(sys.argv) != 3:
    raise SystemExit("usage: write-ssh-authorized-key-header.py <x||y hex> <output>")

public_hex = sys.argv[1].strip().lower()
if not re.fullmatch(r"[0-9a-f]{128}", public_hex):
    raise SystemExit("authorized P-256 key must be exactly 128 hexadecimal characters (x||y)")

public = bytes.fromhex(public_hex)
output = Path(sys.argv[2])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(
    "/* Generated public authorization material; contains no private key. */\n"
    "#ifndef AIUEOS_SSH_AUTHORIZED_KEY_H\n"
    "#define AIUEOS_SSH_AUTHORIZED_KEY_H\n"
    f"#define AIUEOS_SSH_AUTH_X_INITIALIZER {initializer(public[:32])}\n"
    f"#define AIUEOS_SSH_AUTH_Y_INITIALIZER {initializer(public[32:])}\n"
    "#endif\n",
    encoding="ascii",
)
