#!/usr/bin/env python3
# usage: gen-new.py PLC_RUNTIME_C OUT -- aiueos_plc_rt_begin_scan's wait over kotoba/tick-wait.o (as it is now in
# kernel/plc_runtime.c) as new_wait, with plc.next_release a parameter. JUN-554.
import sys
src = open(sys.argv[1]).read()
lo = src.index("  /* kotoba/tick-wait.o: look, then sti; hlt; cli, until the tick counter\n")
hi = src.index("  uint64_t release=plc.next_release;\n", lo)
loop = src[lo:hi]
assert "kotoba_aiueos_tick_wait(" in loop
open(sys.argv[2], "w").write("""#include <stdint.h>
extern volatile uint64_t aiueos_apic_timer_ticks;
extern uint64_t kotoba_aiueos_tick_wait(uint64_t ticks, uint64_t ticks_length, uint64_t target, uint64_t rounds);
struct plc_state { uint64_t next_release; };
void new_wait(uint64_t next_release) {
  struct plc_state plc = {next_release};
""" + loop + "}\n")
