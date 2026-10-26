#!/usr/bin/env python3
"""Debug the native Itonami Goal save, cold restore and CPL3 path via private QMP.

This is a local VM diagnostic. It creates a marked 64 KiB scratch disk under
the output directory; it never opens a host disk, VNC listener or network.
Synthetic QMP keys are test input, not an approval for an external operation.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
ENTRY = "/os/aiueos/native/user-elf-v2-durable-goal-entry.kotoba"
ELF_SHA256 = "d1cd47b63ec90df52f6763f63c9410d2a032266412be3dd49238db8ecdf61248"
PREFIX = "Goal local:\n"
if not __debug__:
    raise RuntimeError("this assertion gate must not run with Python -O")


def import_file(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pin(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def state(qmp, directory, context):
    surface = qmp.dump(context + 0x238000, 8192, "surface.bin", directory)
    work = qmp.dump(context + 0x23a000, 8192, "desktop-context.bin", directory)
    surface = struct.unpack("<2048I", surface)
    work = struct.unpack("<2048I", work)
    length = surface[2038]
    return {"goal": "".join(map(chr, surface[224:224 + length])) if 12 <= length <= 63 else None,
            "focus": surface[2], "keys": work[73], "lastKey": work[77],
            "framesStarted": work[78], "frames": work[79],
            "generation": work[80], "restore": signed(work[81]),
            "commit": signed(work[82]), "draftEnabled": work[84],
            "submitted": work[85], "profile": work[86], "magic": work[72]}


def signed(value):
    return value if value < 0x80000000 else value - 0x100000000


def wait_state(qmp, directory, context, name, predicate, timeout=60):
    deadline = time.monotonic() + timeout
    current = None
    while time.monotonic() < deadline:
        current = state(qmp, directory, context)
        (directory / "last-state.json").write_text(json.dumps(current, indent=2) + "\n")
        if (predicate(current) and current["magic"] == 0x31545844
                and current["profile"] == 3 and current["draftEnabled"] == 1
                and current["frames"] >= 1
                and current["frames"] == current["framesStarted"]):
            (directory / (name + ".json")).write_text(json.dumps(current, indent=2) + "\n")
            return current
        time.sleep(.2)
    (directory / "registers-last.txt").write_text(qmp.hmp("info registers"))
    raise AssertionError((name, current))


def key(qmp, code):
    qmp.call("send-key", {"keys": [{"type": "qcode", "data": "spc" if code == " " else code}],
                          "hold-time": 60})
    time.sleep(.12)


def screenshot(qmp, directory, font, goal, name):
    ppm = directory / (name + ".ppm")
    png = directory / (name + ".png")
    qmp.call("screendump", {"filename": str(ppm)})
    pixels = import_file("desktop_pixels", "check-native-desktop-qemu.py").ppm_png(ppm, png)
    ink = import_file("draft_pixels", "check-native-draft-restart-qemu.py").visible_goal_ink(
        (directory / "surface.bin").read_bytes(), font, pixels, goal)
    assert all((row["inkPixels"] == 0 if letter == " " else row["inkPixels"] > 0)
               for letter, row in zip(goal, ink))
    return {"image": str(png), "pin": pin(png), "glyphs": ink}


def boot(args, directory, disk):
    directory.mkdir(mode=0o700)
    media = getattr(args, "boot_media", None)
    if media is None:
        esp = directory / "esp/EFI/BOOT"
        esp.mkdir(parents=True)
        (esp / "BOOTX64.EFI").write_bytes(args.efi.read_bytes())
    boot_drive = (f"file={media},format=raw,if=ide,snapshot=on" if media is not None
                  else "file=fat:rw:esp,format=raw")
    command = [str(args.qemu), "-machine", "q35,accel=tcg", "-cpu", "max",
               "-m", "128M", "-smp", "1",
               "-drive", f"if=pflash,format=raw,readonly=on,file={args.firmware}",
               "-drive", boot_drive, "-boot", "order=c",
               "-device", "isa-ide,id=draft-controller",
               "-drive", f"file={disk},format=raw,if=none,id=draft,cache=directsync",
               "-device", "ide-hd,drive=draft,bus=draft-controller.0,unit=1,serial=AWAI90DRAFT000001",
               "-nic", "none", "-display", "none", "-no-reboot",
               "-serial", "file:serial.log", "-debugcon", "file:debug.log", "-qmp", "stdio"]
    (directory / "command.json").write_text(json.dumps(command, indent=2) + "\n")
    log = (directory / "qemu.stderr").open("wb")
    process = subprocess.Popen(command, cwd=directory, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=log, bufsize=0)
    try:
        qmp = import_file("scalar_qmp", "check-native-user-scalar-qemu.py").QMP(process)
    except BaseException:
        process.kill()
        process.wait(timeout=10)
        process.stdin.close()
        process.stdout.close()
        log.close()
        raise
    return process, qmp, log


def close(process, qmp, log):
    if process.poll() is None:
        try:
            qmp.call("quit")
        except (OSError, RuntimeError, TimeoutError):
            process.kill()
    process.wait(timeout=10)
    process.stdin.close()
    process.stdout.close()
    log.close()


def endpoint(qmp, directory, code, request, elf, goal):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        registers = qmp.hmp("info registers")
        (directory / "registers-last.txt").write_text(registers)
        rip_match = re.search(r"\bRIP=([0-9a-f]+)", registers, re.I)
        cpl_match = re.search(r"\bCPL=([0-3])", registers)
        request_bytes = qmp.dump(request, 4096, "request-after.bin", directory)
        result = struct.unpack_from("<Q", request_bytes)[0]
        if rip_match and cpl_match:
            rip, cpl = int(rip_match.group(1), 16), int(cpl_match.group(1))
            if result == len(goal) and cpl == 3 and code + 31 <= rip <= code + 35:
                qmp.call("stop")
                code_bytes = qmp.dump(code, 4096, "code-final.bin", directory)
                request_bytes = qmp.dump(request, 4096, "request-final.bin", directory)
                expected = struct.pack("<I", len(goal)) + goal.encode("ascii") + bytes(60 - len(goal))
                assert code_bytes[:330] == elf[4096:4426]
                assert request_bytes[256:320] == expected
                assert struct.unpack_from("<Q", request_bytes, 8)[0] == 255
                return {"rip": rip, "cpl": cpl, "result": result,
                        "goalRegionMatchesRestoredText": True, "codeMatchesPinnedElf": True}
        time.sleep(.2)
    raise AssertionError("restored Goal did not reach the user-v2 CPL3 endpoint")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_dir", type=Path)
    parser.add_argument("--goal", default="a b")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--qemu", type=Path)
    parser.add_argument("--firmware", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z ]{1,51}", args.goal) or not args.goal.strip():
        parser.error("--goal requires 1-51 lowercase letters or spaces with a letter")
    build = args.build_dir.resolve(strict=True)
    receipt = build / "build-state.json"
    if not receipt.is_file():
        parser.error("build_dir requires build-state.json")
    built = json.loads(receipt.read_text())
    if built.get("state") != "MACOS_NATIVE_IMAGE_CANDIDATE" or built.get("kernelEntry") != ENTRY:
        parser.error("build is not the durable Goal native candidate")
    args.kernel, args.efi = build / "KERNEL.ELF", build / "BOOTX64.EFI"
    font, slot = build / "source/boot-font.bin", build / "source/boot-user-slot.bin"
    for name, path, expected in (("kernel", args.kernel, built["kernel"]),
                                 ("efi", args.efi, built["efi"]),
                                 ("font", font, built["bootFont"]),
                                 ("slot", slot, built["bootUserSlot"])):
        if path.is_symlink() or not path.is_file() or pin(path) != expected:
            parser.error(f"{name} missing or differs from build receipt")
    source = HERE.parent / "native/user-elf-v2-durable-goal-entry.kotoba"
    for path in (source, HERE.parent / "native/desktop.kotoba",
                 HERE.parent / "native/draft_store.kotoba"):
        graph_name = "/os/aiueos/" + str(path.relative_to(HERE.parent))
        if (path.is_symlink() or not path.is_file()
                or pin(path) != built.get("sourceGraph", {}).get(graph_name)):
            parser.error(f"{graph_name} differs from build receipt")
    efi_bytes, kernel_bytes, slot_bytes = args.efi.read_bytes(), args.kernel.read_bytes(), slot.read_bytes()
    elf_size = struct.unpack_from("<Q", slot_bytes, 16)[0]
    elf = slot_bytes[64:64 + elf_size]
    if (len(slot_bytes) != 524288 or struct.unpack_from("<QQ", slot_bytes) !=
            (0x0031444c50554941, 2) or elf_size != 8280
            or any(slot_bytes[64 + elf_size:])
            or hashlib.sha256(elf).hexdigest() != ELF_SHA256
            or efi_bytes.count(kernel_bytes) != 1 or efi_bytes.count(slot_bytes) != 1
            or efi_bytes.count(font.read_bytes()) != 1):
        parser.error("kernel, EFI or pinned user-v2 payload contract differs")
    header = struct.unpack_from("<IIQQQQQQ", kernel_bytes, 120)
    if header[:4] != (1, 6, 1048576, 0x200000):
        parser.error("unexpected native context layout")
    context = header[3]
    code, request = context + 0x20000, context + 0x21000
    qemu_name = args.qemu or shutil.which("qemu-system-x86_64")
    if qemu_name is None:
        parser.error("QEMU missing; pass --qemu")
    args.qemu = Path(qemu_name).resolve(strict=True)
    args.firmware = (args.firmware or args.qemu.parent.parent / "share/qemu/edk2-x86_64-code.fd").resolve(strict=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = (args.output or build.parent / f"{build.name}-durable-debug-{stamp}-{os.getpid()}").resolve()
    if output.exists():
        parser.error("output must be a new private directory")
    output.mkdir(mode=0o700)
    disk = output / "draft.raw"
    blank = bytearray(128 * 512)
    struct.pack_into("<4I", blank, 0, 0x49415741, 0x54465244, 1, 128)
    disk.write_bytes(blank)
    boots = []
    for ordinal in (1, 2):
        directory = output / f"boot-{ordinal}"
        process, qmp, log = boot(args, directory, disk)
        try:
            expected = args.goal if ordinal == 2 else ""
            current = wait_state(qmp, directory, context, "boot",
                                 lambda s: s["goal"] == PREFIX + expected and
                                 s["restore"] == ordinal - 1 and s["keys"] == 0)
            key(qmp, "2")
            current = wait_state(qmp, directory, context, "open",
                                 lambda s: s["focus"] == 2 and s["keys"] > current["keys"])
            if ordinal == 1:
                for index, letter in enumerate(args.goal, 1):
                    previous = current["keys"]
                    key(qmp, letter)
                    current = wait_state(qmp, directory, context, f"edit-{index}",
                                         lambda s, i=index, p=previous:
                                         s["goal"] == PREFIX + args.goal[:i] and s["keys"] > p)
                visible = screenshot(qmp, directory, font.read_bytes(), args.goal, "typed-goal")
                previous = current["keys"]
                key(qmp, "f5")
                committed = wait_state(qmp, directory, context, "commit",
                                       lambda s: s["commit"] == 1 and s["generation"] == 1
                                       and s["keys"] > previous)
                boots.append({"boot": 1, "committed": committed, "screenshot": visible})
            else:
                assert current["generation"] == 1 and current["submitted"] == 0
                visible = screenshot(qmp, directory, font.read_bytes(), args.goal, "restored-goal")
                key(qmp, "ret")
                user = endpoint(qmp, directory, code, request, elf, args.goal)
                boots.append({"boot": 2, "restored": current, "screenshot": visible,
                              "userEndpoint": user})
        finally:
            close(process, qmp, log)
        if ordinal == 1:
            first = disk.read_bytes()
            assert first != bytes(blank) and first[:512] == blank[:512]
            assert first[2048:] == blank[2048:]
            assert hashlib.sha256(first[1536:2016]).digest() == first[2016:2048]
        else:
            assert disk.read_bytes() == first, "CPL3 read modified the draft medium"
    report = {"schema": "aiueos.native-durable-user-v2-unattended.v1",
              "status": "PASS_NATIVE_DRAFT_COLD_RESTORE_TO_USER_V2_CPL3",
              "build": str(build), "kernel": pin(args.kernel), "efi": pin(args.efi),
              "font": pin(font), "slot": pin(slot), "source": pin(source),
              "scratchDisk": pin(disk), "qemu": pin(args.qemu),
              "firmware": pin(args.firmware), "observer": pin(Path(__file__)),
              "boots": boots, "qmpTransport": "private-stdio", "vncUsed": False,
              "networkUsed": False, "humanPasswordRequired": False,
              "syntheticKeysAreExternalConsent": False,
              "D2WorkspaceCodec": False, "signedHeadAuthority": False,
              "modelOrToolOperation": False, "physicalHardware": False}
    path = output / "debug-summary.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "receipt": str(path),
                      "screenshot": boots[1]["screenshot"]["image"],
                      "goal": args.goal, "humanPasswordRequired": False}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
