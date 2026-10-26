#!/usr/bin/env python3
import hashlib
import json
import pathlib
import os
import struct
import sys

elf = pathlib.Path(sys.argv[1])
source = pathlib.Path(sys.argv[2])
rtl8125_source = source.with_name("rtl8125.kotoba")
compiler = sys.argv[3]
kotoba_native_commit = None
kotoba_native_worktree_sha256 = None
if len(sys.argv) >= 8 and len(sys.argv[4]) == 64 and len(sys.argv[6]) == 64:
    compiler_worktree_sha256 = sys.argv[4]
    kotoba_native_commit = sys.argv[5]
    kotoba_native_worktree_sha256 = sys.argv[6]
    receipt = pathlib.Path(sys.argv[7])
    capability_inputs = list(zip(sys.argv[8::2], sys.argv[9::2]))
elif len(sys.argv) >= 6 and len(sys.argv[4]) == 64:
    compiler_worktree_sha256 = sys.argv[4]
    receipt = pathlib.Path(sys.argv[5])
    capability_inputs = list(zip(sys.argv[6::2], sys.argv[7::2]))
else:
    # Older host-build paths still use the v5 verifier contract and do not
    # claim a source-tree fingerprint or a closed six-file Amu source record.
    compiler_worktree_sha256 = None
    receipt = pathlib.Path(sys.argv[4])
    capability_inputs = list(zip(sys.argv[5::2], sys.argv[6::2]))
capability_sources = [pathlib.Path(value) for value, _ in capability_inputs]
data = elf.read_bytes()
if not rtl8125_source.is_file():
    raise SystemExit("error: closed native RTL8125 module is missing")
if len(capability_sources) not in (0, 4, 6) or not all(path.is_file() for path in capability_sources):
    raise SystemExit("error: closed native capability/TCP source closure is incomplete")
if data[:4] != b"\x7fELF" or data[4:7] != b"\x02\x01\x01":
    raise SystemExit("error: Kotoba-native kernel is not ELF64 little-endian")
if struct.unpack_from("<H", data, 16)[0] != 2 or struct.unpack_from("<H", data, 18)[0] != 0x3E:
    raise SystemExit("error: Kotoba-native kernel is not x86-64 ET_EXEC")
entry = struct.unpack_from("<Q", data, 24)[0]
phoff = struct.unpack_from("<Q", data, 32)[0]
phentsize, phnum = struct.unpack_from("<HH", data, 54)
if entry != 0x101000 or phentsize != 56 or phnum != 2:
    raise SystemExit("error: Kotoba-native entry/load contract rejected")
segments = [struct.unpack_from("<IIQQQQQQ", data, phoff + i * phentsize) for i in range(phnum)]
if [segment[0] for segment in segments] != [1, 1] or [segment[1] for segment in segments] != [5, 6]:
    raise SystemExit("error: Kotoba-native kernel must contain only RX and RW PT_LOAD segments")
rx_start = segments[0][3]
rx_end = rx_start + segments[0][6]
rx_limit = (rx_end + 4095) & ~4095
rw_start = segments[1][3]
rw_end = rw_start + segments[1][6]
if (rx_start != 0x101000 or rx_limit > rw_start
        or rw_start & 4095 or rw_end >= 0x40000000
        or rw_start != rx_limit):
    raise SystemExit("error: Kotoba-native RX/RW page boundary rejected")
context_offset = segments[1][2]
# Default moved 1048576 -> 67108864 with the build script's, ADR-0203. The two
# must move together: this check is one of the copies the comment below counts,
# and a stale default here refuses a correctly-built kernel.
sealed_fuel = int(os.environ.get("AIUEOS_NATIVE_FUEL", "1073741824"))
# The number the kernel is built with was written down in five places at once
# (two --fuel flags, this check, the receipt and the OK line). Four of them
# were literals, so raising the budget failed here with a message naming the
# old value -- the same shape kotoba-kir ADR 0268 hit when max-native-fuel
# moved. The CHECK stays; only its duplication goes.
if segments[1][5] < 16 or struct.unpack_from("<Q", data, context_offset + 8)[0] != sealed_fuel:
    raise SystemExit(
        "error: Kotoba-native kernel context does not carry sealed fuel %d" % sealed_fuel)
