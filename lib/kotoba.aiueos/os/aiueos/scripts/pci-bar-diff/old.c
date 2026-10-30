/* The C read_bar and bar_extent were before JUN-598 moved their arithmetic to kotoba/pci-bar.o: verbatim from
   kernel/pci.c (main 56499ac0), renamed old_*. config_read / config_write are the driver's emulated device;
   kotoba_aiueos_pci_extent_valid is kotoba/pci-extent-valid.o, as in the kernel. */
#include <stdint.h>
uint32_t config_read(uint8_t bus, uint8_t dev, uint8_t fn, uint8_t off);
void config_write(uint8_t bus, uint8_t dev, uint8_t fn, uint8_t off, uint32_t value);
extern uint64_t kotoba_aiueos_pci_extent_valid(uint64_t value, uint64_t size);
int old_read_bar(uint8_t b, uint8_t d, uint8_t f, uint8_t index, uint64_t *base) {
  if (index >= 6 || !base) return 0;
  uint32_t low = config_read(b,d,f,(uint8_t)(0x10 + index * 4));
  if (low & 1) return 0; /* Port BARs cannot carry modern virtio capabilities. */
  uint32_t type = (low >> 1) & 3;
  uint64_t value = low & ~0xfU;
  if (type == 2) {
    if (index == 5) return 0;
    value |= (uint64_t)config_read(b,d,f,(uint8_t)(0x14 + index * 4)) << 32;
  } else if (type != 0) return 0;
  if (!value || value == 0xfffffff0ULL) return 0;
  *base = value; return 1;
}

int old_bar_extent(uint8_t b, uint8_t d, uint8_t f, uint8_t index,
                      uint64_t *base, uint64_t *length) {
  if (index >= 6 || !base || !length) return 0;
  uint8_t offset = (uint8_t)(0x10 + index * 4);
  uint32_t command = config_read(b,d,f,0x04);
  uint32_t low = config_read(b,d,f,offset), high = 0;
  if ((low & 1) || (((low >> 1) & 3) != 0 && ((low >> 1) & 3) != 2)) return 0;
  int wide = ((low >> 1) & 3) == 2;
  if (wide) { if (index == 5) return 0; high = config_read(b,d,f,offset + 4); }
  config_write(b,d,f,0x04,command & ~3U);
  config_write(b,d,f,offset,0xffffffffU);
  if (wide) config_write(b,d,f,offset + 4,0xffffffffU);
  uint64_t mask = (uint64_t)(config_read(b,d,f,offset) & ~0xfU);
  if (wide) mask |= (uint64_t)config_read(b,d,f,offset + 4) << 32;
  config_write(b,d,f,offset,low);
  if (wide) config_write(b,d,f,offset + 4,high);
  config_write(b,d,f,0x04,command);
  uint64_t value = (uint64_t)(low & ~0xfU) | ((uint64_t)high << 32);
  uint64_t size = wide ? (~mask) + 1 : (uint64_t)(~(uint32_t)mask + 1U);
  if (!kotoba_aiueos_pci_extent_valid(value,size) || value + size < value) return 0;
  *base = value; *length = size; return 1;
}
