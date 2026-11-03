#!/usr/bin/env python3
"""Retain recipes for regenerable native media negative-control images."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def reconstruct(raw, operation, offset):
    if operation == "flip":
        data = bytearray(raw)
        data[offset] ^= 1
        return bytes(data)
    if operation == "truncate":
        return raw[:-1]
    if operation == "append-zero":
        return raw + b"\0"
    raise ValueError("unknown reconstruction operation")


def specifications(disk_size):
    return [
        ("primary-gpt.img", "awai-native.img", "flip", 512 + 24),
        ("backup-gpt.img", "awai-native.img", "flip", disk_size - 512 + 24),
        ("fat-mirror.img", "awai-native.img", "flip", 1049088 + 4),
        ("directory-name.img", "awai-native.img", "flip", 1122816 + 576),
        ("efi-content.img", "awai-native.img", "flip", 1123840 + 512),
        ("truncated.img", "awai-native.img", "truncate", None),
        ("trailer.img", "awai-native.img", "append-zero", None),
        ("iso-catalog.iso", "awai-native.iso", "flip", 19 * 2048 + 1),
        ("iso-efi-content.iso", "awai-native.iso", "flip", 23 * 2048 + 1123840 - 1048576 + 512),
        ("iso-truncated.iso", "awai-native.iso", "truncate", None),
        ("iso-trailer.iso", "awai-native.iso", "append-zero", None),
    ]


def make_record(root, name, source_name, operation, offset):
    source, target = root / source_name, root / name
    if source.is_symlink() or target.is_symlink():
        return None
    raw, control = source.read_bytes(), target.read_bytes()
    if reconstruct(raw, operation, offset) != control:
        return None
    return {"name": name, "source": source_name, "sourceSha256": digest(raw),
            "sha256": digest(control), "bytes": len(control),
            "operation": operation, "offset": offset}


def verify_record(root, record):
    name, source_name = record["name"], record["source"]
    if Path(name).name != name or Path(source_name).name != source_name:
        raise ValueError("record paths must be file names")
    source = root / source_name
    if source.is_symlink() or not source.is_file():
        raise ValueError("source is missing or a symlink")
    raw = source.read_bytes()
    if digest(raw) != record["sourceSha256"]:
        raise ValueError("source digest changed")
    result = reconstruct(raw, record["operation"], record["offset"])
    if len(result) != record["bytes"] or digest(result) != record["sha256"]:
        raise ValueError("reconstructed control differs from receipt")
    return result


def discard_control(root, record):
    target = root / record["name"]
    if target.is_symlink() or not target.is_file():
        return False
    rebuilt = verify_record(root, record)
    if target.read_bytes() != rebuilt:
        return False
    target.unlink()
    return True


def restore_control(root, record):
    rebuilt = verify_record(root, record)
    target = root / record["name"]
    with target.open("xb") as stream:
        stream.write(rebuilt)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="media output containing native-media.json")
    parser.add_argument("name", help="control file name recorded in the receipt")
    args = parser.parse_args()
    receipt = json.loads((args.output / "native-media.json").read_text())
    records = [r for r in receipt.get("reconstructableControls", []) if r["name"] == args.name]
    if receipt.get("state") != "MACOS_NATIVE_MEDIA_CANDIDATE" or len(records) != 1:
        raise ValueError("successful receipt with one matching control required")
    print(restore_control(args.output, records[0]))


if __name__ == "__main__":
    main()
