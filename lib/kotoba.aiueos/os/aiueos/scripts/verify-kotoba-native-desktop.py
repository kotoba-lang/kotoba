#!/usr/bin/env python3
import hashlib
import json
import os
import pathlib
import struct
import sys

elf = pathlib.Path(sys.argv[1])
source = pathlib.Path(sys.argv[2])
browser = pathlib.Path(sys.argv[3])
catalog = pathlib.Path(sys.argv[4])
compiler = sys.argv[5]
compiler_worktree_sha256 = sys.argv[6]
kotoba_native = sys.argv[7]
kotoba_native_worktree_sha256 = sys.argv[8]
receipt = pathlib.Path(sys.argv[9])
data = elf.read_bytes()

if data[:7] != b"\x7fELF\x02\x01\x01":
    raise SystemExit("error: desktop kernel is not ELF64 little-endian")
if struct.unpack_from("<H", data, 16)[0] != 2 or struct.unpack_from("<H", data, 18)[0] != 0x3E:
    raise SystemExit("error: desktop kernel is not x86-64 ET_EXEC")
entry = struct.unpack_from("<Q", data, 24)[0]
phoff = struct.unpack_from("<Q", data, 32)[0]
phentsize, phnum = struct.unpack_from("<HH", data, 54)
if entry != 0x101000 or phentsize != 56 or phnum != 2:
    raise SystemExit("error: desktop kernel entry/load contract rejected")
segments = [struct.unpack_from("<IIQQQQQQ", data, phoff + i * phentsize)
            for i in range(phnum)]
if [segment[0] for segment in segments] != [1, 1] or [segment[1] for segment in segments] != [5, 6]:
    raise SystemExit("error: desktop kernel must contain only RX and RW PT_LOAD segments")
if not any(bytes((opcode,)) in data for opcode in (0xEC, 0xED)):
    raise SystemExit("error: native input-port read lowering is absent")
if b"\xee" not in data:
    raise SystemExit("error: native input-device setup lowering is absent")
for forbidden in (b".interp", b".dynamic", b".dynsym", b"NEEDED", b"libc", b"msvcrt"):
    if forbidden in data:
        raise SystemExit("error: dynamic/C runtime dependency found")
if b"aiueos.browser-frame2" not in source.read_bytes() and b"aiueos.browser-frame2" not in browser.read_bytes():
    raise SystemExit("error: Kotoba Browser desktop frame dependency is absent")
if b"aiueos.session.app-catalog" not in source.read_bytes() or not catalog.is_file():
    raise SystemExit("error: shared Kotoba app catalog dependency is absent")

fuel = int(os.environ.get("AIUEOS_NATIVE_FUEL", "9007199254740991"))
value = {
    "format": "aiueos-kotoba-native-desktop-receipt/v1",
    "profile": "browser-gop-desktop-v1",
    "target": "x86_64-aiueos-kernel-v1",
    "entry": "aiueos_kernel_entry",
    "compiler_commit": compiler,
    "compiler_execution_route": os.environ.get(
        "AIUEOS_NATIVE_COMPILER_ROUTE",
        "native-selfhost" if "AIUEOS_AMU_SELFHOST_BINARY_SHA256" in os.environ
        else "nbb-bootstrap"),
    "compiler_worktree_sha256": compiler_worktree_sha256,
    **({"compiler_binary_sha256": os.environ["AIUEOS_AMU_SELFHOST_BINARY_SHA256"]}
       if "AIUEOS_AMU_SELFHOST_BINARY_SHA256" in os.environ else {}),
    "kotoba_native_commit": kotoba_native,
    "kotoba_native_worktree_sha256": kotoba_native_worktree_sha256,
    "source_closure": [
        {"module": "aiueos.native.desktop", "source": source.name,
         "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        {"module": "aiueos.browser-frame2", "source": browser.name,
         "sha256": hashlib.sha256(browser.read_bytes()).hexdigest()},
        {"module": "aiueos.session.app-catalog", "source": catalog.name,
         "sha256": hashlib.sha256(catalog.read_bytes()).hexdigest()},
    ],
    "artifact_sha256": hashlib.sha256(data).hexdigest(),
    "artifact_bytes": len(data),
    "fuel": {"initial": fuel, "replenishable": False},
    "ui": {
        "frame_source": "aiueos.browser-frame2",
        "presenter": "Kotoba x86-64 GOP framebuffer rasterizer",
        "apps": ["Murakumo", "Itonami", "Yataverse", "Aozora"],
        "input": ["PS/2 launcher and dock clicks, window focus, titlebar drag and close",
                  "keyboard 1-4 launch", "Tab cycles open windows",
                  "Escape closes focused window"],
        "runtime_boot_observed": False,
    },
    "c_sources": [],
    "foreign_objects": [],
    "imports": [],
    "dynamic_dependencies": [],
}
receipt.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="ascii")
print("AIUEOS_KOTOBA_NATIVE_DESKTOP_OK no-c no-crt no-linker imports=0 browser-frame=gop apps=4")
