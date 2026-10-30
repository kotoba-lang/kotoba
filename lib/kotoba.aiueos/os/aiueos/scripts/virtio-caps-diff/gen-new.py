#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- pci.c's find_virtio_caps (the wrapper over kotoba/virtio-caps.o) as
# new_find_virtio_caps, over the driver's synthetic configuration space. JUN-598.
import sys
src = open(sys.argv[1]).read()
def block(start, end="};"):
    a = src.index(start); return src[a:src.index(end, a) + len(end)]
a = src.index("static int find_virtio_caps(uint8_t b, uint8_t d, uint8_t f,")
fv = src[a:src.index("\n}\n", a) + 3].replace("static int find_virtio_caps(", "int new_find_virtio_caps(")
assert "kotoba_aiueos_virtio_caps_find(" in fv
head = """#include <stdint.h>
uint32_t config_read(uint8_t bus, uint8_t dev, uint8_t fn, uint8_t off);
extern int64_t kotoba_aiueos_virtio_caps_find(uint64_t header, uint64_t header_length, uint64_t record, uint64_t record_length);
"""
open(sys.argv[2], "w").write(head + block("struct virtio_pci_cap {") + "\n" + block("struct virtio_caps {") + "\n" + fv)
