#!/usr/bin/env python3
"""Observe Amu-emitted scalar code at CPL3 in the C-free AIUEOS kernel.

QMP stays on private stdio pipes. The guest does not parse or admit the ELF;
the source/artifact comparator independently checks the staged code bytes.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import select
import shutil
import struct
import subprocess
import time


def pin(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


class QMP:
    def __init__(self, process):
        self.process = process
        self.next_id = 0
        assert "QMP" in self._read(15), "QMP greeting unavailable"
        self.call("qmp_capabilities")

    def _read(self, timeout):
        if not select.select([self.process.stdout], [], [], timeout)[0]:
            raise TimeoutError("QMP response timed out")
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f"QEMU closed QMP: {self.process.poll()}")
        return json.loads(line)

    def call(self, command, arguments=None):
        self.next_id += 1
        row = {"execute": command, "id": self.next_id}
        if arguments is not None:
            row["arguments"] = arguments
        self.process.stdin.write(json.dumps(row).encode() + b"\n")
        self.process.stdin.flush()
        while True:
            answer = self._read(10)
            if answer.get("id") == self.next_id:
                if "error" in answer:
                    raise RuntimeError(answer)
                return answer["return"]

    def hmp(self, command):
        return self.call("human-monitor-command", {"command-line": command})

    def dump(self, address, size, filename, output):
        assert self.hmp(f"pmemsave 0x{address:x} {size} {filename}") == ""
        raw = (output / filename).read_bytes()
        assert len(raw) == size
        return raw


def observe(args):
    output = args.output.resolve()
    if output.exists():
        raise ValueError("output must be a new private directory")
    if any(p.is_symlink() or not p.is_file()
           for p in (args.kernel, args.efi, args.elf, args.source)):
        raise ValueError("kernel, EFI, ELF and source must be regular non-symlink files")
    kernel = args.kernel.resolve(strict=True)
    efi = args.efi.resolve(strict=True)
    scalar = args.elf.resolve(strict=True)
    source = args.source.resolve(strict=True)
    qemu = args.qemu.resolve(strict=True)
    firmware = args.firmware.resolve(strict=True)
    spec = importlib.util.spec_from_file_location(
        "scalar_source", Path(__file__).with_name("verify-native-user-scalar-source.py"))
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    expected_code = verifier.verify(source, scalar)
    image = kernel.read_bytes()
    assert efi.read_bytes().count(image) == 1, "EFI must contain exact kernel once"
    rw = struct.unpack_from("<IIQQQQQQ", image, 120)
    assert rw[0] == 1 and rw[1] == 6 and rw[5] == 0x240000
    context = rw[3]
    code = context + 0x20000
    request = code + 4096
    output.mkdir(parents=True, mode=0o700)
    esp = output / "esp/EFI/BOOT"
    esp.mkdir(parents=True)
    shutil.copy2(efi, esp / "BOOTX64.EFI")
    command = [str(qemu), "-machine", "q35,accel=tcg", "-cpu", "max",
               "-m", "128M", "-smp", "1",
               "-drive", f"if=pflash,format=raw,readonly=on,file={firmware}",
               "-drive", "file=fat:rw:esp,format=raw", "-boot", "order=c",
               "-nic", "none", "-display", "none", "-no-reboot",
               "-serial", "file:serial.log", "-debugcon", "file:debug.log",
               "-qmp", "stdio"]
    with (output / "qemu.stderr").open("wb") as log:
        process = subprocess.Popen(command, cwd=output, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=log, bufsize=0)
        qmp = None
        try:
            qmp = QMP(process)
            deadline = time.monotonic() + 45
            endpoint = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"QEMU exited: {process.returncode}")
                registers = qmp.hmp("info registers")
                (output / "registers-last.txt").write_text(registers)
                rip_match = re.search(r"\bRIP=([0-9a-f]+)", registers, re.I)
                if rip_match is None:
                    time.sleep(.25)
                    continue
                rip = int(rip_match.group(1), 16)
                cpl_match = re.search(r"\bCPL=([0-3])", registers)
                assert cpl_match is not None
                cpl = int(cpl_match.group(1))
                data = qmp.dump(request, 4096, "request.bin", output)
                result = struct.unpack_from("<Q", data)[0]
                if result == 42 and cpl == 3 and code + 19 <= rip <= code + 23:
                    endpoint = (rip, cpl, result)
                    break
                time.sleep(.25)
            if endpoint is None:
                raise AssertionError("CPL3 scalar result endpoint was not reached")
            qmp.call("stop")
            actual_code = qmp.dump(code, 4096, "code.bin", output)
            assert actual_code[:109] == expected_code
            assert actual_code[109:112] == bytes(3)
            data = qmp.dump(request, 4096, "request.bin", output)
            assert struct.unpack_from("<Q", data)[0] == 42
            report = {
                "schema": "aiueos.native-user-scalar-qemu.v1",
                "status": "PASS_CFREE_USER_SCALAR_CODE_QEMU",
                "kernel": pin(kernel), "efi": pin(efi), "scalarSource": pin(source),
                "scalarElf": pin(scalar), "qemu": pin(qemu), "firmware": pin(firmware),
                "observer": pin(Path(__file__)), "context": context,
                "codePage": code, "requestPage": request,
                "userRip": endpoint[0], "cpl": endpoint[1], "result": endpoint[2],
                "codeBytesMatchCompiledElf": True, "qmpTransport": "private-stdio",
                "vncUsed": False, "networkUsed": False,
                "guestElfParserOrSignatureAdmission": False,
                "registeredItonamiTurn": False, "releaseAdmission": False,
                "physicalHardware": False,
            }
            (output / "native-user-scalar-qemu.json").write_text(
                json.dumps(report, indent=2) + "\n")
            print(report["status"], hex(code), report["result"])
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "efi", "elf", "source", "qemu", "firmware", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    observe(parser.parse_args())