cr3_read_encodings = (b"\x0f\x20\xd8", b"\x41\x0f\x20\xda")
cr3_write_encodings = (b"\x0f\x22\xd8", b"\x41\x0f\x22\xda")
invlpg_encodings = (b"\x0f\x01\x38", b"\x41\x0f\x01\x3a")
cr0_read_encodings = (b"\x0f\x20\xc0", b"\x41\x0f\x20\xc2")
cr0_write_encodings = (b"\x0f\x22\xc0", b"\x41\x0f\x22\xc2")
# The page-fault-recovery configurator's first store names a kernel context
# slot. Until kotoba-native #153 (4ca092eb, in amu >= 94f8fe37 / f040b483) it
# was `mov [0x110100],r10` -- an absolute disp32 that the packager had since
# moved into RX text, so under CR0.WP it page-faulted before the kernel's own
# #PF gate existed (ADR-0156: CR2=0x110100 -> #GP -> #DF -> triple fault). The
# slot block now lives at r9+0x160 in the RW context page
# (`kotoba.native.interrupt-abi/context-slot-block-offset`), and r9 is the
# context register in compiled Kotoba, so the store is `mov [r9+0x160],r10`.
# The old absolute form is refused below: a kernel that re-hardcodes the slot
# is the defect, not older evidence.
context_slot_store = b"\x4d\x89\x91\x60\x01\x00\x00"
absolute_context_slot_store = b"\x4c\x89\x14\x25\x00\x01\x11\x00"
if absolute_context_slot_store in data:
    raise SystemExit(
        "error: kernel context slot addressed by absolute disp32 0x110100 "
        "(inside RX text; kotoba-native #153 moved the slot block to r9+0x160)")
page_fault_frame_encodings = (
    b"\x41\x0f\x20\xd2\x4c\x8b\x1c\x24",
    b"\x41\x0f\x20\xd2\x4c\x8b\x5c\x24\x30",
    b"\x41\x0f\x20\xd2\x4c\x8b\x5c\x24\x38",
    b"\x41\x0f\x20\xd2\x4d\x8b\x1e",
)
if (not any(encoding in data for encoding in cr3_read_encodings)
        or not any(encoding in data for encoding in cr3_write_encodings)
        or not any(encoding in data for encoding in invlpg_encodings)
        or not any(encoding in data for encoding in cr0_read_encodings)
        or not any(encoding in data for encoding in cr0_write_encodings)
        or b"\x0f\x32" not in data or b"\x0f\x30" not in data
        or b"\x0f\xa2" not in data
        or b"\x66\x41\x8c\xca" not in data
        or b"\x41\x0f\x01\x1a" not in data
        or b"\x0f\x01\x0c\x24" not in data
        or not any(encoding in data for encoding in page_fault_frame_encodings)
        or context_slot_store not in data
        or b"\xed" not in data
        or b"\xee" not in data or b"\xef" not in data):
    raise SystemExit("error: privileged paging/protection lowering evidence is absent")
if b"\x88" not in data:
    raise SystemExit("error: allocator zero-store lowering evidence is absent")
if b"\x0f\xb7" not in data or not any(
    encoding in data
    for encoding in (b"\x66\x89", b"\x66\x41\x89", b"\x66\x45\x89")
):
    raise SystemExit("error: native u16 RTL8125 MMIO lowering evidence is absent")
for forbidden in (b".interp", b".dynamic", b".dynsym", b"NEEDED", b"libc"):
    if forbidden in data:
        raise SystemExit("error: dynamic/C runtime dependency found")
probe_encodings = {
    "guard-write": b"\xc6\x04\x25\x00\x00\x10\x00\x00",
    "text-write": b"\xc6\x04\x25\x00\x10\x10\x00\x00",
    "nx-execute": b"\x49\xba\x00\xc0\x10\x00\x00\x00\x00\x00\x41\xff\xd2",
    "recoverable-guard-write": b"\x49\xc7\xc2\x00\x00\x10\x00\x41\xc6\x02\x00",
}
present_probes = [name for name, encoding in probe_encodings.items() if encoding in data]
if len(present_probes) > 1:
    raise SystemExit("error: more than one sealed page-fault probe entered one artifact")
