#!/usr/bin/env python3
"""Verify the narrow C-free Kotoba/Amu RT kernel artifact."""

import hashlib
import json
import os
import pathlib
import struct
import sys

elf = pathlib.Path(sys.argv[1])
source = pathlib.Path(sys.argv[2])
compiler_commit = sys.argv[3]
if len(sys.argv) >= 6 and len(sys.argv[4]) == 64:
    compiler_worktree_sha256 = sys.argv[4]
    receipt = pathlib.Path(sys.argv[5])
    sources = [source] + [pathlib.Path(value) for value in sys.argv[6:]]
else:
    compiler_worktree_sha256 = None
    receipt = pathlib.Path(sys.argv[4])
    sources = [source] + [pathlib.Path(value) for value in sys.argv[5:]]
data = elf.read_bytes()
if data[:7] != b"\x7fELF\x02\x01\x01":
    raise SystemExit("error: RT kernel is not ELF64 little-endian")
if struct.unpack_from("<HH", data, 16) != (2, 0x3E):
    raise SystemExit("error: RT kernel is not x86-64 ET_EXEC")
entry = struct.unpack_from("<Q", data, 24)[0]
phoff = struct.unpack_from("<Q", data, 32)[0]
phentsize, phnum = struct.unpack_from("<HH", data, 54)
segments = [struct.unpack_from("<IIQQQQQQ", data, phoff + i * phentsize)
            for i in range(phnum)]
if entry != 0x101000 or phentsize != 56 or phnum != 2:
    raise SystemExit("error: RT kernel entry/load contract rejected")
if [s[0] for s in segments] != [1, 1] or [s[1] for s in segments] != [5, 6]:
    raise SystemExit("error: RT kernel must contain only RX and RW PT_LOAD segments")
if segments[1][3] != 0x110000:
    raise SystemExit("error: RT kernel fixed state page is not 0x110000")
required = {
    "timer_counter": b"\x48\xff\x04\x25\x00\x02\x11\x00",
    "apic_eoi_zero_extended": b"\xba\xb0\x00\xe0\xfe\xc7\x02",
    "interrupt_return": b"\x48\xcf",
    "interrupt_enable": b"\xfb",
    "interrupt_wait": b"\xf4",
    "load_idt": b"\x41\x0f\x01\x1a",
    "write_msr": b"\x0f\x30",
}
missing = [name for name, encoding in required.items() if encoding not in data]
if missing:
    raise SystemExit("error: RT lowering evidence absent: " + ",".join(missing))
for forbidden in (b".interp", b".dynamic", b".dynsym", b"NEEDED", b"libc"):
    if forbidden in data:
        raise SystemExit("error: dynamic/C runtime dependency found")
payload = {
    "format": "aiueos-kotoba-native-rt-functional-receipt/v2" if compiler_worktree_sha256 else "aiueos-kotoba-native-rt-functional-receipt/v1",
    "target": "x86_64-aiueos-kernel-v1",
    "timing_profile": "logical-qemu-unqualified",
    "rtos_qualified": False,
    "runtime_linux": False, "runtime_jvm": False, "runtime_gc": False,
    "hosted_adapters": False,
    "compiler_commit": compiler_commit,
    **({"compiler_binary_sha256": os.environ["AIUEOS_AMU_SELFHOST_BINARY_SHA256"]}
       if "AIUEOS_AMU_SELFHOST_BINARY_SHA256" in os.environ else {}),
    **({"compiler_worktree_sha256": compiler_worktree_sha256}
       if compiler_worktree_sha256 else {}),
    "sources": {item.name: hashlib.sha256(item.read_bytes()).hexdigest()
                for item in sources},
    "artifact_sha256": hashlib.sha256(data).hexdigest(),
    "artifact_bytes": len(data),
    "c_sources": [], "foreign_objects": [], "imports": [],
    "dynamic_dependencies": [],
    "interrupt": {"controller": "x86-local-apic", "vector": 32,
                  "entry": "amu-sealed-register-preserving-iretq",
                  "counter_address": "0x110200"},
    "scheduler": {"policy": "fixed-priority",
                  "priority_order": "lower-number-is-more-urgent",
                  "plc_priority": 1, "background_priority": 10,
                  "period_ticks": 2},
    "mutex": {"protocol": "immediate-priority-ceiling",
              "recursive_lock": "rejected",
              "foreign_unlock": "rejected"},
    "io_provider": {"abi": "two-input-two-output-transaction/v1",
                    "input": "latched-before-scan",
                    "output": "shadow-then-atomic-commit",
                    "watchdog": "exactly-one-before-commit",
                    "physical_driver_qualified": False},
    "device_profiles": {
        "protocol_families": ["mmio", "modbus-rtu", "modbus-tcp",
                              "ethercat", "profinet-irt",
                              "ethernet-ip-cip-sync", "canopen",
                              "cc-link-ie-tsn", "opc-ua-pubsub-tsn"],
        "unknown_or_proprietary": "fail-closed",
        "model_specific_hardware_qualified": False,
    },
    "plc": {"language": "kotoba", "scan_count": 100,
            "input": "single-snapshot", "output": "single-commit",
            "external_elf_admission": "sha256+ecdsa-p256+canonical-elf",
            "ring3_execution_qualified": False},
}
receipt.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
                   encoding="ascii")
print("AIUEOS_KOTOBA_RT_KERNEL_OK no-c no-linux no-jvm apic-vector=32 fixed-priority plc-scans=100 timing=logical-unqualified")
