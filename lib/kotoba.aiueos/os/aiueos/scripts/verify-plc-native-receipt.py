#!/usr/bin/env python3
"""Fail closed unless an AIUEOS PLC deployment receipt is fully bound."""

import json
import pathlib
import re
import sys


SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA1 = re.compile(r"^[0-9a-f]{40}$")


def violations(receipt):
    scan = receipt.get("scan", {})
    timing = receipt.get("timing") or {}
    failures = []

    def require(condition, name):
        if not condition:
            failures.append(name)

    require(receipt.get("format") == "aiueos-plc-native-receipt/v1", "format")
    require(receipt.get("profile") == "aiueos-plc-v1", "profile")
    require(receipt.get("target") == "x86_64-aiueos-user-v1", "target")
    require(receipt.get("source_language") ==
            "iec-61131-3-structured-text-subset-v1", "source_language")
    for key in ("runtime_linux", "runtime_jvm", "runtime_gc", "dynamic_allocation"):
        require(receipt.get(key) is False, key)
    require(receipt.get("capabilities") == [16, 17, 18, 19], "capabilities")
    for key in ("input_snapshot", "shadow_outputs", "atomic_commit",
                "safe_state_on_failure"):
        require(scan.get(key) is True, "scan." + key)
    for key in ("st_source_sha256", "generated_kotoba_sha256",
                "native_elf_sha256", "rt_kernel_artifact_sha256",
                "rt_kernel_receipt_sha256", "io_map_sha256",
                "admission_analysis_sha256", "signature_sha256",
                "signer_public_key_sha256"):
        require(bool(SHA256.fullmatch(str(receipt.get(key, "")))), key)
    require(receipt.get("signature_scheme") == "ecdsa-p256-sha256",
            "signature_scheme")
    require(bool(GIT_SHA1.fullmatch(str(receipt.get("compiler_commit", "")))),
            "compiler_commit")
    priority = timing.get("priority")
    cycle = timing.get("cycle_us")
    deadline = timing.get("deadline_us")
    budget = timing.get("budget_us")
    wcet = timing.get("wcet_us")
    require(isinstance(priority, int) and 1 <= priority <= 255, "timing.priority")
    require(all(isinstance(value, int) for value in (cycle, deadline, budget, wcet))
            and 0 < wcet <= budget <= deadline <= cycle, "timing.envelope")
    response = timing.get("response_time_us")
    blocking = timing.get("blocking_us")
    interference = timing.get("interference_us")
    require(isinstance(wcet, (int, float)) and
            all(isinstance(value, (int, float)) for value in
                (response, blocking, interference)) and
            0 <= blocking and 0 <= interference and wcet + blocking + interference <= response <= deadline,
            "timing.response_time")
    require(isinstance(timing.get("sample_count"), int) and
            timing["sample_count"] >= 10000, "timing.sample_count")
    require(receipt.get("deployment_ready") is True, "deployment_ready")
    return failures


def main(argv):
    if len(argv) != 2:
        raise SystemExit("usage: verify-plc-native-receipt.py RECEIPT.json")
    receipt = json.loads(pathlib.Path(argv[1]).read_text(encoding="ascii"))
    failures = violations(receipt)
    if failures:
        raise SystemExit("error: AIUEOS PLC deployment refused: " + ", ".join(failures))
    print("AIUEOS_PLC_DEPLOYMENT_RECEIPT_OK linux=0 jvm=0 atomic-output=1")


if __name__ == "__main__":
    main(sys.argv)
