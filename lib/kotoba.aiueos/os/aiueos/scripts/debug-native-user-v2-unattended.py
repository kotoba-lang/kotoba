#!/usr/bin/env python3
"""Boot a dual-payload AIUEOS build and debug its Itonami Goal without VNC."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys


HERE = Path(__file__).resolve().parent


def pin(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_dir", type=Path,
                        help="complete Mac native dual-payload kernel build")
    parser.add_argument("--goal", default="a b",
                        help="one lowercase Goal to type (default: a b)")
    parser.add_argument("--output", type=Path,
                        help="new private output directory beside the build by default")
    parser.add_argument("--qemu", type=Path)
    parser.add_argument("--firmware", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z ]{1,51}", args.goal) or not args.goal.strip():
        parser.error("--goal requires 1-51 lowercase letters or spaces with a letter")
    build = args.build_dir.resolve()
    state_path = build / "build-state.json"
    if not state_path.is_file():
        parser.error("build_dir requires build-state.json")
    state = json.loads(state_path.read_text())
    if (state.get("state") != "MACOS_NATIVE_IMAGE_CANDIDATE"
            or state.get("bootFont") is None or state.get("bootUserSlot") is None
            or state.get("kernelEntry") != "/os/aiueos/native/user-elf-v2-live-goal-entry.kotoba"):
        parser.error("build is not the native dual-payload live-Goal candidate")
    paths = {"kernel": build / "KERNEL.ELF", "efi": build / "BOOTX64.EFI",
             "font": build / "source/boot-font.bin",
             "slot": build / "source/boot-user-slot.bin"}
    receipts = {"kernel": state["kernel"], "efi": state["efi"],
                "font": state["bootFont"], "slot": state["bootUserSlot"]}
    for name, path in paths.items():
        if path.is_symlink() or not path.is_file() or pin(path) != receipts[name]:
            parser.error(f"{name} missing or differs from build receipt")
    slot = paths["slot"].read_bytes()
    if len(slot) != 524288 or struct.unpack_from("<QQ", slot) != (0x0031444c50554941, 2):
        parser.error("user slot header is invalid")
    elf_size = struct.unpack_from("<Q", slot, 16)[0]
    if elf_size != 8280 or any(slot[64 + elf_size:]):
        parser.error("user slot is not the pinned v2 ELF fixture")
    if args.qemu is None:
        found = shutil.which("qemu-system-x86_64")
        if found is None:
            parser.error("QEMU missing; pass --qemu")
        args.qemu = Path(found)
    qemu = args.qemu.resolve()
    firmware = (args.firmware or qemu.parent.parent / "share/qemu/edk2-x86_64-code.fd").resolve()
    if not qemu.is_file() or not firmware.is_file():
        parser.error("QEMU and firmware must be regular files")
    if args.output:
        output = args.output.resolve()
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = build.parent / f"{build.name}-user-v2-debug-{stamp}-{os.getpid()}"
    if output.exists():
        parser.error("output must be a new directory")
    source = HERE.parent / "native/user-elf-v2-live-goal-entry.kotoba"
    graph = state.get("sourceGraph", {}).get("/os/aiueos/native/user-elf-v2-live-goal-entry.kotoba")
    if source.is_symlink() or not source.is_file() or pin(source) != graph:
        parser.error("current kernel source differs from build receipt")
    output.mkdir(mode=0o700)
    elf_path = output / "pinned-user-v2.elf"
    elf_path.write_bytes(slot[64:64 + elf_size])
    other_goal = "hello" if args.goal != "hello" else "a b"
    gate = output / "qmp"
    command = [sys.executable, str(HERE / "check-native-user-v2-live-goal-qemu.py"),
               "--kernel", str(paths["kernel"]), "--efi", str(paths["efi"]),
               "--elf", str(elf_path), "--font", str(paths["font"]),
               "--slot", str(paths["slot"]), "--source", str(source),
               "--qemu", str(qemu), "--firmware", str(firmware),
               "--output", str(gate), "--goals", args.goal, other_goal]
    result = subprocess.run(command, check=False)
    receipt = gate / "native-user-v2-live-goal-qemu.json"
    passed = (result.returncode == 0 and receipt.is_file()
              and json.loads(receipt.read_text()).get("status") ==
              "PASS_NATIVE_DUAL_PAYLOAD_ITONAMI_GOAL_CPL3_AND_REFUSALS")
    summary = {"status": "PASS" if passed else "FAIL", "goal": args.goal,
               "build": str(build), "buildReceipt": str(state_path),
               "observerReceipt": str(receipt),
               "screenshot": str(gate / "goal-1/desktop.png"),
               "emptyGoalRefusal": passed, "modifiedSlotRefusal": passed,
               "qmpTransport": "private-stdio", "vncUsed": False,
               "networkUsed": False}
    (output / "debug-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
