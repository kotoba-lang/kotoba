#include "ethernet.h"

#include <stddef.h>

struct supported_pci_id {
  uint16_t vendor;
  uint16_t device;
  enum aiueos_ethernet_driver_family family;
};

/* Matching means the bounded foundation recognizes the controller family.
   It does not mean MMIO, PHY, queue, interrupt, or packet I/O is implemented. */
static const struct supported_pci_id supported_ids[] = {
    {AIUEOS_PCI_VENDOR_INTEL, 0x15f2U, AIUEOS_ETHERNET_DRIVER_INTEL_IGC_FOUNDATION}, /* I225-LM */
    {AIUEOS_PCI_VENDOR_INTEL, 0x15f3U, AIUEOS_ETHERNET_DRIVER_INTEL_IGC_FOUNDATION}, /* I225-V */
    {AIUEOS_PCI_VENDOR_INTEL, 0x125bU, AIUEOS_ETHERNET_DRIVER_INTEL_IGC_FOUNDATION}, /* I226-LM */
    {AIUEOS_PCI_VENDOR_INTEL, 0x125cU, AIUEOS_ETHERNET_DRIVER_INTEL_IGC_FOUNDATION}, /* I226-V */
    {AIUEOS_PCI_VENDOR_REALTEK, 0x8125U, AIUEOS_ETHERNET_DRIVER_REALTEK_2P5G_FOUNDATION},
    {AIUEOS_PCI_VENDOR_REALTEK, 0x8126U, AIUEOS_ETHERNET_DRIVER_REALTEK_2P5G_FOUNDATION},
};

int aiueos_ethernet_inventory(uint16_t vendor_id, uint16_t device_id,
                              uint8_t revision_id, uint8_t class_code,
                              uint8_t subclass, uint8_t programming_interface,
                              struct aiueos_ethernet_inventory *out) {
  size_t i;

  if (out == NULL || vendor_id == UINT16_MAX || vendor_id == 0U ||
      class_code != AIUEOS_ETHERNET_CLASS_NETWORK ||
      subclass != AIUEOS_ETHERNET_SUBCLASS_ETHERNET) {
    return 0;
  }
  out->vendor_id = vendor_id;
  out->device_id = device_id;
  out->revision_id = revision_id;
  out->class_code = class_code;
  out->subclass = subclass;
  out->programming_interface = programming_interface;
  out->driver_family = AIUEOS_ETHERNET_DRIVER_NONE;
  out->supported = 0U;
  for (i = 0U; i < sizeof(supported_ids) / sizeof(supported_ids[0]); ++i) {
    if (supported_ids[i].vendor == vendor_id && supported_ids[i].device == device_id) {
      out->driver_family = supported_ids[i].family;
      out->supported = 1U;
      break;
    }
  }
  return 1;
}

const char *aiueos_ethernet_driver_name(
    enum aiueos_ethernet_driver_family family) {
  switch (family) {
    case AIUEOS_ETHERNET_DRIVER_INTEL_IGC_FOUNDATION:
      return "intel-igc-foundation";
    case AIUEOS_ETHERNET_DRIVER_REALTEK_2P5G_FOUNDATION:
      return "realtek-2p5g-foundation";
    case AIUEOS_ETHERNET_DRIVER_NONE:
    default:
      return "unsupported";
  }
}
