#!/usr/bin/env python3
"""Read back two Mac native desktop builds with distinct static distributions.

This is an observer. Amu/Kotoba emit the native artifacts and QEMU exercises
them; this script cannot qualify a release, hardware or an Itonami agent turn.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[3]
ARTIFACTS = {
    "font": "font/aiueos-padded.fnt",
    "kernel": "kernel/KERNEL.ELF",
    "efi": "kernel/BOOTX64.EFI",
    "media": "media/awai-native.img",
}
COMMON = ("compiler", "packager", "qemu", "firmware", "fontSource",
          "ownerManifest", "ownerNames", "scripts", "host", "profile",
          "fuel", "font", "kernel", "efi", "media", "guestEvents")


def pin(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or symlinked evidence: {path}")
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read_build(directory, distribution):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(f"missing or symlinked build: {directory}")
    state = json.loads((directory / "native-desktop-macos.json").read_text())
    guest = json.loads((directory / "qemu/native-desktop-qemu.json").read_text())
    if (state.get("state") != "MACOS_NATIVE_DESKTOP_QEMU_CANDIDATE"
            or state.get("profile") != "desktop"
            or state.get("distribution", {}).get("id") != distribution
            or state.get("guestInputQualified") is not True
            or state.get("nativeFormatEmission") is not True
            or state.get("releaseQualified") is not False
            or state.get("physicalHardwareQualified") is not False):
        raise ValueError(f"incomplete native build: {distribution}")
    descriptor = state["distribution"]["descriptor"]
    if descriptor != {"path": "distribution.json", **pin(directory / "distribution.json")}:
        raise ValueError(f"copied descriptor mismatch: {distribution}")
    if pin(REPO / "distributions" / distribution / "distribution.json") != {
            key: descriptor[key] for key in ("bytes", "sha256")}:
        raise ValueError(f"repository descriptor mismatch: {distribution}")
    if guest.get("status") != "PASS_NATIVE_DESKTOP_INPUT_QEMU":
        raise ValueError(f"QEMU input did not pass: {distribution}")
    for key, relative in ARTIFACTS.items():
        if pin(directory / relative) != state[key] or guest.get(key) != state[key]:
            raise ValueError(f"artifact or QEMU pin mismatch: {distribution}/{key}")
    return state, guest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("aiueos", type=Path)
    parser.add_argument("awai", type=Path)
    parser.add_argument("--output", type=Path, required=True,
                        help="new JSON receipt; parent must already exist")
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("output must be new")
    aiueos, _ = read_build(args.aiueos, "aiueos")
    awai, _ = read_build(args.awai, "awai")
    for key in COMMON:
        if aiueos.get(key) != awai.get(key):
            raise ValueError(f"common build value differs: {key}")
    if aiueos["distribution"]["descriptor"] == awai["distribution"]["descriptor"]:
        raise ValueError("distribution descriptors are identical")
    report = {
        "schema": "aiueos.macos-distribution-parity.v1",
        "status": "PASS",
        "buildStates": {name: state["state"] for name, state in
                        (("aiueos", aiueos), ("awai", awai))},
        "qemuStatuses": {"aiueos": "PASS_NATIVE_DESKTOP_INPUT_QEMU",
                         "awai": "PASS_NATIVE_DESKTOP_INPUT_QEMU"},
        "distributions": {name: state["distribution"] for name, state in
                          (("aiueos", aiueos), ("awai", awai))},
        "commonArtifacts": {key: aiueos[key] for key in
                            ("compiler", "packager", "font", "kernel", "efi", "media")},
        "guestEvents": aiueos["guestEvents"],
        "releaseQualified": False,
        "physicalHardwareQualified": False,
        "userV3AgentLoopQualified": False,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("PASS_NATIVE_DISTRIBUTION_PARITY", report["commonArtifacts"]["media"]["sha256"])


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"FAIL_NATIVE_DISTRIBUTION_PARITY: {error}", file=sys.stderr)
        raise SystemExit(1)
