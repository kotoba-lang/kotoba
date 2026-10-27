#!/usr/bin/env python3
"""Build the padded AIUEOS font with Mac Kotoba/Amu native executables.

Python stages and observes bytes. Amu compiles; the Kotoba packager emits a
Mach-O wrapper; the signed native font program performs padding.
"""
import argparse
import hashlib
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
    data = path.read_bytes()
    if len(data) < 32 or struct.unpack_from("<IiiI", data) != (0xfeedfacf, 0x100000c, 0, 2):
        raise ValueError("image is not an arm64 Mach-O executable")
    subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(path)],
                   check=True, capture_output=True)
    dependencies = subprocess.run(["/usr/bin/otool", "-L", str(path)],
                                  check=True, capture_output=True).stdout.splitlines()
    if dependencies != [f"{path}:".encode()]:
        raise ValueError("image has undeclared dylib dependencies")


def main(args):
    if platform.system() != "Darwin" or platform.machine() not in ("arm64", "aarch64"):
        raise ValueError("this builder requires Apple Silicon")
    compiler = args.compiler_image.resolve(strict=True)
    packager = args.packager_image.resolve(strict=True)
    verify_macho(compiler, args.compiler_sha256)
    verify_macho(packager, args.packager_sha256)
    source_root = args.amu_source.resolve(strict=True)
    font = args.font.resolve(strict=True)
    if args.font.is_symlink() or not font.is_file():
        raise ValueError("font source must be a regular file")
    original = pin(font)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    state = {"schema": "aiueos.macos-native-font-candidate.v1", "state": "STAGING",
             "compiler": pin(compiler), "packager": pin(packager), "original": original,
             "linuxJVMNodeOrCCompiler": False, "calls": []}

    def save():
        (output / "native-font.json").write_text(json.dumps(state, indent=2) + "\n")

    save()
    try:
        parts = [source_root / "seed/00-ns-static.kotoba", source_root / "seed/01-mem.kotoba",
                 source_root / "seed/02-io.kotoba", HERE.parent / "native/font-pad.kotoba"]
        state["sourceParts"] = [{"name": p.name, **pin(p)} for p in parts]
        (output / "font-pad.kotoba").write_bytes(b"".join(p.read_bytes() + b"\n" for p in parts))
        state["sourceUnity"] = pin(output / "font-pad.kotoba")
        shutil.copyfile(font, output / "original.fnt")
        scope = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
        if scope != 3:
            os.dup2(scope, 3)
            os.close(scope)
            scope = 3

        def run(name, command):
            result = subprocess.run(list(map(str, command)), cwd=output, pass_fds=(scope,),
                                    capture_output=True, timeout=300, env={"PATH": "/nonexistent"})
            (output / f"{name}.stdout").write_bytes(result.stdout)
            (output / f"{name}.stderr").write_bytes(result.stderr)
            state["calls"].append({"name": name, "exit": result.returncode,
                                   "stdout": pin(output / f"{name}.stdout"),
                                   "stderr": pin(output / f"{name}.stderr")})
            save()
            if result.returncode or result.stderr:
                state["state"] = "BLOCKED_" + name.upper().replace("-", "_")
                raise ValueError(f"{name}: native exit {result.returncode}: "
                                 + result.stderr.decode(errors="replace")[:400])
            return result.stdout

        try:
            run("compile", [compiler, "compile", "font-pad.kotoba", "--target", "aarch64-macos",
                            "--output", "font-pad.kseed"])
            extracted = run("extract", [compiler, "extract-native", "font-pad.kseed",
                                        "--symbol", "main", "--output", "font-pad.raw"])
            match = re.search(rb":offset (\d+), :length (\d+), :arity 0\}", extracted)
            if not match or int(match.group(2)) != pin(output / "font-pad.raw")["bytes"]:
                raise ValueError("native main extraction is missing or inconsistent")
            run("package", [packager, "font-pad-unsigned.macho", "font-pad.raw",
                            "fs2-cli-stdio-general", match.group(1).decode("ascii")])
            signed = output / "font-pad.macho"
            shutil.copyfile(output / "font-pad-unsigned.macho", signed)
            signed.chmod(0o755)
            subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(signed)],
                           check=True, capture_output=True)
            verify_macho(signed, pin(signed)["sha256"])
            run("pad", [signed, "original.fnt", "aiueos-padded.fnt"])
            raw = font.read_bytes()
            padded = (output / "aiueos-padded.fnt").read_bytes()
            magic, version, count, reserved = struct.unpack_from("<4I", raw)
            if (magic, version, reserved) != (0x46554941, 1, 0) or not (0 < count <= 14563):
                raise ValueError("source font header is invalid")
            if len(raw) != 16 + count * 36 or len(padded) != 524288:
                raise ValueError("source or padded font size is invalid")
            codepoints = [struct.unpack_from("<I", raw, 16 + i * 4)[0] & 0xffffff
                          for i in range(count)]
            if codepoints != sorted(set(codepoints)) or 0xfffd not in codepoints:
                raise ValueError("font codepoint table is invalid")
            if padded[:len(raw)] != raw or any(padded[len(raw):]) or pin(font) != original:
                raise ValueError("native padding or source readback differs")
            if (pin(output / "original.fnt") != original
                    or pin(compiler)["sha256"] != args.compiler_sha256
                    or pin(packager)["sha256"] != args.packager_sha256
                    or any(pin(path) != {key: value for key, value in row.items() if key != "name"}
                           for path, row in zip(parts, state["sourceParts"]))):
                raise ValueError("font compiler, packager or source input changed")
            state.update(state="MACOS_NATIVE_FONT_CANDIDATE", tool=pin(signed),
                         container=pin(output / "font-pad.kseed"),
                         raw=pin(output / "font-pad.raw"), padded=pin(output / "aiueos-padded.fnt"),
                         glyphs=count)
            save()
            print(state["state"], count, "glyphs", state["padded"]["sha256"])
        finally:
            os.close(scope)
    except Exception as error:
        if not state["state"].startswith("BLOCKED_"):
            state["state"] = "BLOCKED_INPUT_OR_BUILD"
        state["error"] = str(error)
        save()
        raise


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--amu-source", type=Path, required=True)
    p.add_argument("--compiler-image", type=Path, required=True)
    p.add_argument("--compiler-sha256", required=True)
    p.add_argument("--packager-image", type=Path, required=True)
    p.add_argument("--packager-sha256", required=True)
    p.add_argument("--font", type=Path, default=HERE.parent / "fonts/aiueos-16.fnt")
    p.add_argument("--output", type=Path, required=True)
    main(p.parse_args())
