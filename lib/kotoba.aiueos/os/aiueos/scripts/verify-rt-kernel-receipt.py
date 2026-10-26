#!/usr/bin/env python3
"""Fail closed unless a native AIUEOS kernel receipt satisfies RT v1."""

import json
import pathlib
import re
import sys


SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA1 = re.compile(r"^[0-9a-f]{40}$")


def violations(receipt):
    scheduler = receipt.get("scheduler", {})
    memory = receipt.get("memory", {})
    measured = receipt.get("measurement", {})
    limits = receipt.get("requirements", {})
    failures = []

    def require(condition, name):
        if not condition:
            failures.append(name)

    require(receipt.get("format") == "aiueos-kotoba-native-rt-receipt/v1", "format")
    require(receipt.get("target") == "x86_64-aiueos-rt-kernel-v1", "target")
    require(receipt.get("timing_profile") == "hard-real-time", "timing_profile")
    require(receipt.get("rtos_qualified") is True, "rtos_qualified")
    require(receipt.get("runtime_linux") is False, "runtime_linux")
    require(receipt.get("runtime_jvm") is False, "runtime_jvm")
    require(receipt.get("runtime_gc") is False, "runtime_gc")
    require(receipt.get("hosted_adapters") is False, "hosted_adapters")
    for key in ("c_sources", "foreign_objects", "imports", "dynamic_dependencies"):
        require(receipt.get(key) == [], key)
    require(scheduler.get("policy") == "fixed-priority-preemptive", "scheduler.policy")
    require(scheduler.get("cores") == 1, "scheduler.cores")
    require(scheduler.get("priority_order") == "lower-number-is-more-urgent",
            "scheduler.priority_order")
    require(scheduler.get("same_priority_default") == "fifo",
            "scheduler.same_priority_default")
    require(scheduler.get("round_robin_trigger") == "quantum-expiry-only",
            "scheduler.round_robin_trigger")
    require(scheduler.get("task_set") == "static-after-admission",
            "scheduler.task_set")
    require(scheduler.get("base_priority_change_after_start") is False,
            "scheduler.base_priority_change_after_start")
    require(scheduler.get("cooperative_task_class") is False,
            "scheduler.cooperative_task_class")
    require(scheduler.get("deadline_ordering") is False,
            "scheduler.deadline_ordering")
    require(scheduler.get("priority_inversion") == "priority-ceiling",
            "scheduler.priority_inversion")
    require(scheduler.get("admission") == "response-time-analysis",
            "scheduler.admission")
    require(memory.get("dynamic_allocation_after_start") is False,
            "memory.dynamic_allocation_after_start")
    require(memory.get("page_faults_after_start") is False,
            "memory.page_faults_after_start")
    require(receipt.get("amu_rt_subset_version") == 1, "amu_rt_subset_version")
    require(bool(GIT_SHA1.fullmatch(str(receipt.get("compiler_commit", "")))),
            "compiler_commit")
    for key in ("artifact_sha256", "measured_artifact_sha256",
                "admission_analysis_sha256", "scheduler_policy_sha256",
                "embedded_scheduler_policy_sha256"):
        require(bool(SHA256.fullmatch(str(receipt.get(key, "")))), key)
    require(receipt.get("artifact_sha256") == receipt.get("measured_artifact_sha256"),
            "measurement_artifact_binding")
    require(receipt.get("scheduler_policy_sha256") ==
            receipt.get("embedded_scheduler_policy_sha256"),
            "scheduler_policy_binding")
    require(measured.get("physical_hardware") is True, "measurement.physical_hardware")
    require(measured.get("monotonic_clock") is True, "measurement.monotonic_clock")
    require(isinstance(measured.get("timer_frequency_hz"), (int, float)) and
            measured.get("timer_frequency_hz", 0) > 0, "measurement.timer_frequency_hz")
    require(isinstance(measured.get("sample_count"), int) and
            measured.get("sample_count", 0) >= 10000, "measurement.sample_count")
    for key in ("hardware_id_sha256", "timer_calibration_sha256",
                "measurement_run_sha256"):
        require(bool(SHA256.fullmatch(str(measured.get(key, "")))),
                "measurement." + key)
    for key in ("max_interrupt_latency_us", "max_dispatch_latency_us",
                "max_timer_jitter_us", "wcet_max_us"):
        value = measured.get(key)
        bound = limits.get(key if key != "wcet_max_us" else "task_budget_us")
        require(isinstance(value, (int, float)) and value > 0 and
                isinstance(bound, (int, float)) and bound > 0 and value <= bound,
                f"measurement.{key}")
    return failures


def main(argv):
    if len(argv) != 2:
        raise SystemExit("usage: verify-rt-kernel-receipt.py RECEIPT.json")
    path = pathlib.Path(argv[1])
    receipt = json.loads(path.read_text(encoding="ascii"))
    failures = violations(receipt)
    if failures:
        raise SystemExit("error: AIUEOS RT receipt refused: " + ", ".join(failures))
    print("AIUEOS_RT_RECEIPT_OK target=x86_64-aiueos-rt-kernel-v1 linux=0 jvm=0")


if __name__ == "__main__":
    main(sys.argv)
