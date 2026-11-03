#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- pci.c's read_bar and bar_extent (over kotoba/pci-bar.o) as new_read_bar /
# new_bar_extent, over the driver's emulated device. JUN-598.
import sys
src = open(sys.argv[1]).read()
def fn(start):
    a = src.index(start); return src[a:src.index("\n}\n", a) + 3]
rb = fn("static int read_bar(uint8_t b, uint8_t d, uint8_t f, uint8_t index, uint64_t *base) {").replace("static int read_bar(", "int new_read_bar(")
be = fn("static int bar_extent(uint8_t b, uint8_t d, uint8_t f, uint8_t index,").replace("static int bar_extent(", "int new_bar_extent(")
assert "kotoba_aiueos_pci_bar_base(" in rb and "kotoba_aiueos_pci_bar_size(" in be
head = """#include <stdint.h>
uint32_t config_read(uint8_t bus, uint8_t dev, uint8_t fn, uint8_t off);
void config_write(uint8_t bus, uint8_t dev, uint8_t fn, uint8_t off, uint32_t value);
extern uint64_t kotoba_aiueos_pci_extent_valid(uint64_t value, uint64_t size);
extern int64_t kotoba_aiueos_pci_bar_kind(int64_t low, int64_t index); extern int64_t kotoba_aiueos_pci_bar_value(int64_t low, int64_t high);
extern int64_t kotoba_aiueos_pci_bar_base(int64_t low, int64_t high, int64_t index); extern int64_t kotoba_aiueos_pci_bar_size(int64_t mask_low, int64_t mask_high, int64_t kind);
"""
open(sys.argv[2], "w").write(head + rb + "\n" + be)
