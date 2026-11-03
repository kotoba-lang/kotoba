#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- pci.c's net_udp_checksum and net_udp_rx_checksum_ok (the wrappers over
# kotoba/udp-checksum.o) as new_udp_checksum / new_udp_rx_checksum_ok. JUN-552.
import sys
src = open(sys.argv[1]).read()
def fn(start):
    a = src.index(start); return src[a:src.index("\n}\n", a) + 3]
ext = src[src.index("extern int64_t kotoba_aiueos_udp_checksum_sum("):]
ext = ext[:ext.index(";") + 1]
tx = fn("static uint16_t net_udp_checksum(const uint8_t *frame, uint32_t udp_length) {").replace(
    "static uint16_t net_udp_checksum(", "uint16_t new_udp_checksum(")
rx = fn("static int net_udp_rx_checksum_ok(const uint8_t *frame, uint32_t udp_length) {").replace(
    "static int net_udp_rx_checksum_ok(", "int new_udp_rx_checksum_ok(")
assert "kotoba_aiueos_udp_checksum_sum(" in tx and "kotoba_aiueos_udp_checksum_sum(" in rx
open(sys.argv[2], "w").write("#include <stdint.h>\n" + ext + "\n" + tx + "\n" + rx)
