#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- pci.c's net_build_dns_query_named (the wrapper over kotoba/dns-query.o) as
# new_build_dns_query, over MAC globals new_set sets. JUN-552.
import sys
src = open(sys.argv[1]).read()
start = src.index("extern int64_t kotoba_aiueos_dns_query_build(")
end = src.index("\n}\n", src.index("static uint32_t net_build_dns_query_named(", start)) + 3
body = src[start:end].replace("static uint32_t net_build_dns_query_named(", "uint32_t new_build_dns_query(")
assert "new_build_dns_query(" in body and "kotoba_aiueos_dns_query_build(" in body
head = """#include <stdint.h>
static uint8_t net_mac[6], net_peer_mac[6];
void new_set(const uint8_t mac[6], const uint8_t peer[6]) {
  for (int i = 0; i < 6; i++) { net_mac[i] = mac[i]; net_peer_mac[i] = peer[i]; }
}
"""
open(sys.argv[2], "w").write(head + body)
