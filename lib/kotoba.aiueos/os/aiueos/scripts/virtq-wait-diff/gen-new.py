#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- rng_refill's completion wait over kotoba/virtq-wait.o (as it is now in kernel/pci.c)
# as new_wait, with the 10^8 budget made a parameter and rng_backend's fields as parameters. JUN-598.
import sys
src = open(sys.argv[1]).read()
a = src.index("static int rng_refill(void) {")
lo = src.index("  for (uint32_t budget = 0; budget < 100000000U; budget += 65536U) {", a)
hi = src.index("  return 0;\n}", lo)
loop = src[lo:hi].replace("100000000U", "budget_limit").replace("rng_backend.used", "used").replace("rng_backend.posted", "posted")
loop = loop.replace("      return (uint32_t)kotoba_aiueos_virtq_used_elem((uint64_t)(uintptr_t)used, 4096, 0) == 32;", "      return 1;")
assert "kotoba_aiueos_virtq_wait(" in loop
head = """#include <stdint.h>
extern volatile uint64_t aiueos_virtio_rng_irq_count;
extern int64_t kotoba_aiueos_virtq_wait(uint64_t used, uint64_t used_length, uint64_t counter, uint64_t counter_length, uint64_t before, uint64_t want, uint64_t rounds);
int new_wait(void *used, uint64_t before, uint16_t posted, uint32_t budget_limit) {
"""
open(sys.argv[2], "w").write(head + loop + "  return 0;\n}\n")
