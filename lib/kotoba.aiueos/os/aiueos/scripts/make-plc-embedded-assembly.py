#!/usr/bin/env python3
"""Bind one PLC ELF and its build receipt into an RT-only kernel build."""

import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import sys

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def validate_elf(path):
    validator_path = pathlib.Path(__file__).with_name("make-plc-native-receipt.py")
    spec = importlib.util.spec_from_file_location("make_plc_native_receipt", validator_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.validate_elf(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("elf", type=pathlib.Path)
    parser.add_argument("receipt", type=pathlib.Path)
    parser.add_argument("signature", type=pathlib.Path)
    parser.add_argument("public_key", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    args = parser.parse_args()
    blob = args.elf.read_bytes()
    validate_elf(args.elf)
    receipt_bytes = args.receipt.read_bytes()
    signature = args.signature.read_bytes()
    public_key = args.public_key.read_bytes()
    if len(signature) != 64 or len(public_key) != 64 or not any(public_key):
        raise SystemExit("error: PLC admission requires raw P-256 signature and public key")
    receipt = json.loads(receipt_bytes)
    digest = hashlib.sha256(blob).hexdigest()
    if (receipt.get("format") != "aiueos-plc-native-receipt/v1" or
            receipt.get("profile") != "aiueos-plc-v1" or
            receipt.get("target") != "x86_64-aiueos-user-v1"):
        raise SystemExit("error: incompatible PLC receipt")
    if not SHA256.fullmatch(str(receipt.get("native_elf_sha256", ""))) or \
            receipt["native_elf_sha256"] != digest:
        raise SystemExit("error: PLC ELF does not match its receipt")
    if receipt.get("runtime_linux") is not False or \
            receipt.get("runtime_jvm") is not False or \
            receipt.get("runtime_gc") is not False:
        raise SystemExit("error: hosted runtime entered PLC receipt")
    if receipt.get("capabilities") != [16, 17, 18, 19]:
        raise SystemExit("error: PLC receipt capability set changed")
    path = str(args.elf.resolve())
    if any(character in path for character in ('"', '\n', '\r')):
        raise SystemExit("error: PLC ELF path cannot be represented in assembly")
    digest_bytes = ",".join("0x" + digest[index:index + 2]
                            for index in range(0, 64, 2))
    receipt_digest = hashlib.sha256(receipt_bytes).hexdigest()
    receipt_bytes_asm = ",".join("0x" + receipt_digest[index:index + 2]
                                 for index in range(0, 64, 2))
    signature_asm = ",".join(f"0x{value:02x}" for value in signature)
    public_key_asm = ",".join(f"0x{value:02x}" for value in public_key)
    args.output.write_text(
        '.section .rodata.plc_elf,"a",@progbits\n'
        '.balign 16\n'
        '.global aiueos_plc_elf_start\n'
        '.global aiueos_plc_elf_end\n'
        'aiueos_plc_elf_start:\n'
        f'.incbin "{path}"\n'
        'aiueos_plc_elf_end:\n'
        '.global aiueos_plc_elf_sha256\n'
        'aiueos_plc_elf_sha256:\n'
        f'.byte {digest_bytes}\n'
        '.global aiueos_plc_receipt_sha256\n'
        'aiueos_plc_receipt_sha256:\n'
        f'.byte {receipt_bytes_asm}\n'
        '.global aiueos_plc_signature\n'
        'aiueos_plc_signature:\n'
        f'.byte {signature_asm}\n'
        '.global aiueos_plc_public_key\n'
        'aiueos_plc_public_key:\n'
        f'.byte {public_key_asm}\n', encoding="ascii")
    print("AIUEOS_PLC_EMBED_OK elf_sha256=" + digest +
          " receipt_sha256=" + receipt_digest)


if __name__ == "__main__":
    main()
