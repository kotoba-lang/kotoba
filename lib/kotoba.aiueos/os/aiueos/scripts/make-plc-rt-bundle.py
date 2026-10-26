#!/usr/bin/env python3
"""Build the bounded signed PLC payload consumed by the C-free UEFI loader."""

import argparse
import hashlib
import importlib.util
import pathlib
import struct
import sys


def load_receipt_module():
    path = pathlib.Path(__file__).with_name("make-plc-native-receipt.py")
    spec = importlib.util.spec_from_file_location("plc_native_receipt", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_bundle(elf, signature, public_key):
    receipt = load_receipt_module()
    if len(elf) > 12288:
        raise ValueError("PLC ELF exceeds the 12 KiB runtime bound")
    if len(signature) != 64 or len(public_key) != 64:
        raise ValueError("PLC signature and public key must each be 64 bytes")
    digest = hashlib.sha256(elf).digest()
    if not receipt.ecdsa_p256_sha256_valid(signature, public_key, digest):
        raise ValueError("PLC ELF signature is invalid")
    header = (b"AIUPLC1\0" + struct.pack("<II", 1, len(elf)) +
              signature + public_key + digest)
    if len(header) != 176:
        raise AssertionError("PLC bundle header drift")
    return header + elf


def parse_bundle(blob):
    if len(blob) < 176 or blob[:8] != b"AIUPLC1\0":
        raise ValueError("invalid PLC bundle magic")
    version, length = struct.unpack_from("<II", blob, 8)
    if version != 1 or not 8280 <= length <= 12288 or len(blob) != 176 + length:
        raise ValueError("invalid PLC bundle bounds")
    elf = blob[176:]
    digest = hashlib.sha256(elf).digest()
    if blob[144:176] != digest:
        raise ValueError("PLC bundle digest mismatch")
    receipt = load_receipt_module()
    if not receipt.ecdsa_p256_sha256_valid(blob[16:80], blob[80:144], digest):
        raise ValueError("PLC bundle signature mismatch")
    return elf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("elf", type=pathlib.Path)
    parser.add_argument("signature", type=pathlib.Path)
    parser.add_argument("public_key", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    args = parser.parse_args()
    elf = args.elf.read_bytes()
    load_receipt_module().validate_elf(args.elf)
    bundle = make_bundle(elf, args.signature.read_bytes(), args.public_key.read_bytes())
    args.output.write_bytes(bundle)
    parse_bundle(bundle)
    print("AIUEOS_PLC_RT_BUNDLE_OK signed external-elf bytes=" + str(len(bundle)))


if __name__ == "__main__":
    main()
