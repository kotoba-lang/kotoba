/* entry points for scripts/acpi-dmar-diff: reset the discovered globals as aiueos_acpi_initialize does, parse, report */
int PFX(parse)(const uint8_t *table) {
  discovered_dmar_drhd_count = 0; discovered_dmar_register_base = 0; discovered_dmar_segment = 0; discovered_dmar_include_all = 0;
  return parse_dmar((const struct sdt_header *)(const void *)table);
}
void PFX(state)(uint64_t s[4]) {
  s[0] = discovered_dmar_drhd_count; s[1] = discovered_dmar_register_base; s[2] = discovered_dmar_segment; s[3] = discovered_dmar_include_all;
}
