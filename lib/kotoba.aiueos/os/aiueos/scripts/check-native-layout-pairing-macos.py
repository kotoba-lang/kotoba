#!/usr/bin/env python3
"""Exercise native Amu's versioned AIUEOS package admission on built artifacts.

The Mac host stages bytes and inspects results; only the signed Amu image
packages the EFI. This is a layout gate, not a boot or release verdict.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import tempfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_build(path, kernel_entry, user_target):
    state = json.loads((path / "build-state.json").read_text())
    if (state["state"] != "MACOS_NATIVE_IMAGE_CANDIDATE"
            or not state["kernelEntry"].endswith(kernel_entry)
            or state["bootUserTarget"] != user_target):
        raise ValueError("wrong build state or layout target: " + str(path))
    for filename, field in (("KERNEL.ELF", "kernel"),
                            ("BOOTX64.EFI", "efi"),
                            ("boot-user.elf", "bootUserElf")):
        if digest(path / filename) != state[field]["sha256"]:
            raise ValueError("build artifact pin drift: " + str(path / filename))
    slot = path / "source/boot-user-slot.bin"
    if digest(slot) != state["bootUserSlot"]["sha256"]:
        raise ValueError("user slot pin drift: " + str(slot))
    return state, slot


def main(args):
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("Apple Silicon Mac required")
    compiler = args.compiler_image.resolve(strict=True)
    if digest(compiler) != args.compiler_sha256:
        raise ValueError("compiler SHA-256 mismatch")
    subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(compiler)],
                   check=True, capture_output=True)
    old, old_slot = load_build(args.old_build, "user-elf-v3-local-model-entry.kotoba",
                               "x86_64-aiueos-user-v3")
    new, new_slot = load_build(args.new_build, "user-elf-v4-local-model-entry.kotoba",
                               "x86_64-aiueos-user-v4")
    font = args.font.resolve(strict=True)
    if digest(font) != old["bootFont"]["sha256"] or digest(font) != new["bootFont"]["sha256"]:
        raise ValueError("font pin drift")
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    with tempfile.TemporaryDirectory(prefix="aiueos-layout-") as tmp:
        stage = Path(tmp)
        shutil.copyfile(font, stage / "font.bin")
        scope = os.open(stage, os.O_RDONLY | os.O_DIRECTORY)
        if scope != 3:
            os.dup2(scope, 3)
            os.close(scope)
            scope = 3
        try:
            for name, kernel_build, slot, accepted, mutation in (
                ("kernel-v1-slot-v2", args.old_build, old_slot, True, None),
                ("kernel-v2-slot-v3", args.new_build, new_slot, True, None),
                ("kernel-v1-slot-v3", args.old_build, new_slot, False, None),
                ("kernel-v2-slot-v2", args.new_build, old_slot, False, None),
                ("kernel-v2-rw-paddr", args.new_build, new_slot, False, "rw-paddr"),
                ("kernel-v2-rw-memsz", args.new_build, new_slot, False, "rw-memsz"),
                ("user-v4-entry", args.new_build, new_slot, False, "user-entry"),
            ):
                kernel_bytes = bytearray((kernel_build / "KERNEL.ELF").read_bytes())
                slot_bytes = bytearray(slot.read_bytes())
                if mutation in ("rw-paddr", "rw-memsz"):
                    phoff = struct.unpack_from("<Q", kernel_bytes, 32)[0]
                    rw = phoff + struct.unpack_from("<H", kernel_bytes, 54)[0]
                    off = rw + (24 if mutation == "rw-paddr" else 40)
                    value = struct.unpack_from("<Q", kernel_bytes, off)[0]
                    struct.pack_into("<Q", kernel_bytes, off,
                                     value + 4096 if mutation == "rw-paddr" else value - 1)
                elif mutation == "user-entry":
                    user_elf = bytearray((args.new_build / "boot-user.elf").read_bytes())
                    entry = struct.unpack_from("<Q", user_elf, 24)[0]
                    struct.pack_into("<Q", user_elf, 24, entry + 1)
                    (stage / "user.elf").write_bytes(user_elf)
                    (stage / "slot.bin").unlink(missing_ok=True)
                    result = subprocess.run(
                        [str(compiler), "package-aiueos-user-payload", "user.elf",
                         "--output", "slot.bin", "--version", "v3"],
                        cwd=stage, pass_fds=(scope,), capture_output=True, timeout=120,
                        env={"PATH": "/nonexistent"})
                    stderr = result.stderr.decode(errors="replace").strip()
                    if result.returncode == 0 or "E7111" not in stderr or (stage / "slot.bin").exists():
                        raise ValueError("invalid user ELF accepted: " + stderr)
                    rows.append({"case": name, "accepted": False, "exit": result.returncode,
                                 "stderr": stderr})
                    continue
                (stage / "KERNEL.ELF").write_bytes(kernel_bytes)
                (stage / "slot.bin").write_bytes(slot_bytes)
                target = stage / "BOOTX64.EFI"
                target.unlink(missing_ok=True)
                result = subprocess.run(
                    [str(compiler), "package-aiueos-boot", "KERNEL.ELF", "--output",
                     "BOOTX64.EFI", "--font", "font.bin", "--user-slot", "slot.bin",
                     "--pci-resources", "v1"],
                    cwd=stage, pass_fds=(scope,), capture_output=True, timeout=120,
                    env={"PATH": "/nonexistent"})
                stderr = result.stderr.decode(errors="replace").strip()
                if accepted:
                    expected = old if kernel_build == args.old_build else new
                    if result.returncode or stderr or not target.is_file() or digest(target) != expected["efi"]["sha256"]:
                        raise ValueError("matching layout refused or changed: " + name + " " + stderr)
                elif result.returncode == 0 or "E7111" not in stderr or target.exists():
                    raise ValueError("invalid layout accepted: " + name + " " + stderr)
                rows.append({"case": name, "accepted": accepted, "exit": result.returncode,
                             "stderr": stderr})
        finally:
            os.close(scope)
    receipt = {"schema": "aiueos.native-layout-pairing.v1",
               "compilerSha256": args.compiler_sha256,
               "kernelV1Sha256": old["kernel"]["sha256"],
               "kernelV2Sha256": new["kernel"]["sha256"],
               "cases": rows, "status": "PASS_NATIVE_LAYOUT_PAIRING"}
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(receipt["status"], len(rows), "cases")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler-image", type=Path, required=True)
    parser.add_argument("--compiler-sha256", required=True)
    parser.add_argument("--old-build", type=Path, required=True)
    parser.add_argument("--new-build", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
