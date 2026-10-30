# usage: gen-new.py ACPI_C OUT -- kernel/acpi.c's current MADT tail over the same headers, globals and epilogue. JUN-552.
import sys
src = open(sys.argv[1]).read()
hdr = src[src.index('struct __attribute__((packed)) sdt_header {'):src.index('static uint32_t discovered_apic_ids[256];')]
glob = """static uint32_t discovered_apic_ids[256];
static uint32_t discovered_cpu_count;
static uint32_t discovered_ioapic_address;
static uint32_t discovered_ioapic_gsi_base;
static uint32_t discovered_timer_gsi;
"""
helpers = src[src.index('extern int64_t kotoba_aiueos_acpi_madt_parse('):src.index('int aiueos_acpi_initialize(')]
a = src.index('  /* The MADT walk is kotoba/acpi-madt-parse.kotoba')
b = src.index('\n}\n', a) + 3
open(sys.argv[2], 'w').write('#include <stdint.h>\n#include <stddef.h>\n#define PFX(x) new_##x\n' + hdr + glob + helpers +
  'static int PFX(walk)(const struct madt_header *madt) {\n' + src[a:b] + '#include "epilogue.h"\n')
