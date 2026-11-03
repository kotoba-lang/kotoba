# usage: gen-new.py ACPI_C OUT -- kernel/acpi.c's current parse_dmar over the same header, globals and epilogue. JUN-552.
import sys
src = open(sys.argv[1]).read()
hdr = src[src.index('struct __attribute__((packed)) sdt_header {'):src.index('struct __attribute__((packed)) madt_header {')]
glob = """static uint32_t discovered_dmar_drhd_count;
static uint64_t discovered_dmar_register_base;
static uint16_t discovered_dmar_segment;
static uint8_t discovered_dmar_include_all;
"""
a = src.index('/* The DMAR walk is kotoba/acpi-dmar-parse.kotoba'); b = src.index('int aiueos_acpi_initialize(', a)
open(sys.argv[2], 'w').write('#include <stdint.h>\n#include <stddef.h>\n#define PFX(x) new_##x\n' + hdr + glob + src[a:b] + '#include "epilogue.h"\n')
