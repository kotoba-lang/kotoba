#!/usr/bin/env python3
"""Build and observe the Kotoba LLM result probe without VNC or credentials.

Both guests are produced by the pinned Mac selfhost compiler. The negative
guest is a valid kernel returning 42 but has no LLM receipt. This qualifies
only kernel-side request/result components, not wire 11 or model execution.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "native"
ALIAS_PROBE_SHA256 = "54b6b739daaf6b8b67f78fc339942118a8cf0d054593b4fc6481c95136c8a7c4"


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
    if pin(NATIVE / "llm_v1_header_probe.kotoba")["sha256"] != ALIAS_PROBE_SHA256:
        p.error("review the alias checks before claiming their QEMU readback")
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
        result_shape = "/os/aiueos/native/llm_v1_result_shape.kotoba"
        utf8_shape = "/os/aiueos/native/llm_v1_utf8.kotoba"
        assert (validator in graph) == expected
        assert (request_shape in graph) == expected
        assert (result_shape in graph) == expected
        assert (utf8_shape in graph) == expected
        assert state["sourceModuleCount"] == (20 if expected else 16)
        guest = output / (name + "-qemu")
        result = run([sys.executable, "-I", observer,
                      "--kernel", build / "KERNEL.ELF",
                      "--efi", build / "BOOTX64.EFI", "--qemu", a.qemu,
                      "--firmware", a.firmware, "--output", guest,
                      "--llm-result"], output / (name + "-qemu.stdout"),
                     output / (name + "-qemu.stderr"), 240)
        receipt = guest / "entry-qemu.json"
        if expected:
            assert result.returncode == 0 and receipt.is_file(), result.stderr.decode(errors="replace")[-2000:]
            report = json.loads(receipt.read_text())
            assert report["result"] == 42
            assert report["llmHeader"]["checks"] == [1] * 12
            assert report["llmRequest"]["checks"] == [1] * 9
            assert report["llmResult"]["checks"] == [1] * 6
            assert report["llmResult"]["providerDispatch"] is False
            assert report["llmResult"]["userValueLowering"] is False
            assert report["llmHeader"]["providerDispatch"] is False
            assert report["llmHeader"]["modelExecution"] is False
        else:
            assert result.returncode != 0 and not receipt.exists()
            assert b"assert checks[:12] == (1,)*12" in result.stderr, result.stderr.decode(errors="replace")[-2000:]
        calls.append({"case": name, "entry": entry, "build": state["state"],
                      "guestExit": result.returncode,
                      "kernel": pin(build / "KERNEL.ELF"),
                      "efi": pin(build / "BOOTX64.EFI")})
    proof = {"schema": "aiueos.llm-v1-result-qemu.v1",
             "status": "PASS_MAC_NATIVE_LLM_RESULT_GUEST_AND_NEGATIVE",
             "compiler": pin(a.compiler_image), "observer": pin(observer),
             "validator": pin(NATIVE / "llm_v1_header.kotoba"),
             "requestShape": pin(NATIVE / "llm_v1_request_shape.kotoba"),
             "resultShape": pin(NATIVE / "llm_v1_result_shape.kotoba"),
             "utf8Shape": pin(NATIVE / "llm_v1_utf8.kotoba"),
             "probe": pin(NATIVE / cases[0][1]), "runner": pin(Path(__file__)),
             "qemu": subprocess.check_output([str(a.qemu), "--version"]).decode().splitlines()[0],
             "firmware": pin(a.firmware), "calls": calls,
             "guestEmulation": "QEMU TCG", "wire11Dispatch": False,
             "modelExecution": False, "humanConsent": False,
             "utf8ComponentValidated": True, "aliasingQualified": False,
             "aliasRefusalsObserved": [
                 "model-selected-same-root",
                 "empty-system-prompt-same-root",
                 "prompt-result-same-root",
                 "prompt-result-overlap-offset-1",
             ],
             "nestedUserValueQualified": False,
             "desktop": False, "physicalHardware": False}
    (output / "llm-result-qemu.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(proof["status"])


if __name__ == "__main__":
    main()
