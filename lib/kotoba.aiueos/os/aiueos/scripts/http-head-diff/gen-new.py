#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- pci.c's rtl8125_http_success (the wrapper over kotoba/http-head.o) as new_http_success,
# with the externs it calls; the cid offset is compared at the object's own export. JUN-552.
import sys
src = open(sys.argv[1]).read()
ext = src[src.index("extern int64_t kotoba_aiueos_http_cid_body("):]
ext = ext[:ext.index("static int net_http_cid_admit(")]
a = src.index("static int rtl8125_http_success(const uint8_t *bytes, uint32_t length) {")
rtl = src[a:src.index("\n}\n", a) + 3].replace("static int rtl8125_http_success(", "int new_http_success(")
assert "kotoba_aiueos_http_success(" in rtl
open(sys.argv[2], "w").write("#include <stdint.h>\n" + ext + rtl)
