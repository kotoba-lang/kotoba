/* entry points for scripts/acpi-madt-diff: reset as aiueos_acpi_initialize does, walk the MADT, report */
int PFX(parse)(const uint8_t *table) {
  discovered_cpu_count = 0; discovered_ioapic_address = 0; discovered_ioapic_gsi_base = 0; discovered_timer_gsi = 0;
  for (int i = 0; i < 256; i++) discovered_apic_ids[i] = 0;
  return PFX(walk)((const struct madt_header *)(const void *)table);
}
void PFX(state)(uint32_t s[260]) {
  s[0] = discovered_cpu_count; s[1] = discovered_ioapic_address; s[2] = discovered_ioapic_gsi_base; s[3] = discovered_timer_gsi;
  for (int i = 0; i < 256; i++) s[4 + i] = discovered_apic_ids[i];
}
