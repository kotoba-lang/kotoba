#ifndef AIUEOS_NATIVE_ETHERNET_H
#define AIUEOS_NATIVE_ETHERNET_H

#include <stdint.h>

#define AIUEOS_ETHERNET_CLASS_NETWORK 0x02U
#define AIUEOS_ETHERNET_SUBCLASS_ETHERNET 0x00U
#define AIUEOS_PCI_VENDOR_INTEL 0x8086U
#define AIUEOS_PCI_VENDOR_REALTEK 0x10ecU

enum aiueos_ethernet_driver_family {
  AIUEOS_ETHERNET_DRIVER_NONE = 0,
  AIUEOS_ETHERNET_DRIVER_INTEL_IGC_FOUNDATION = 1,
  AIUEOS_ETHERNET_DRIVER_REALTEK_2P5G_FOUNDATION = 2
};

struct aiueos_ethernet_inventory {
  uint16_t vendor_id;
  uint16_t device_id;
  uint8_t revision_id;
  uint8_t class_code;
  uint8_t subclass;
  uint8_t programming_interface;
  enum aiueos_ethernet_driver_family driver_family;
  uint8_t supported;
};

int aiueos_ethernet_inventory(uint16_t vendor_id, uint16_t device_id,
                              uint8_t revision_id, uint8_t class_code,
                              uint8_t subclass, uint8_t programming_interface,
                              struct aiueos_ethernet_inventory *out);
const char *aiueos_ethernet_driver_name(
    enum aiueos_ethernet_driver_family family);

#endif
