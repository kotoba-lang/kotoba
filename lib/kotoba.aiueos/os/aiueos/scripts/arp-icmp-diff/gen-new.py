#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- pci.c's net_build_arp_request and net_build_icmp_echo (the wrappers over
# kotoba/arp-icmp-build.o) as new_build_arp_request / new_build_icmp_echo, over MAC globals new_set sets. JUN-552.
import sys
src = open(sys.argv[1]).read()
def fn(start):
    a = src.index(start); return src[a:src.index("\n}\n", a) + 3]
ext = src[src.index("extern int64_t kotoba_aiueos_arp_request_build("):]
ext = ext[:ext.index("static uint32_t net_build_arp_request(")]
arp = fn("static uint32_t net_build_arp_request(uint8_t *frame) {").replace("static uint32_t net_build_arp_request(", "uint32_t new_build_arp_request(")
icmp = fn("static uint32_t net_build_icmp_echo(uint8_t *frame) {").replace("static uint32_t net_build_icmp_echo(", "uint32_t new_build_icmp_echo(")
assert "kotoba_aiueos_arp_request_build(" in arp and "kotoba_aiueos_icmp_echo_build(" in icmp
head = """#include <stdint.h>
static uint8_t net_mac[6], net_peer_mac[6];
void new_set(const uint8_t mac[6], const uint8_t peer[6]) {
  for (int i = 0; i < 6; i++) { net_mac[i] = mac[i]; net_peer_mac[i] = peer[i]; }
}
"""
open(sys.argv[2], "w").write(head + ext + arp + "\n" + icmp)
