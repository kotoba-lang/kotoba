#include <stdint.h>

#define PCI_CONFIG_ADDRESS 0xcf8
#define PCI_CONFIG_DATA 0xcfc
#define VIRTIO_VENDOR_ID 0x1af4

static inline void out32(uint16_t port, uint32_t value) {
  __asm__ volatile("outl %0, %1" : : "a"(value), "Nd"(port));
}
static inline uint32_t in32(uint16_t port) {
  uint32_t value; __asm__ volatile("inl %1, %0" : "=a"(value) : "Nd"(port)); return value;
}
static uint32_t config_read(uint8_t bus, uint8_t device, uint8_t function, uint8_t offset) {
  uint32_t address = 0x80000000U | ((uint32_t)bus << 16) |
    ((uint32_t)device << 11) | ((uint32_t)function << 8) | (offset & 0xfcU);
  out32(PCI_CONFIG_ADDRESS, address);
  return in32(PCI_CONFIG_DATA);
}

int aiueos_pci_enumerate(void) {
  uint32_t present = 0, virtio = 0;
  for (uint16_t bus = 0; bus < 256; bus++) {
    for (uint8_t device = 0; device < 32; device++) {
      uint32_t identity0 = config_read((uint8_t)bus, device, 0, 0);
      if ((identity0 & 0xffffU) == 0xffffU) continue;
      uint8_t header = (uint8_t)(config_read((uint8_t)bus, device, 0, 0x0c) >> 16);
      uint8_t functions = (header & 0x80U) ? 8 : 1;
      for (uint8_t function = 0; function < functions; function++) {
        uint32_t identity = config_read((uint8_t)bus, device, function, 0);
        uint16_t vendor = (uint16_t)identity;
        if (vendor == 0xffffU) continue;
        present++;
        if (vendor == VIRTIO_VENDOR_ID) virtio++;
      }
    }
  }
  return present > 0 && virtio > 0;
}

