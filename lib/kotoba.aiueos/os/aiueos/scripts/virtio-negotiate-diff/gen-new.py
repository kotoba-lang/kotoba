#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- pci.c's negotiate (the wrapper over kotoba/virtio-negotiate.o) as new_negotiate. JUN-598.
import sys
src = open(sys.argv[1]).read()
a = src.index("static int negotiate(volatile struct virtio_common_cfg *cfg) {")
neg = src[a:src.index("\n}\n", a) + 3].replace("static int negotiate(", "int new_negotiate(")
vc = src[src.index("struct virtio_common_cfg {"):]
vc = vc[:vc.index("} __attribute__((packed));") + len("} __attribute__((packed));")]
assert "kotoba_aiueos_virtio_negotiate(" in neg
open(sys.argv[2], "w").write("#include <stdint.h>\nextern int64_t kotoba_aiueos_virtio_negotiate(uint64_t cfg, uint64_t length);\n" + vc + "\n" + neg)
