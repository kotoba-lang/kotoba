#!/usr/bin/env python3
"""Execute bounded owner-source HTML cases with an explicitly pinned native Amu.

The Kotoba fixtures determine the verdict. This Mac-only observer stages exact
source bytes, invokes the compiler and packager, and records input digests. It
is not the Hiccup parity suite or a site-generation qualification.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

OWNER = Path(__file__).resolve().parent.parent


def pin(path):
    b = path.read_bytes()
    return {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def checked_image(path, expected):
    if path.is_symlink() or not path.is_file() or pin(path)["sha256"] != expected:
        raise ValueError("missing, symlinked, or mismatched image: " + str(path))
    return path.resolve(strict=True)


def native(image, directory, args):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    saved = None
    try:
        if fd != 3:
            try:
                saved = os.dup(3)
            except OSError:
                pass
            os.dup2(fd, 3)
        env = {"PATH": "/nonexistent", "LANG": "C", "TMPDIR": str(directory)}
        r = subprocess.run([str(image), *args], cwd=directory, env=env,
                           pass_fds=(3,), capture_output=True, timeout=300)
    finally:
        if fd != 3:
            if saved is None:
                os.close(3)
            else:
                os.dup2(saved, 3)
                os.close(saved)
        os.close(fd)
    if r.returncode or r.stderr:
        raise RuntimeError(f"{image.name} exit {r.returncode}: {r.stderr[-1000:]!r}")
    return r.stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for arg in ("compiler", "packager", "output"):
        ap.add_argument("--" + arg, type=Path, required=True)
    ap.add_argument("--compiler-sha256", required=True)
    ap.add_argument("--packager-sha256", required=True)
    a = ap.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("requires native macOS ARM64")
    compiler = checked_image(a.compiler, a.compiler_sha256)
    packager = checked_image(a.packager, a.packager_sha256)
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    cases = []
    for name in ("html_core", "html_document"):
        original = OWNER / "kotoba" / (name + ".kotoba")
        fixture = OWNER / "test/native" / (name + "_cases.kotoba.inc")
        text = original.read_text()
        ns = "html-core" if name == "html_core" else "html-document"
        marker = "(ns " + ns
        if text.count(marker) != 1:
            raise ValueError("unexpected namespace")
        text = text.replace(marker, marker + "\n  (:export [main])", 1)
        if name == "html_document":
            if text.count("(defn main []") != 1:
                raise ValueError("unexpected document self-test")
            text = text.replace("(defn main []", "(defn original-main []", 1)
        staged = out / (name + ".kotoba")
        staged.write_text(text + "\n" + fixture.read_text())
        native(compiler, out, ["compile", staged.name, "--target", "aarch64-macos", "--output", name + ".kseed"])
        result = native(compiler, out, ["extract-native", name + ".kseed", "--symbol", "main", "--output", name + ".raw"])
        match = re.search(rb":offset (\d+), :length (\d+), :arity 0}", result)
        if not match or int(match[2]) != (out / (name + ".raw")).stat().st_size:
            raise ValueError("unexpected native image extent")
        native(packager, out, [name + "-unsigned.macho", name + ".raw", "fs2-cli-stdio-general", match[1].decode()])
        image = out / (name + ".macho")
        shutil.copyfile(out / (name + "-unsigned.macho"), image)
        image.chmod(0o755)
        subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(image)],
                       check=True, capture_output=True, timeout=30)
        result = subprocess.run([str(image)], cwd=out, env={"PATH": "/nonexistent"},
                                capture_output=True, timeout=60)
        if result.returncode or result.stderr:
            raise RuntimeError(f"{name} fixture exit {result.returncode}: {result.stderr[-1000:]!r}")
        cases.append({"name": name, "source": pin(original), "fixture": pin(fixture),
                      "staged": pin(staged), "image": pin(image), "exit": result.returncode})
    receipt = {"status": "PASS_BOUNDED_HTML_MACOS_NATIVE", "compiler": pin(compiler),
               "packager": pin(packager), "cases": cases,
               "fullHiccupParity": False, "siteGeneration": False}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(receipt["status"])


if __name__ == "__main__":
    main()
