#!/usr/bin/env python3
"""Build and observe the Kotoba LLM header probe without VNC or credentials.

Both guests are produced by the pinned Mac selfhost compiler. The negative
guest is a valid kernel returning 42 but has no LLM receipt. This qualifies
only the kernel-side header validator, not wire 11 or model execution.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "native"


def pin(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def run(argv, stdout, stderr, timeout):
    result = subprocess.run([str(part) for part in argv], capture_output=True,
                            timeout=timeout, check=False)
    stdout.write_bytes(result.stdout)
    stderr.write_bytes(result.stderr)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--compiler-image", type=Path, required=True)
    p.add_argument("--compiler-sha256", required=True)
    p.add_argument("--observer", type=Path, required=True)
    p.add_argument("--observer-sha256", required=True)
    p.add_argument("--qemu", type=Path, required=True)
    p.add_argument("--firmware", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    observer = a.observer.resolve(strict=True)
    if a.observer.is_symlink() or pin(observer)["sha256"] != a.observer_sha256:
        p.error("observer must be a regular file with the declared digest")
    output = a.output.resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    cases = (("positive", "llm_v1_header_probe.kotoba", True),
             ("negative", "dma-snapshot-probe.kotoba", False))
    calls = []
    for name, entry, expected in cases:
        build = output / (name + "-build")
        result = run([sys.executable, "-I", HERE / "build-native-kernel-macos.py",
                      "--compiler-image", a.compiler_image,
                      "--compiler-sha256", a.compiler_sha256,
                      "--kernel-source", NATIVE / entry, "--fuel", "500000",
                      "--output", build], output / (name + "-build.stdout"),
                     output / (name + "-build.stderr"), 3600)
        assert result.returncode == 0, (name, result.stderr.decode(errors="replace")[-2000:])
        state = json.loads((build / "build-state.json").read_text())
        assert state["state"] == "MACOS_NATIVE_IMAGE_CANDIDATE"
        assert state["kernelEntry"].endswith("/" + entry)
        graph = set(state["sourceGraph"])
        validator = "/os/aiueos/native/llm_v1_header.kotoba"
        request_shape = "/os/aiueos/native/llm_v1_request_shape.kotoba"
        assert (validator in graph) == expected
        assert (request_shape in graph) == expected
        assert state["sourceModuleCount"] == (18 if expected else 16)
        guest = output / (name + "-qemu")
        result = run([sys.executable, "-I", observer,
                      "--kernel", build / "KERNEL.ELF",
                      "--efi", build / "BOOTX64.EFI", "--qemu", a.qemu,
                      "--firmware", a.firmware, "--output", guest,
                      "--llm-header"], output / (name + "-qemu.stdout"),
                     output / (name + "-qemu.stderr"), 240)
        receipt = guest / "entry-qemu.json"
        if expected:
            assert result.returncode == 0 and receipt.is_file(), result.stderr.decode(errors="replace")[-2000:]
            report = json.loads(receipt.read_text())
            assert report["result"] == 42
            assert report["llmHeader"]["checks"] == [1] * 12
            assert report["llmRequest"]["checks"] == [1] * 9
            assert report["llmHeader"]["providerDispatch"] is False
            assert report["llmHeader"]["modelExecution"] is False
        else:
            assert result.returncode != 0 and not receipt.exists()
            assert b"assert checks[:12] == (1,)*12" in result.stderr, result.stderr.decode(errors="replace")[-2000:]
        calls.append({"case": name, "entry": entry, "build": state["state"],
                      "guestExit": result.returncode,
                      "kernel": pin(build / "KERNEL.ELF"),
                      "efi": pin(build / "BOOTX64.EFI")})
    proof = {"schema": "aiueos.llm-v1-header-qemu.v1",
             "status": "PASS_MAC_NATIVE_LLM_HEADER_GUEST_AND_NEGATIVE",
             "compiler": pin(a.compiler_image), "observer": pin(observer),
             "validator": pin(NATIVE / "llm_v1_header.kotoba"),
             "requestShape": pin(NATIVE / "llm_v1_request_shape.kotoba"),
             "probe": pin(NATIVE / cases[0][1]), "runner": pin(Path(__file__)),
             "qemu": subprocess.check_output([str(a.qemu), "--version"]).decode().splitlines()[0],
             "firmware": pin(a.firmware), "calls": calls,
             "guestEmulation": "QEMU TCG", "wire11Dispatch": False,
             "modelExecution": False, "humanConsent": False,
             "utf8ComponentValidated": True, "aliasingQualified": False,
             "desktop": False, "physicalHardware": False}
    (output / "llm-header-qemu.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(proof["status"])


if __name__ == "__main__":
    main()
