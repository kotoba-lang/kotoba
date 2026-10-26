#!/usr/bin/env python3
"""Build and verify AIUEOS diagnostic media with Mac Kotoba/Amu executables.

Python stages immutable inputs, checks provenance, launches native programs,
and independently reads the result. Kotoba emits and verifies the disk bytes.
This is a VM diagnostic image, never a physical-disk installer.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess


HERE = Path(__file__).resolve().parent


def pin(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def verify_macho(path, expected):
    if pin(path)["sha256"] != expected:
        raise ValueError("Mac native image digest mismatch")
    raw = path.read_bytes()
    if len(raw) < 32 or struct.unpack_from("<IiiI", raw) != (0xfeedfacf, 0x100000c, 0, 2):
        raise ValueError("image is not an arm64 Mach-O executable")
    subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(path)],
                   check=True, capture_output=True)
    linked = subprocess.run(["/usr/bin/otool", "-L", str(path)],
                            check=True, capture_output=True).stdout.splitlines()
    if linked != [f"{path}:".encode()]:
        raise ValueError("image has undeclared dylib dependencies")


def main(args):
    if platform.system() != "Darwin" or platform.machine() not in ("arm64", "aarch64"):
        raise ValueError("this builder requires Apple Silicon")
    for name in ("amu_source", "compiler_image", "packager_image", "efi"):
        if getattr(args, name).is_symlink():
            raise ValueError(name + " must not be a symlink")
    amu = args.amu_source.resolve(strict=True)
    compiler = args.compiler_image.resolve(strict=True)
    packager = args.packager_image.resolve(strict=True)
    efi = args.efi.resolve(strict=True)
    if not amu.is_dir() or not efi.is_file():
        raise ValueError("Amu source and EFI must be a directory and regular file")
    verify_macho(compiler, args.compiler_sha256)
    verify_macho(packager, args.packager_sha256)
    original_efi = pin(efi)
    if original_efi["sha256"] != args.efi_sha256 or not (512 <= original_efi["bytes"] <= 6291456):
        raise ValueError("EFI digest or size mismatch")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    state = {
        "schema": "aiueos.macos-native-media-candidate.v1", "state": "STAGING",
        "compiler": pin(compiler), "packager": pin(packager), "efi": original_efi,
        "linuxJVMNodeOrCCompiler": False, "nativeFormatEmission": False,
        "qemuBootQualified": False, "physicalHardwareQualified": False, "calls": [],
    }

    def save():
        (output / "native-media.json").write_text(json.dumps(state, indent=2) + "\n")

    save()
    try:
        parts = [amu / "seed/00-ns-static.kotoba", amu / "seed/01-mem.kotoba",
                 amu / "seed/02-io.kotoba", HERE.parent / "native/media-builder.kotoba"]
        for source in parts:
            if source.is_symlink() or not source.is_file():
                raise ValueError("source is missing or a symlink: " + str(source))
        identities = [{"name": source.name, **pin(source)} for source in parts]
        (output / "media.kotoba").write_bytes(
            b"".join(source.read_bytes() + b"\n" for source in parts))
        state["sourceParts"] = identities
        state["sourceUnity"] = pin(output / "media.kotoba")
        shutil.copyfile(efi, output / "BOOTX64.EFI")
        if pin(output / "BOOTX64.EFI") != original_efi:
            raise ValueError("staged EFI differs")
        scope = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
        if scope != 3:
            os.dup2(scope, 3)
            os.close(scope)
            scope = 3

        def run(name, command, expected=0):
            result = subprocess.run([str(part) for part in command], cwd=output,
                                    pass_fds=(scope,), capture_output=True, timeout=300,
                                    env={"PATH": "/nonexistent"})
            stdout = output / (name + ".stdout")
            stderr = output / (name + ".stderr")
            stdout.write_bytes(result.stdout)
            stderr.write_bytes(result.stderr)
            state["calls"].append({
                "name": name, "exit": result.returncode,
                "stdout": pin(stdout), "stderr": pin(stderr),
            })
            save()
            if result.returncode != expected or (expected == 0 and result.stderr):
                state["state"] = "BLOCKED_" + name.upper().replace("-", "_")
                raise ValueError(f"{name}: native exit {result.returncode}: "
                                 + result.stderr.decode(errors="replace")[-500:])
            return result.stdout

        try:
            run("compile", [compiler, "compile", "media.kotoba", "--target",
                            "aarch64-macos", "--output", "media.kseed"])
            extracted = run("extract", [compiler, "extract-native", "media.kseed",
                                        "--symbol", "main", "--output", "media.raw"])
            match = re.search(rb":offset (\d+), :length (\d+), :arity 0\}", extracted)
            if not match or int(match.group(2)) != pin(output / "media.raw")["bytes"]:
                raise ValueError("native main extraction is missing or inconsistent")
            run("package", [packager, "media-unsigned.macho", "media.raw",
                            "fs2-cli-stdio-general", match.group(1).decode("ascii")])
            program = output / "media.macho"
            shutil.copyfile(output / "media-unsigned.macho", program)
            program.chmod(0o755)
            subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(program)],
                           check=True, capture_output=True)
            verify_macho(program, pin(program)["sha256"])

            def invoke(name, operation, image, expected=0, source="BOOTX64.EFI",
                       digest=None, size=None):
                return run(name, [program, operation, source, image,
                                  digest or original_efi["sha256"],
                                  str(size if size is not None else original_efi["bytes"])],
                           expected)

            disk = "awai-native.img"
            reproduced = "awai-native.reproduced.img"
            if b"PASS_NATIVE_GPT_FAT16_BUILD" not in invoke("build", "build", disk):
                raise ValueError("native media builder omitted success marker")
            if b"PASS_NATIVE_GPT_FAT16_VERIFY" not in invoke("verify", "verify", disk):
                raise ValueError("native media verifier omitted success marker")
            invoke("reproduce", "build", reproduced)
            if pin(output / disk) != pin(output / reproduced):
                raise ValueError("native media reproduction differed")
            invoke("existing-output", "build", disk, 1)
            invoke("wrong-efi-size", "verify", disk, 1, size=original_efi["bytes"] + 1)
            invoke("wrong-efi-digest", "verify", disk, 1, digest="0" * 64)
            if pin(output / disk) != pin(output / reproduced):
                raise ValueError("negative control modified the disk")

            spec = importlib.util.spec_from_file_location(
                "media_reader", HERE / "check-native-media-format.py")
            reader = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(reader)
            independent = reader.verify(output / disk, output / "BOOTX64.EFI")
            raw = (output / disk).read_bytes()
            offsets = {
                "primary-gpt": 512 + 24, "backup-gpt": len(raw) - 512 + 24,
                "fat-mirror": 1049088 + 4, "directory-name": 1122816 + 576,
                "efi-content": 1123840 + 512,
            }
            for name, offset in offsets.items():
                damaged = bytearray(raw)
                damaged[offset] ^= 1
                path = output / (name + ".img")
                path.write_bytes(damaged)
                invoke(name, "verify", path.name, 1)
                try:
                    reader.verify(path, output / "BOOTX64.EFI")
                except (AssertionError, ValueError, struct.error):
                    pass
                else:
                    raise ValueError("independent reader accepted " + name)
            for name, damaged in (("truncated", raw[:-1]), ("trailer", raw + b"\0")):
                path = output / (name + ".img")
                path.write_bytes(damaged)
                invoke(name, "verify", path.name, 1)
            if (pin(compiler)["sha256"] != args.compiler_sha256
                    or pin(packager)["sha256"] != args.packager_sha256
                    or pin(efi) != original_efi
                    or pin(output / "BOOTX64.EFI") != original_efi
                    or pin(output / "media.kotoba") != state["sourceUnity"]
                    or any(pin(path) != {k: v for k, v in identity.items() if k != "name"}
                           for path, identity in zip(parts, identities))
                    or pin(output / disk) != pin(output / reproduced)):
                raise ValueError("source, executable or media drift")
            state.update(state="MACOS_NATIVE_MEDIA_CANDIDATE", tool=pin(program),
                         container=pin(output / "media.kseed"), raw=pin(output / "media.raw"),
                         image=pin(output / disk), independentMedia=independent,
                         refusalCases=10, nativeFormatEmission=True,
                         qualification="Mac native media build and format verification; QEMU and release separate")
            save()
            print(state["state"], state["image"]["sha256"])
        finally:
            os.close(scope)
    except Exception as error:
        if not state["state"].startswith("BLOCKED_"):
            state["state"] = "BLOCKED_INPUT_OR_BUILD"
        state["error"] = str(error)
        save()
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amu-source", type=Path, required=True)
    parser.add_argument("--compiler-image", type=Path, required=True)
    parser.add_argument("--compiler-sha256", required=True)
    parser.add_argument("--packager-image", type=Path, required=True)
    parser.add_argument("--packager-sha256", required=True)
    parser.add_argument("--efi", type=Path, required=True)
    parser.add_argument("--efi-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
