#!/usr/bin/env python3
# usage: gen-old.py PCI_C OUT -- the MSI-X programming as it was before JUN-598 (run once over main 4008b9d7's
# kernel/pci.c to write old.c, which is committed). JUN-598.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import extract
src = open(sys.argv[1]).read()
open(sys.argv[2], "w").write("/* setup_rng_msix's and setup_blk_msix's MSI-X programming before JUN-598 moved it to kotoba/msix-entry.o:\n"
  "   verbatim from kernel/pci.c (main 4008b9d7), between the table entry pointer and the MSI-X enable. */\n"
  '#include "common.h"\n' + extract(src, "old"))