recovery_handler = b"\x48\x89\x04\x25\x10\x01\x11\x00" in data
payload = {
    "format": "aiueos-kotoba-native-receipt/v7" if kotoba_native_worktree_sha256
              else "aiueos-kotoba-native-receipt/v6" if compiler_worktree_sha256
              else "aiueos-kotoba-native-receipt/v5",
    "target": "x86_64-aiueos-kernel-v1",
    "timing_profile": "best-effort",
    "rtos_qualified": False,
    "runtime_linux": False,
    "runtime_jvm": False,
    "entry": "aiueos_kernel_entry",
    "compiler_commit": compiler,
    **({"compiler_binary_sha256": os.environ["AIUEOS_AMU_SELFHOST_BINARY_SHA256"]}
       if "AIUEOS_AMU_SELFHOST_BINARY_SHA256" in os.environ else {}),
    **({"compiler_worktree_sha256": compiler_worktree_sha256}
       if compiler_worktree_sha256 else {}),
    **({"kotoba_native_commit": kotoba_native_commit,
        "kotoba_native_worktree_sha256": kotoba_native_worktree_sha256}
       if kotoba_native_worktree_sha256 else {}),
    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "source_closure": [
        {"module": "aiueos.native.kernel", "source": source.name,
         "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        {"module": "native.rtl8125", "source": rtl8125_source.name,
         "sha256": hashlib.sha256(rtl8125_source.read_bytes()).hexdigest()},
    ] + [
        {"module": module, "source": "/".join(path.parts[-4:]),
         "revision": revision,
         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for module, (path, revision) in zip(
            ["capability.link.frame", "capability.dma.map",
             "capability.mmio.map", "capability.net.transport",
             "tcp.seq-core", "tcp.reassemble-core"][:len(capability_sources)],
            zip(capability_sources, [revision for _, revision in capability_inputs]),
        )
    ],
    "artifact_sha256": hashlib.sha256(data).hexdigest(),
    "artifact_bytes": len(data),
    "foreign_objects": [],
    "c_sources": [],
    "imports": [],
    "dynamic_dependencies": [],
    "fuel": {"initial": sealed_fuel, "replenishable": False},
    "allocator": {"page_bytes": 4096, "published_pages": 14,
                  "allocation_source": "amu-uefi-loader-rw-tail",
                  "zero_before_publish": True,
                  "ownership_state": "boot-lifetime-fourteen-slot-bitmap",
                  "duplicate_claim_rejected": True,
                  "double_free_rejected": True,
                  "reclamation_reused": True,
                  "page_table_root_allocated": True,
                  "identity_map_bytes": 1073741824,
                  "cr3_activated": True,
                  "invlpg_executed": True},
    "protection": {"nxe_readback": True, "cr0_wp_readback": True,
                   "guard_page": "0x100000-unmapped",
                   "kernel_text": f"0x{rx_start:x}-0x{rx_limit - 1:x}-rx",
                   "kernel_gap": (f"0x{rx_limit:x}-0x{rw_start - 1:x}-unmapped"
                                  if rx_limit < rw_start else "none"),
                   "kernel_state": f"0x{rw_start:x}-0x{rw_end - 1:x}-rw-nx",
                   "remaining_identity_map": "rw-nx"},
    "network": {"provider": "native.rtl8125",
                "pci_bdfs": ["02:00.0", "03:00.0"],
                "bar_mapping": "2m-uc-rw-nx",
                "dma_pages": 4,
                "rings": {"tx": 1, "rx": 1},
                "qemu_path": "bounded-no-device",
                "physical_k16": "unverified"},
    "exceptions": {"idt_vector": 14, "selector": "runtime-current-cs",
                   "lidt": True, "sidt_readback": True,
                   "handler": ("recoverable-bounded-frame-iretq"
                               if recovery_handler
                               else "non-returning-cr2-error-code-classifier"),
                   "recovery_configuration": "sealed-frame-page-and-dedicated-stack",
                   "frame_fields": ["cr2", "error-code", "original-rip", "handler-stack-top"],
                   "sealed_probe": present_probes[0] if present_probes else None},
}
receipt.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="ascii")
print("AIUEOS_KOTOBA_NATIVE_KERNEL_OK no-c no-crt no-linker imports=0 fuel=%d " % sealed_fuel + "allocator-pages=14 ownership-bitmap page-table-root identity-1g rtl8125-pci-mmio-dma guard-unmapped text-rx state-rw-nx nxe cr0-wp cr3-activated invlpg idt14-sidt-readback pf-cr2-error-code recovery-frame dedicated-handler-stack reuse double-free-rejected descriptors<=410 zero-before-publish")
