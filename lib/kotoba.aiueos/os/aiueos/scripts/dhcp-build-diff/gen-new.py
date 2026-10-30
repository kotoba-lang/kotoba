#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- pci.c's net_build_dhcp (the wrapper over kotoba/dhcp-build.o) as new_build_dhcp,
# over a net_mac new_set sets. JUN-552.
import sys
src = open(sys.argv[1]).read()
start = src.index("extern int64_t kotoba_aiueos_dhcp_build(")
end = src.index("\n}\n", src.index("static uint32_t net_build_dhcp(", start)) + 3
body = src[start:end].replace("static uint32_t net_build_dhcp(", "uint32_t new_build_dhcp(")
assert "new_build_dhcp(" in body and "kotoba_aiueos_dhcp_build(" in body
head = """#include <stdint.h>
#define NET_DHCP_OPTIONS 64
#define NET_DHCP_BOOTP (236 + 4 + NET_DHCP_OPTIONS)
static uint8_t net_mac[6];
void new_set(const uint8_t mac[6]) { for (int i = 0; i < 6; i++) net_mac[i] = mac[i]; }
"""
open(sys.argv[2], "w").write(head + body)
