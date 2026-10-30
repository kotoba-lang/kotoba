#!/usr/bin/env python3
# usage: gen-new.py PCI_C OUT -- the MSI-X programming over kotoba/msix-entry.o, as it is now in kernel/pci.c. JUN-598.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import extract
src = open(sys.argv[1]).read()
body = extract(src, "new")
assert body.count("kotoba_aiueos_msix_program(") == 2
open(sys.argv[2], "w").write('#include "common.h"\nextern uint64_t kotoba_aiueos_msix_program(uint64_t entry, uint64_t entry_length, '
  'uint64_t cfg, uint64_t cfg_length, uint64_t address, uint64_t data, uint64_t vector);\n' + body)
