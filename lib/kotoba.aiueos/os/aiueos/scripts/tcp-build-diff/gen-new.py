#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- pci.c's net_build_tcp (the wrapper over kotoba/tcp-build.o) as new_build_tcp, over
# globals new_set sets. JUN-552.
import sys
src = open(sys.argv[1]).read()
start = src.index("extern int64_t kotoba_aiueos_tcp_build(")
body = src[start:src.index("static int net_tcp_send(struct net_ring *tx", start)]
body = body.replace("static uint32_t net_build_tcp(", "uint32_t new_build_tcp(")
assert "new_build_tcp(" in body and "kotoba_aiueos_tcp_build(" in body
head = """#include <stdint.h>
static uint8_t net_mac[6], net_peer_mac[6];
static uint16_t net_tx_window, net_ip_id;
void new_set(const uint8_t mac[6], const uint8_t peer[6], uint16_t window, uint16_t id) {
  for (int i = 0; i < 6; i++) { net_mac[i] = mac[i]; net_peer_mac[i] = peer[i]; }
  net_tx_window = window; net_ip_id = id;
}
uint16_t new_ip_id(void) { return net_ip_id; }
"""
open(sys.argv[2], "w").write(head + body)
