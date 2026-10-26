#!/usr/bin/env python3
"""Prove pinned boot-slot ELF execution and digest refusal in private QEMU.

This is a diagnostic whole-image admission gate, not signature or release
authority. QMP uses stdio; no VNC, network, login, or guest input is needed.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time


def pin(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def qmp_class():
    source = Path(__file__).with_name("check-native-user-scalar-qemu.py")
    spec = importlib.util.spec_from_file_location("scalar_qmp", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.QMP


def boot(qmp_type, directory, efi_bytes, firmware, qemu, code, request,
         expected_code, negative):
    directory.mkdir(mode=0o700)
    esp = directory / "esp/EFI/BOOT"
    esp.mkdir(parents=True)
    (esp / "BOOTX64.EFI").write_bytes(efi_bytes)
    command = [str(qemu), "-machine", "q35,accel=tcg", "-cpu", "max",
               "-m", "128M", "-smp", "1",
               "-drive", f"if=pflash,format=raw,readonly=on,file={firmware}",
               "-drive", "file=fat:rw:esp,format=raw", "-boot", "order=c",
               "-nic", "none", "-display", "none", "-no-reboot",
               "-serial", "file:serial.log", "-debugcon", "file:debug.log",
               "-qmp", "stdio"]
    with (directory / "qemu.stderr").open("wb") as log:
        process = subprocess.Popen(command, cwd=directory, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=log, bufsize=0)
        qmp = None
        try:
            qmp = qmp_type(process)
            deadline = time.monotonic() + (25 if negative else 50)
            kernel_refusal_samples = 0
            refusal_rip = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"QEMU exited before endpoint: {process.returncode}")
                registers = qmp.hmp("info registers")
                (directory / "registers-last.txt").write_text(registers)
                rip_match = re.search(r"\bRIP=([0-9a-f]+)", registers, re.I)
                cpl_match = re.search(r"\bCPL=([0-3])", registers)
                if rip_match is None or cpl_match is None:
                    time.sleep(.25)
                    continue
                rip = int(rip_match.group(1), 16)
                cpl = int(cpl_match.group(1))
                result = struct.unpack_from(
                    "<Q", qmp.dump(request, 4096, "request.bin", directory))[0]
                if negative:
                    assert cpl != 3 and result != 42, (
                        f"modified payload admitted: {hex(rip)} CPL{cpl} result={result}")
                    if 0x100000 <= rip < 0x200000 and cpl == 0 and result == 0:
                        kernel_refusal_samples = (kernel_refusal_samples + 1
                                                  if rip == refusal_rip else 1)
                        refusal_rip = rip
                    else:
                        kernel_refusal_samples = 0
                    if kernel_refusal_samples >= 12:
                        return {"kernelRefusalSamples": kernel_refusal_samples,
                                "lastRip": rip, "cpl": cpl, "result": result}
                elif result == 42 and cpl == 3 and code + 19 <= rip <= code + 23:
                    qmp.call("stop")
                    actual = qmp.dump(code, 4096, "code.bin", directory)
                    assert actual[:len(expected_code)] == expected_code
                    assert actual[len(expected_code):len(expected_code) + 3] == bytes(3)
                    return {"userRip": rip, "cpl": cpl, "result": result,
                            "codeBytesMatchCompiledElf": True}
                time.sleep(.3)
            raise AssertionError("guest endpoint not reached before timeout")
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


def verify(args):
    paths = [args.kernel, args.efi, args.elf, args.slot]
    if any(p.is_symlink() or not p.is_file() for p in paths + [args.source]):
        raise ValueError("artifact and source inputs must be regular non-symlink files")
    if not args.qemu.resolve(strict=True).is_file() or not args.firmware.resolve(strict=True).is_file():
        raise ValueError("QEMU and firmware must resolve to files")
    if args.output.exists():
        raise ValueError("output must be a new private directory")
    kernel, efi, elf, slot = (p.read_bytes() for p in paths[:4])
    assert len(slot) == 524288
    assert struct.unpack_from("<QQQ", slot) == (0x0031444c50554941, 1, len(elf))
    assert slot[64:64 + len(elf)] == elf and not any(slot[64 + len(elf):])
    assert efi.count(kernel) == 1 and efi.count(slot) == 1
    assert struct.unpack_from("<Q", elf, 0)[0] == 0x00010102464c457f
    header = struct.unpack_from("<IIQQQQQQ", kernel, 120)
    assert header[0:3] == (1, 6, 1048576)
    context = header[3]
    code, request = context + 0x20000, context + 0x21000
    assert context == 0x200000
    assert struct.unpack_from("<Q", elf, 24)[0] == code
    assert struct.unpack_from("<Q", elf, 80)[0] == code
    assert struct.unpack_from("<Q", elf, 136)[0] == request
    assert len(elf) == 8280
    args.output.mkdir(mode=0o700)
    qmp_type = qmp_class()
    positive = boot(qmp_type, args.output / "positive", efi,
                    args.firmware.resolve(), args.qemu.resolve(), code,
                    request, elf[4096:4205], False)
    changed = bytearray(efi)
    changed[efi.index(slot) + 64 + 4096 + 20] ^= 1
    assert sum(a != b for a, b in zip(efi, changed)) == 1
    negative = boot(qmp_type, args.output / "negative", changed,
                    args.firmware.resolve(), args.qemu.resolve(), code,
                    request, elf[4096:4205], True)
    bad_header = bytearray(efi)
    bad_header[efi.index(slot)] ^= 1
    assert sum(a != b for a, b in zip(efi, bad_header)) == 1
    header_refusal = boot(qmp_type, args.output / "invalid-slot-header",
                          bad_header, args.firmware.resolve(),
                          args.qemu.resolve(), code, request,
                          elf[4096:4205], True)
    report = {
        "schema": "aiueos.native-user-payload-qemu.v2",
        "status": "PASS_CFREE_ELF_BOOT_SLOT_AND_TWO_REFUSALS",
        "kernel": pin(args.kernel), "efi": pin(args.efi),
        "elf": pin(args.elf), "slot": pin(args.slot),
        "source": pin(args.source), "qemu": pin(args.qemu),
        "firmware": pin(args.firmware), "observer": pin(Path(__file__)),
        "context": context, "codePage": code, "requestPage": request,
        "positive": positive, "modifiedPayloadRefusal": negative,
        "invalidSlotHeaderRefusal": header_refusal,
        "qmpTransport": "private-stdio", "vncUsed": False,
        "networkUsed": False, "guestSignatureAdmission": False,
        "registeredItonamiTurn": False, "releaseAdmission": False,
        "physicalHardware": False,
    }
    (args.output / "native-user-payload-qemu.json").write_text(
        json.dumps(report, indent=2) + "\n")
    print(report["status"], hex(code), positive["result"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "efi", "elf", "slot", "source", "qemu",
                 "firmware", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    verify(parser.parse_args())
