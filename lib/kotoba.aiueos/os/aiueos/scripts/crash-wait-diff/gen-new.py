#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- crash_sector_io_polled's completion wait over kotoba/blk-wait.o (as it is now in
# kernel/pci.c) as new_wait, with the 10^8 budget made a parameter. JUN-598.
import sys
src = open(sys.argv[1]).read()
a = src.index("static int crash_sector_io_polled(uint32_t type) {")
lo = src.index("  for (uint32_t budget = 0, got; budget < 100000000U; budget += 65536U) {", a)
hi = src.index("  return 0;\n}", lo)
loop = src[lo:hi].replace("100000000U", "budget_limit")
assert "kotoba_aiueos_blk_wait(" in loop
head = """#include "common.h"
extern uint64_t kotoba_aiueos_blk_wait(uint64_t used, uint64_t used_length, uint64_t counter, uint64_t counter_length, uint64_t target, uint64_t msix, uint64_t start, uint64_t rounds);
int new_wait(struct crash_backend *b, uint32_t type, uint32_t budget_limit) {
  uint16_t old = b->submitted, target = old + 1;
"""
open(sys.argv[2], "w").write(head + loop + "  return 0;\n}\n")
