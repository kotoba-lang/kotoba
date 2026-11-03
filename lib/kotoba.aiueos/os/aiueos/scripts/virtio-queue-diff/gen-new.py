#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- pci.c's prepare_queue_index (the wrapper over kotoba/virtio-queue.o) as
# new_prepare_queue_index, with the structs it uses. JUN-598.
import sys
src = open(sys.argv[1]).read()
def blk(start, end):
    a = src.index(start); return src[a:src.index(end, a) + len(end)]
a = src.index("static volatile uint16_t *prepare_queue_index(volatile struct virtio_common_cfg *cfg,")
pq = src[a:src.index("\n}\n", a) + 3].replace("static volatile uint16_t *prepare_queue_index(", "volatile uint16_t *new_prepare_queue_index(")
assert "kotoba_aiueos_virtio_queue_setup(" in pq
parts = [blk("struct virtio_pci_cap {", "};"), blk("struct virtio_common_cfg {", "} __attribute__((packed));"),
         blk("struct virtq_desc {", "__attribute__((packed));"), blk("struct virtq_avail {", "__attribute__((packed));"),
         blk("struct virtq_used_element {", "__attribute__((packed));"), blk("struct virtq_used {", "__attribute__((packed));"),
         blk("struct virtio_caps {", "};")]
head = "#include <stdint.h>\nextern int64_t kotoba_aiueos_virtio_queue_setup(uint64_t cfg, uint64_t length, uint64_t record, uint64_t record_length);\n"
open(sys.argv[2], "w").write(head + "\n".join(parts) + "\n" + pq)
