#!/usr/bin/env python3
"""Build the proposed AIUEOS LLM header validator with a pinned Mac Amu image.

This is a source/ELF/refusal gate. It does not execute the object in AIUEOS.
Python stages files and observes the native compiler; it is not an OS runtime.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys


SOURCE = Path(__file__).resolve().parents[1] / "native/llm_v1_header.kotoba"
UNROOTED_CALL = "kernel-load-u32 header header-bytes 12"


def pin(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def run_compiler(image, output, source, name, expected):
    directory_fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
    saved = None
    relocated = directory_fd != 3
    try:
        if relocated:
            try:
                saved = os.dup(3)
            except OSError:
                pass
            os.dup2(directory_fd, 3)
        result = subprocess.run(
            [str(image), "compile", source, "--target", "x86_64-aiueos-kernel-v1",
             "--output", name], cwd=output, capture_output=True, pass_fds=(3,),
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "TMPDIR": str(output),
                 "TMP": str(output), "TEMP": str(output)}, timeout=1200,
            check=False)
    finally:
        if relocated:
            if saved is None:
                os.close(3)
            else:
                os.dup2(saved, 3)
                os.close(saved)
        os.close(directory_fd)
    if result.returncode != expected:
        raise RuntimeError(f"{source}: rc={result.returncode}, expected={expected}: "
                           + result.stderr.decode(errors="replace")[-800:])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler-image", type=Path, required=True)
    parser.add_argument("--compiler-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.compiler_image.is_symlink() or not args.compiler_image.is_file():
        parser.error("compiler must be a regular non-symlink file")
    compiler = args.compiler_image.resolve(strict=True)
    compiler_pin = pin(compiler)
    if compiler_pin["sha256"] != args.compiler_sha256:
        parser.error("compiler digest mismatch")
    signature = subprocess.run(["/usr/bin/codesign", "--verify", "--strict",
                                str(compiler)], capture_output=True, check=False)
    if signature.returncode:
        parser.error("compiler signature verification failed")
    output = args.output.resolve()
    if output.exists():
        parser.error("output must be a new directory")
    output.mkdir(parents=True, mode=0o700)
    source_pin = pin(SOURCE)
    shutil.copyfile(SOURCE, output / "llm-v1-header.kotoba")
    for name in ("header.o", "header-reproduced.o"):
        result = run_compiler(compiler, output, "llm-v1-header.kotoba", name, 0)
        if result.stderr or b":x86_64-aiueos-kernel-v1" not in result.stdout:
            raise RuntimeError("native kernel object compiler did not report success")
    image = (output / "header.o").read_bytes()
    if (image != (output / "header-reproduced.o").read_bytes()
            or len(image) < 512 or image[:4] != b"\x7fELF"
            or struct.unpack_from("<HH", image, 16) != (1, 62)):
        raise RuntimeError("native object changed or is not x86_64 ELF ET_REL")
    object_check = subprocess.run(
        [sys.executable, "-I", str(Path(__file__).with_name(
            "verify-kotoba-kernel-object.py")), str(output / "header.o"),
         pin(output / "header.o")["sha256"], "aiueos-llm-v1-header-valid"],
        capture_output=True, check=False, timeout=30)
    if (object_check.returncode or
            b"imports=0 relocations=1" not in object_check.stdout):
        raise RuntimeError("native object ABI verification failed")
    text = SOURCE.read_text()
    if text.count(UNROOTED_CALL) != 1:
        raise RuntimeError("rooted load site changed")
    (output / "header-unrooted.kotoba").write_text(
        text.replace(UNROOTED_CALL, "kernel-load-u32 header 64 12", 1))
    refused = run_compiler(compiler, output, "header-unrooted.kotoba",
                           "header-unrooted.o", 1)
    if b"E7106" not in refused.stderr or (output / "header-unrooted.o").exists():
        raise RuntimeError("unrooted region length was not refused without output")
    if pin(SOURCE) != source_pin or pin(compiler) != compiler_pin:
        raise RuntimeError("qualification inputs changed")
    report = {"schema": "aiueos.llm-v1-header-native-build.v1",
              "status": "PASS_COMPILE_REPRODUCIBLE_UNROOTED_REFUSED",
              "source": source_pin, "compiler": compiler_pin,
              "object": pin(output / "header.o"),
              "reproducedObject": pin(output / "header-reproduced.o"),
              "unrootedSource": pin(output / "header-unrooted.kotoba"),
              "unrootedDiagnostic": "E7106", "unrootedArtifactAbsent": True,
              "objectAbi": "AIUEOS_KOTOBA_OBJECT_OK imports=0 relocations=1",
              "observer": pin(Path(__file__)), "guestExecution": False,
              "wire11Dispatch": False, "humanConsent": False}
    receipt = output / "llm-v1-header-native-build.json"
    receipt.write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], report["object"]["sha256"], flush=True)


if __name__ == "__main__":
    main()
