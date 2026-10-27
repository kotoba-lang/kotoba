#!/usr/bin/env python3
"""Open a verified native AIUEOS draft in a local Cocoa QEMU window.

This is a Mac development launcher. It owns no guest behavior, compiler,
network service, password, or release admission. The separate draft disk is
kept in the named workspace so closing and reopening the VM restores Goal.
"""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import struct
import subprocess


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"regular file required: {path}")
    return path


def pinned(path, pin):
    regular(path)
    if path.stat().st_size != pin.get("bytes") or sha256(path) != pin.get("sha256"):
        raise ValueError(f"artifact digest mismatch: {path}")


def github_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "github":
            return parent
    raise ValueError("launcher is outside the canonical github workspace")


def session_workspace(raw):
    root = github_root() / "workspaces"
    path = raw.expanduser().absolute()
    if ".." in path.parts or root not in path.parents or path == root:
        raise ValueError("workspace must be a directory below github/workspaces")
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError("workspace path must not contain a symlink")
    if path.exists() and not path.is_dir():
        raise ValueError("workspace is not a directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_mode & 0o077:
        raise ValueError("workspace must be private (mode 0700)")
    return path


def draft_disk(path):
    if not path.exists():
        data = bytearray(128 * 512)
        struct.pack_into("<4I", data, 0, 0x49415741, 0x54465244, 1, 128)
        with path.open("xb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        path.chmod(0o600)
    regular(path)
    if path.stat().st_size != 128 * 512 or path.stat().st_mode & 0o077:
        raise ValueError("draft disk has an unexpected size or mode")
    with path.open("rb") as source:
        if source.read(16) != struct.pack("<4I", 0x49415741, 0x54465244, 1, 128):
            raise ValueError("draft disk marker mismatch")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_dir", type=Path, help="completed Mac native desktop build")
    parser.add_argument("--workspace", type=Path, required=True,
                        help="private persistent directory below github/workspaces")
    parser.add_argument("--display", choices=("cocoa", "none"), default="cocoa")
    parser.add_argument("--qemu", type=Path)
    parser.add_argument("--firmware", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="verify pins and print the command only")
    args = parser.parse_args()
    if platform.system() != "Darwin":
        parser.error("the local Cocoa launcher requires macOS")
    os.umask(0o077)
    build = args.build_dir.expanduser().resolve(strict=True)
    receipt = regular(build / "native-desktop-macos.json")
    candidate = json.loads(receipt.read_text())
    if (candidate.get("state") != "MACOS_NATIVE_DRAFT_RESTORE_QEMU_CANDIDATE"
            or candidate.get("profile") != "local-draft"
            or candidate.get("linuxJVMNodeOrCCompiler") is not False
            or candidate.get("localDraftRestoreQualified") is not True):
        parser.error("build is not a verified Mac native local-draft candidate")
    media = build / "media" / "awai-native.img"
    pinned(media, candidate["media"])
    pinned(build / "kernel" / "KERNEL.ELF", candidate["kernel"])
    pinned(build / "kernel" / "BOOTX64.EFI", candidate["efi"])
    pinned(build / "font" / "aiueos-padded.fnt", candidate["font"])
    found_qemu = shutil.which("qemu-system-x86_64")
    if args.qemu is None and found_qemu is None:
        parser.error("qemu-system-x86_64 is unavailable")
    qemu = (args.qemu or Path(found_qemu)).expanduser().resolve(strict=True)
    firmware = (args.firmware or Path("/opt/homebrew/share/qemu/edk2-x86_64-code.fd")).expanduser().resolve(strict=True)
    pinned(qemu, candidate["qemu"])
    pinned(firmware, candidate["firmware"])
    workspace = session_workspace(args.workspace)
    lock = workspace / ".session.lock"
    if lock.is_symlink():
        raise ValueError("session lock must not be a symlink")
    with lock.open("a+b") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("a VM is already using this workspace") from exc
        identity = {"schema": "aiueos.local-native-desktop-session.v1",
                    "buildReceiptSha256": sha256(receipt), "mediaSha256": sha256(media),
                    "qemuSha256": sha256(qemu), "firmwareSha256": sha256(firmware),
                    "distribution": candidate["distribution"]["id"], "profile": "local-draft"}
        marker = workspace / "session.json"
        if marker.exists():
            regular(marker)
            if json.loads(marker.read_text()) != identity:
                raise ValueError("workspace belongs to a different native build")
        elif not args.dry_run:
            with marker.open("x") as target:
                json.dump(identity, target, indent=2)
                target.write("\n")
        disk = workspace / "draft.raw"
        if not args.dry_run:
            draft_disk(disk)
        runs = workspace / "runs"
        if not args.dry_run:
            if runs.is_symlink() or (runs.exists() and not runs.is_dir()):
                raise ValueError("runs must be a directory, not a symlink")
            runs.mkdir(mode=0o700, exist_ok=True)
            if runs.stat().st_mode & 0o077:
                raise ValueError("runs directory must be private (mode 0700)")
        index = 1
        while (runs / f"{index:04d}").exists():
            index += 1
        run = runs / f"{index:04d}"
        if not args.dry_run:
            run.mkdir(mode=0o700)
        command = [str(qemu), "-machine", "q35,accel=tcg", "-cpu", "max",
                   "-m", "128M", "-smp", "1",
                   "-drive", f"if=pflash,format=raw,readonly=on,file={firmware}",
                   "-drive", f"file={media},format=raw,if=ide,snapshot=on",
                   "-boot", "order=c", "-nic", "none", "-display", args.display,
                   "-no-reboot", "-monitor", "none",
                   "-serial", f"file:{run / 'serial.log'}",
                   "-debugcon", f"file:{run / 'debug.log'}",
                   "-device", "isa-ide,id=draft-controller",
                   "-drive", f"file={disk},format=raw,if=none,id=draft,cache=directsync",
                   "-device", "ide-hd,drive=draft,bus=draft-controller.0,unit=1,serial=AWAI90DRAFT000001"]
        if args.dry_run:
            print(json.dumps({"verified": True, "workspace": str(workspace),
                              "command": command, "identity": identity}, indent=2))
            return
        with (run / "qemu.stderr").open("wb") as stderr:
            process = subprocess.Popen(command, cwd=run, stdout=subprocess.DEVNULL,
                                       stderr=stderr, start_new_session=True)
            try:
                print(json.dumps({"pid": process.pid, "workspace": str(workspace),
                                  "run": str(run), "display": args.display}), flush=True)
                process.wait()
            except KeyboardInterrupt:
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=15)
            if process.returncode not in (0, -signal.SIGTERM):
                raise SystemExit(process.returncode)
        pinned(media, candidate["media"])


if __name__ == "__main__":
    main()
