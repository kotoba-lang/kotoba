#!/usr/bin/env python3
"""Type two Itonami Goals over private QMP and observe actual CPL3 reads."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import time


HERE = Path(__file__).resolve().parent
ELF_SHA256 = "d1cd47b63ec90df52f6763f63c9410d2a032266412be3dd49238db8ecdf61248"
if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")


def import_file(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pin(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def state(qmp, output, context):
    surface_bytes = qmp.dump(context + 0x238000, 8192, "surface.bin", output)
    work_bytes = qmp.dump(context + 0x23a000, 8192, "desktop-context.bin", output)
    surface = struct.unpack("<2048I", surface_bytes)
    work = struct.unpack("<2048I", work_bytes)
    length = surface[2038]
    goal = "".join(map(chr, surface[224:224 + length])) if 12 <= length <= 63 else None
    return {"goal": goal, "focus": surface[2], "keys": work[73],
            "lastKey": work[77], "submitted": work[85], "mode": work[86],
            "magic": work[72], "framesStarted": work[78], "frames": work[79]}


def wait_ui(qmp, output, context, prior_keys, expected_goal, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = state(qmp, output, context)
        if (row["magic"] == 0x31545844 and row["mode"] == 2
                and row["frames"] >= 1 and row["frames"] == row["framesStarted"]
                and row["keys"] > prior_keys and row["goal"] == expected_goal):
            return row
        time.sleep(.15)
    raise AssertionError("Itonami UI input endpoint unavailable")


def key(qmp, code):
    qmp.call("send-key", {"keys": [{"type": "qcode", "data": "spc" if code == " " else code}],
                          "hold-time": 60})


def run_boot(qmp_type, args, output, context, code, request, elf_bytes, goal,
             font_bytes, efi_image, tampered=False):
    output.mkdir(mode=0o700)
    esp = output / "esp/EFI/BOOT"
    esp.mkdir(parents=True)
    (esp / "BOOTX64.EFI").write_bytes(efi_image)
    command = [str(args.qemu), "-machine", "q35,accel=tcg", "-cpu", "max",
               "-m", "128M", "-smp", "1",
               "-drive", f"if=pflash,format=raw,readonly=on,file={args.firmware}",
               "-drive", "file=fat:rw:esp,format=raw", "-boot", "order=c",
               "-nic", "none", "-display", "none", "-no-reboot",
               "-serial", "file:serial.log", "-debugcon", "file:debug.log",
               "-qmp", "stdio"]
    (output / "command.json").write_text(json.dumps(command, indent=2) + "\n")
    with (output / "qemu.stderr").open("wb") as log:
        process = subprocess.Popen(command, cwd=output, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=log, bufsize=0)
        qmp = None
        try:
            qmp = qmp_type(process)
            initial = wait_ui(qmp, output, context, -1, "Goal (RAM):\n", timeout=55)
            assert initial["focus"] != 2 and initial["submitted"] == 0
            events = [{"key": "initial", **initial}]
            for codepoint in "2" + goal:
                previous = events[-1]["keys"]
                key(qmp, codepoint)
                expected = "Goal (RAM):\n" + goal[:max(0, len(events) - 1)]
                row = wait_ui(qmp, output, context, previous, expected)
                events.append({"key": codepoint, **row})
                time.sleep(.12)
            final = events[-1]
            assert final["focus"] == 2 and final["submitted"] == 0
            assert qmp.dump(request, 4096, "request-before.bin", output)[256:320] == bytes(64)
            if not goal:
                key(qmp, "ret")
                after = wait_ui(qmp, output, context, final["keys"], "Goal (RAM):\n")
                assert after["focus"] == 2 and after["submitted"] == 0
                assert qmp.dump(request, 4096, "request-empty.bin", output)[0:320] == bytes(320)
                registers = qmp.hmp("info registers")
                cpl_match = re.search(r"\bCPL=([0-3])", registers)
                assert cpl_match is not None and int(cpl_match.group(1)) == 0
                return {"goal": "", "ui": after, "emptyEnterRefused": True,
                        "userPageUnchanged": True, "cpl": 0}
            ppm = output / "desktop.ppm"
            qmp.call("screendump", {"filename": str(ppm)})
            pixels = import_file("desktop_pixels", "check-native-desktop-qemu.py").ppm_png(
                ppm, output / "desktop.png")
            ink = import_file("goal_pixels", "check-native-draft-restart-qemu.py").visible_goal_ink(
                (output / "surface.bin").read_bytes(), font_bytes, pixels, goal)
            assert len(ink) == len(goal)
            assert all(item["inkPixels"] > 0 for character, item in zip(goal, ink)
                       if character != " ")
            key(qmp, "ret")
            if tampered:
                samples = 0
                last_rip = None
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(f"QEMU exited before refusal: {process.returncode}")
                    registers = qmp.hmp("info registers")
                    rip_match = re.search(r"\bRIP=([0-9a-f]+)", registers, re.I)
                    cpl_match = re.search(r"\bCPL=([0-3])", registers)
                    if rip_match and cpl_match:
                        rip, cpl = int(rip_match.group(1), 16), int(cpl_match.group(1))
                        assert cpl != 3, "modified user ELF reached CPL3"
                        data = qmp.dump(request, 4096, "request-refusal.bin", output)
                        user_code = qmp.dump(code, 4096, "code-refusal.bin", output)
                        if (cpl == 0 and 0x100000 <= rip < 0x200000
                                and data[:320] == bytes(320)
                                and user_code[:330] == bytes(330)):
                            samples = samples + 1 if rip == last_rip else 1
                            last_rip = rip
                            if samples >= 12:
                                return {"goal": goal, "cpl": 0, "lastRip": rip,
                                        "refusalSamples": samples,
                                        "userPagesUnchanged": True}
                        else:
                            samples = 0
                    time.sleep(.2)
                raise AssertionError("modified user slot refusal endpoint unavailable")
            endpoint = None
            deadline = time.monotonic() + 35
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"QEMU exited before CPL3 endpoint: {process.returncode}")
                registers = qmp.hmp("info registers")
                (output / "registers-last.txt").write_text(registers)
                rip_match = re.search(r"\bRIP=([0-9a-f]+)", registers, re.I)
                cpl_match = re.search(r"\bCPL=([0-3])", registers)
                request_bytes = qmp.dump(request, 4096, "request-after.bin", output)
                result = struct.unpack_from("<Q", request_bytes)[0]
                if rip_match and cpl_match:
                    rip, cpl = int(rip_match.group(1), 16), int(cpl_match.group(1))
                    if result == len(goal) and cpl == 3 and code + 31 <= rip <= code + 35:
                        endpoint = {"rip": rip, "cpl": cpl, "result": result}
                        break
                time.sleep(.2)
            if endpoint is None:
                raise AssertionError("live Goal did not reach the Kotoba CPL3 endpoint")
            qmp.call("stop")
            actual_code = qmp.dump(code, 4096, "code.bin", output)
            actual_request = qmp.dump(request, 4096, "request-final.bin", output)
            expected_region = struct.pack("<I", len(goal)) + goal.encode("ascii") + bytes(60-len(goal))
            assert actual_code[:330] == elf_bytes[4096:4426]
            # The compiled program spends one unit of its context fuel and
            # writes the result; the remaining context words stay pinned.
            assert struct.unpack_from("<Q", actual_request, 8)[0] == 255
            assert actual_request[16:88] == elf_bytes[8208:8280]
            assert actual_request[256:320] == expected_region
            return {"goal": goal, "endpoint": endpoint, "ui": final,
                    "inkGlyphs": ink, "events": events,
                    "codeBytesMatchElf": True, "goalRegionMatchesTypedText": True}
        finally:
            if process.poll() is None:
                try:
                    if qmp is not None:
                        qmp.call("quit")
                except (OSError, RuntimeError, TimeoutError):
                    process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            process.stdin.close()
            process.stdout.close()


def main(args):
    if (not args.goals or len(args.goals) > 2
            or any(not re.fullmatch(r"[a-z ]{1,51}", goal) or not goal.strip()
                   for goal in args.goals)
            or len(set(args.goals)) != len(args.goals)):
        raise ValueError("--goals requires one or two distinct nonempty lowercase Goals")
    if (args.inline is None) == (args.slot is None):
        raise ValueError("choose exactly one of --inline or --slot")
    files = [args.kernel, args.efi, args.elf, args.font, args.source,
             args.inline if args.inline else args.slot]
    if any(p.is_symlink() or not p.is_file() for p in files):
        raise ValueError("all source and artifact files must be regular, not symlinks")
    if args.output.exists():
        raise ValueError("output must be a new private directory")
    elf = args.elf.read_bytes()
    if hashlib.sha256(elf).hexdigest() != ELF_SHA256:
        raise ValueError("Amu user-v2 ELF pin mismatch")
    kernel, efi, font = (p.read_bytes() for p in (args.kernel, args.efi, args.font))
    if efi.count(kernel) != 1 or efi.count(font) != 1:
        raise ValueError("EFI must contain the exact kernel and font once")
    slot = None
    if args.inline:
        generator = import_file("inline_generator", "generate-native-v2-inline.py")
        if args.inline.read_text() != generator.render(elf):
            raise ValueError("inline source does not match the pinned ELF")
    else:
        slot = args.slot.read_bytes()
        if (len(slot) != 524288
                or struct.unpack_from("<QQQ", slot) != (0x0031444c50554941, 2, len(elf))
                or slot[64:64+len(elf)] != elf or any(slot[64+len(elf):])
                or efi.count(slot) != 1
                or efi.index(slot) != efi.index(font) + 524288):
            raise ValueError("dual EFI user slot is not the pinned Amu ELF after the font")
    header = struct.unpack_from("<IIQQQQQQ", kernel, 120)
    if header[:3] != (1, 6, 1048576) or header[3] != 0x200000:
        raise ValueError("unexpected native context layout")
    context = header[3]
    code, request = context + 0x20000, context + 0x21000
    if struct.unpack_from("<Q", elf, 24)[0] != code:
        raise ValueError("user ELF code address mismatch")
    args.qemu = args.qemu.resolve(strict=True)
    args.firmware = args.firmware.resolve(strict=True)
    args.output.mkdir(mode=0o700)
    qmp_type = import_file("scalar_qmp", "check-native-user-scalar-qemu.py").QMP
    boots = [run_boot(qmp_type, args, args.output / f"goal-{index}", context,
                      code, request, elf, goal, font, efi)
             for index, goal in enumerate(args.goals, 1)]
    empty = run_boot(qmp_type, args, args.output / "empty-goal", context,
                     code, request, elf, "", font, efi)
    modified = None
    if slot is not None:
        changed = bytearray(efi)
        changed[efi.index(slot) + 64 + 4096 + 20] ^= 1
        if sum(a != b for a, b in zip(efi, changed)) != 1:
            raise ValueError("expected one changed user ELF code byte")
        modified = run_boot(qmp_type, args, args.output / "modified-slot", context,
                            code, request, elf, "a b", font, bytes(changed), tampered=True)
    report = {"schema": "aiueos.native-user-v2-live-goal-qemu.v2",
              "status": ("PASS_NATIVE_DUAL_PAYLOAD_ITONAMI_GOAL_CPL3_AND_REFUSALS"
                         if slot is not None else
                         "PASS_NATIVE_ITONAMI_GOAL_TO_USER_V2_CPL3_AND_EMPTY_REFUSAL"),
              "kernel": pin(args.kernel), "efi": pin(args.efi), "elf": pin(args.elf),
              "font": pin(args.font), "source": pin(args.source),
              "inline": pin(args.inline) if args.inline else None,
              "generator": pin(HERE / "generate-native-v2-inline.py") if args.inline else None,
              "userSlot": pin(args.slot) if args.slot else None,
              "observer": pin(Path(__file__)),
              "qemu": pin(args.qemu), "firmware": pin(args.firmware),
              "context": context, "codePage": code, "requestPage": request,
              "boots": boots, "emptyGoalRefusal": empty,
              "modifiedSlotRefusal": modified,
              "qmpTransport": "private-stdio", "vncUsed": False,
              "networkUsed": False, "guestSignatureAdmission": False,
              "modelOrToolOperation": False, "durableTurn": False,
              "releaseAdmission": False, "physicalHardware": False}
    (args.output / "native-user-v2-live-goal-qemu.json").write_text(
        json.dumps(report, indent=2) + "\n")
    print(report["status"], [item["endpoint"]["result"] for item in boots])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "efi", "elf", "font", "source", "qemu", "firmware", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--inline", type=Path)
    parser.add_argument("--slot", type=Path)
    parser.add_argument("--goals", nargs="+", default=["a b", "hello"])
    main(parser.parse_args())
