#!/usr/bin/env python3
"""Report the physical K16 pure-native closure without upgrading claims."""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "contracts" / "k16-kotoba-native-closure-v1.edn"
PHYSICAL_EVIDENCE = ROOT / "contracts" / "physical-kotoba-native-k16-v1.edn"
EXPECTED_COMPILER = "13d2f5dfe1adeaa99b7e9e6c04fcf8cb8fc15a4b"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    text = CONTRACT.read_text(encoding="utf-8")
    kernel_builder = (ROOT / "scripts" / "build-kotoba-native-kernel.sh").read_text(
        encoding="utf-8"
    )
    boot_builder = (ROOT / "scripts" / "build-kotoba-native-boot.sh").read_text(
        encoding="utf-8"
    )
    physical_evidence = PHYSICAL_EVIDENCE.read_text(encoding="utf-8")
    pure_source = ROOT / "native" / "kernel.kotoba"

    expected_pin = f"expected={EXPECTED_COMPILER}"
    reference_files = {
        "nic": ["kernel/rtl8125.c", "kernel/rtl8125.h"],
        "https": ["kernel/tls13.c", "kernel/tls_aes_gcm.c"],
        "qwen": [
            "kernel/qwen35_infer.c",
            "kernel/qwen35_quant.c",
            "kernel/qwen35_runtime.c",
        ],
    }
    native_sources = {
        "nic": [str(pathlib.Path("native") / "rtl8125.kotoba")],
        "https": [
            str(pathlib.Path("kotoba") / "aes128-gcm.kotoba"),
            str(pathlib.Path("kotoba") / "hkdf-sha256.kotoba"),
            str(pathlib.Path("kotoba") / "tls13-record.kotoba"),
        ],
        "qwen": [
            str(pathlib.Path("kotoba") / "qwen35-gguf-header-valid.kotoba")
        ],
    }
    layers = {
        "boot": {
            "state": "physical-preflight-kernel-entry-passed",
            "source": str(pure_source.relative_to(ROOT)),
            "source_sha256": sha256(pure_source),
            "compiler_pin_matches": expected_pin in kernel_builder
            and expected_pin in boot_builder,
            "physical_evidence": str(PHYSICAL_EVIDENCE.relative_to(ROOT)),
        }
    }
    for name, paths in reference_files.items():
        present = [path for path in paths if (ROOT / path).is_file()]
        layers[name] = {
            "state": (
                "physical-arp-and-udp-receipt-passed"
                if name == "nic"
                else "not-implemented-in-pure-closure"
            ),
            "foreign_reference_files_present": present,
            "native_sources": {
                path: sha256(ROOT / path)
                for path in native_sources[name]
                if (ROOT / path).is_file()
            },
        }

    declared_incomplete = all(
        marker in text
        for marker in (
            ":all-native-ready? false",
            ":status :in-progress",
            ":nic {:state :one-shot-native-provider",
            ":https {:state :not-implemented-in-pure-closure",
            ":qwen {:state :not-implemented-in-pure-closure",
        )
    ) and all(
        marker in physical_evidence
        for marker in (
            ':checkpoint "AIUEOS K16 PREFLIGHT STATUS 5A"',
            ':provider-status 0',
            ':message "AIUEOS_NATIVE_ARP_OK"',
            ':physical-rtl8125-provider :passed',
        )
    )
    result = {
        "format": "aiueos.k16-kotoba-native-closure-audit/v1",
        "contract": str(CONTRACT.relative_to(ROOT)),
        "contract_declares_incomplete": declared_incomplete,
        "compiler": EXPECTED_COMPILER,
        "layers": layers,
        "all_native_ready": False,
        "next_blocker": "physical-pure-kotoba-tcp-positive-receipt",
    }
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")

    if not declared_incomplete or not layers["boot"]["compiler_pin_matches"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
