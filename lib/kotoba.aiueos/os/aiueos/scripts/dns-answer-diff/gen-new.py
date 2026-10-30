#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- pci.c's net_dns_answer_ok_named (the wrapper over kotoba/dns-answer.o) as
# new_dns_answer_ok_named, with the extern it calls. JUN-552.
import sys
src = open(sys.argv[1]).read()
start = src.index("extern int64_t kotoba_aiueos_dns_answer(")
body = src[start:src.index("static int net_dns_probe(", start)]
body = body.replace("static int net_dns_answer_ok_named(", "int new_dns_answer_ok_named(")
assert "new_dns_answer_ok_named(" in body and "kotoba_aiueos_dns_answer(" in body
open(sys.argv[2], "w").write("#include <stdint.h>\n" + body)
