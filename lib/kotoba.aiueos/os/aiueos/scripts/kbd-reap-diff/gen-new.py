#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- kbd_recycle over kotoba/kbd-reap.o (as it is now in kernel/pci.c) as new_recycle, with
# its position and event counter renamed new_*. JUN-598.
import sys
src = open(sys.argv[1]).read()
lo = src.index("static uint32_t kbd_recycle(int want_press) {")
hi = src.index("  return press;\n}\n", lo) + len("  return press;\n}\n")
f = src[lo:hi].replace("static uint32_t kbd_recycle(", "uint32_t new_recycle(")
assert "kotoba_aiueos_kbd_reap(" in f
head = """#include "common.h"
#define kbd_seen new_seen
#define aiueos_input_ring_events new_events
uint16_t kbd_seen; uint32_t aiueos_input_ring_events;
extern uint64_t kotoba_aiueos_kbd_reap(uint64_t used, uint64_t used_length, uint64_t avail, uint64_t avail_length, uint64_t event, uint64_t event_length, uint64_t state);
"""
open(sys.argv[2], "w").write(head + f)
