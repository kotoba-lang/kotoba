#!/usr/bin/env python3
"""Observe a Kotoba guest copying a pinned GPT image to an isolated QEMU disk.

This is a block-mechanism diagnostic. QMP supplies synthetic keys and cannot
qualify human consent, signed release admission, guided install or hardware.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import select
import struct
import subprocess
import time


HERE = Path(__file__).resolve().parent
DISK_BYTES = 8 * 1024 * 1024


def pin(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def sector_chain(path):
    raw = path.read_bytes()
    if len(raw) != DISK_BYTES:
        raise ValueError("sector-chain source must be exactly 8 MiB")
    digest = bytes(32)
    for offset in range(0, DISK_BYTES, 512):
        digest = hashlib.sha256(digest + raw[offset:offset + 512]).digest()
    return digest


class Guest:
    def __init__(self, args, directory, source_copy, target):
        directory.mkdir(mode=0o700)
        self.directory = directory
        self.target = target
        self.log = (directory / "qemu.log").open("wb")
        command = [
            str(args.qemu), "-machine", "q35,accel=tcg", "-cpu", "max",
            "-m", "128M", "-smp", "1",
            "-drive", f"if=pflash,format=raw,readonly=on,file={args.firmware}",
            "-drive", f"file={args.media},format=raw,if=ide,snapshot=on",
            "-device", "isa-ide,id=installer-controller",
            "-drive", f"file={source_copy},format=raw,if=none,id=source,cache=writeback",
            "-device", "ide-hd,drive=source,bus=installer-controller.0,unit=0",
            "-drive", f"file={target},format=raw,if=none,id=target,cache=writeback",
            "-device", "ide-hd,drive=target,bus=installer-controller.0,unit=1",
            "-boot", "order=c", "-nic", "none", "-display", "none",
            "-no-reboot", "-serial", "file:serial.log",
            "-debugcon", "file:debug.log", "-qmp", "stdio",
            "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
        ]
        (directory / "command.json").write_text(json.dumps(command, indent=2) + "\n")
        self.process = subprocess.Popen(
            command, cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.log, bufsize=0)
        self.sequence = 0
        try:
            greeting = self.read_line(15)
            if not greeting or "QMP" not in json.loads(greeting):
                raise AssertionError("QMP greeting absent")
            self.call("qmp_capabilities")
        except BaseException:
            self.close()
            raise

    def read_line(self, timeout):
        if not select.select([self.process.stdout], [], [], timeout)[0]:
            raise TimeoutError("QMP response timed out")
        data = self.process.stdout.readline()
        if not data:
            raise AssertionError(f"QMP closed: {self.process.poll()}")
        return data

    def call(self, name, arguments=None):
        self.sequence += 1
        request = {"execute": name, "id": self.sequence}
        if arguments is not None:
            request["arguments"] = arguments
        self.process.stdin.write(json.dumps(request).encode() + b"\n")
        while True:
            response = json.loads(self.read_line(15))
            if response.get("id") == self.sequence:
                if "error" in response:
                    raise AssertionError(response)
                return response["return"]

    def key(self, code):
        self.call("send-key", {"keys": [{"type": "qcode", "data": code}],
                               "hold-time": 60})
        time.sleep(.12)

    def wait_marker(self, marker, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            raw = (self.directory / "debug.log").read_bytes() if (
                self.directory / "debug.log").exists() else b""
            if marker in raw:
                return raw
            if self.process.poll() is not None:
                raise AssertionError(("guest exited before marker", marker, raw,
                                      self.process.returncode))
            time.sleep(.2)
        raise TimeoutError(("guest marker timed out", marker,
                            (self.directory / "debug.log").read_bytes()))

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.log.close()


def main(args):
    if args.output.exists():
        raise ValueError("output exists")
    if any(path.is_symlink() for path in (args.media, args.efi, args.release_media,
                                         args.release_efi, args.manifest)):
        raise ValueError("linked media input")
    args.qemu = args.qemu.resolve(strict=True)
    args.firmware = args.firmware.resolve(strict=True)
    if (pin(args.qemu)["sha256"] != args.qemu_sha256
            or pin(args.firmware)["sha256"] != args.firmware_sha256):
        raise ValueError("QEMU or firmware digest mismatch")
    installer = pin(args.media)
    source = pin(args.release_media)
    if installer["bytes"] != DISK_BYTES or source["bytes"] != DISK_BYTES:
        raise ValueError("installer and source must be exact native 8 MiB GPT images")
    manifest = args.manifest.read_bytes()
    chain = sector_chain(args.release_media)
    if (len(manifest) != 524288 or manifest[:8] != b"AIUEINS2"
            or struct.unpack_from("<QQ", manifest, 8) != (2, DISK_BYTES)
            or manifest[24:56] != chain):
        raise ValueError("manifest does not bind the release source image")
    if args.efi.read_bytes().count(manifest) != 1:
        raise ValueError("installer EFI does not embed the exact manifest once")
    reader_spec = importlib.util.spec_from_file_location(
        "native_media_reader", HERE / "check-native-media-format.py")
    reader = importlib.util.module_from_spec(reader_spec)
    reader_spec.loader.exec_module(reader)
    media_proof = reader.verify(args.media, args.efi)
    source_proof = reader.verify(args.release_media, args.release_efi)
    args.output.mkdir(parents=True, mode=0o700)
    source_copy = args.output / "source-copy.raw"
    source_copy.write_bytes(args.release_media.read_bytes())
    if pin(source_copy) != source:
        raise AssertionError("staged source differs from release media")
    cases = {}
    for name, size, mark, keys, expected_marker, expected_exit, source_path in (
            ("approved", DISK_BYTES, False, "erase", b"P", 33, source_copy),
            ("denied-key", DISK_BYTES, False, "a", b"N", 35, source_copy),
            ("nonblank-target", DISK_BYTES, True, "", b"E", 37, source_copy),
            ("oversized-target", DISK_BYTES * 2, False, "", b"E", 37, source_copy),
            ("tampered-source", DISK_BYTES, False, "", b"E", 37,
             args.output / "tampered-source.raw"),
            ("truncated-source", DISK_BYTES, False, "", b"E", 37,
             args.output / "truncated-source.raw")):
        if name == "tampered-source":
            raw = bytearray(args.release_media.read_bytes())
            raw[8192] ^= 1
            source_path.write_bytes(raw)
        if name == "truncated-source":
            source_path.write_bytes(args.release_media.read_bytes()[:DISK_BYTES // 2])
        target = args.output / (name + "-target.raw")
        target.write_bytes(bytes(size))
        if mark:
            with target.open("r+b") as stream:
                stream.seek(4096)
                stream.write(b"AIUEOS_TARGET_MUST_BE_BLANK")
        before = pin(target)
        guest = None
        try:
            guest = Guest(args, args.output / name, source_path, target)
            if keys:
                guest.wait_marker(b"R", 300)
                for code in keys:
                    guest.key(code)
            markers = guest.wait_marker(expected_marker, 300)
            guest.process.wait(timeout=10)
            if guest.process.returncode != expected_exit:
                raise AssertionError((name, "unexpected guest status",
                                      guest.process.returncode, markers))
            if any(marker in markers for marker in (b"X", b"Y", b"F")):
                raise AssertionError((name, "source chain failed before comparison", markers))
            if name in ("approved", "denied-key") and b"HR" not in markers:
                raise AssertionError((name, "source was not fully admitted", markers))
            if name == "tampered-source" and b"HDE" not in markers:
                raise AssertionError((name, "digest mismatch was not observed", markers))
        finally:
            if guest:
                guest.close()
        after = pin(target)
        if name == "approved":
            if after != source:
                raise AssertionError("guest target is not byte-identical to source")
        elif after != before:
            raise AssertionError((name, "rejected target changed"))
        if (pin(args.media) != installer or pin(args.release_media) != source
                or pin(source_copy) != source):
            raise AssertionError((name, "guest changed source media"))
        cases[name] = {"source": pin(source_path), "targetBefore": before,
                       "targetAfter": after, "guestMarkers": markers.decode("latin1"),
                       "exitCode": expected_exit}
    receipt = {
        "schema": "aiueos.native-install-copy-qemu.v2",
        "status": "PASS_NATIVE_GUEST_SOURCE_ADMISSION_DIAGNOSTIC",
        "installerMedia": installer,
        "source": source,
        "sourceSectorChainRoot": chain.hex(),
        "manifest": pin(args.manifest),
        "stagedATABootCopy": pin(source_copy),
        "target": cases["approved"]["targetAfter"],
        "independentMedia": media_proof,
        "independentSourceMedia": source_proof,
        "observer": pin(Path(__file__)),
        "cases": cases,
        "qmpKeysAreTrustedApproval": False,
        "signedReleaseAdmission": False,
        "guidedInstallerQualified": False,
        "physicalHardwareQualified": False,
    }
    (args.output / "native-install-copy-qemu.json").write_text(
        json.dumps(receipt, indent=2) + "\n")
    print(receipt["status"], len(cases), "cases", receipt["target"]["sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("media", "efi", "release-media", "release-efi",
                 "manifest", "qemu", "firmware", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--qemu-sha256", required=True)
    parser.add_argument("--firmware-sha256", required=True)
    main(parser.parse_args())
