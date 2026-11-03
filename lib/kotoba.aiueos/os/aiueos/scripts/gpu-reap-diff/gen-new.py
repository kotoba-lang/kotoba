#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- gpu_ctrl over kotoba/gpu-reap.o (as it is now in kernel/pci.c) as new_ctrl, its 10^8
# budget the harness's budget_limit and its driver globals renamed new_*. JUN-598.
import sys
src = open(sys.argv[1]).read()
lo = src.index("static int gpu_ctrl(struct virtq_desc *desc, struct virtq_avail *avail,")
hi = src.index("  return 0;\n}\n", lo) + len("  return 0;\n}\n")
f = src[lo:hi].replace("static int gpu_ctrl(", "int new_ctrl(").replace("100000000U", "budget_limit")
assert "kotoba_aiueos_gpu_reap(" in f
head = """#include "common.h"
#define gpu_event_buf new_event_buf
#define gpu_avail_next new_avail_next
#define gpu_used_consumed new_used_consumed
#define gpu_display_events new_display_events
struct virtio_gpu_event gpu_event_buf; uint16_t gpu_avail_next, gpu_used_consumed; uint32_t gpu_display_events;
extern uint64_t kotoba_aiueos_gpu_reap(uint64_t used, uint64_t used_length, uint64_t resp, uint64_t resp_length,
                                       uint64_t state, uint64_t resp_len, uint64_t expect);
"""
open(sys.argv[2], "w").write(head + f)
