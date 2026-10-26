#ifndef AIUEOS_NATIVE_XHCI_H
#define AIUEOS_NATIVE_XHCI_H

#include <stddef.h>
#include <stdint.h>

#include "native_dma.h"

#define AIUEOS_XHCI_CLASS_SERIAL_BUS 0x0cU
#define AIUEOS_XHCI_SUBCLASS_USB 0x03U
#define AIUEOS_XHCI_PROGIF_XHCI 0x30U
#define AIUEOS_USB_BOOT_KEYBOARD_REPORT_BYTES 8U
#define AIUEOS_USB_BOOT_KEY_CAPACITY 6U
#define AIUEOS_USB_KEY_EVENT_CAPACITY 20U

struct aiueos_xhci_capability {
  uint8_t capability_length;
  uint16_t interface_version;
  uint8_t max_slots;
  uint16_t max_interrupters;
  uint8_t max_ports;
  uint32_t doorbell_offset;
  uint32_t runtime_offset;
  uint32_t extended_capability_offset;
};

struct aiueos_xhci_port_plan {
  uint8_t port_number;
  uint32_t portsc_offset;
};

struct aiueos_xhci_ring_plan {
  uint64_t command_ring_dma;
  uint64_t event_ring_dma;
  uint64_t erst_dma;
  uint16_t command_trbs;
  uint16_t event_trbs;
};

struct aiueos_usb_boot_keyboard_plan {
  uint8_t configuration_value;
  uint8_t interface_number;
  uint8_t endpoint_address;
  uint16_t max_packet_size;
  uint8_t interval;
  uint8_t set_protocol_value;
};

struct aiueos_usb_key_event {
  uint8_t usage;
  uint8_t pressed;
};

struct aiueos_usb_boot_report {
  uint8_t modifiers;
  uint8_t keys[AIUEOS_USB_BOOT_KEY_CAPACITY];
};

int aiueos_xhci_pci_admit(uint8_t class_code, uint8_t subclass,
                          uint8_t programming_interface);
int aiueos_xhci_capability_parse(uint8_t capability_length,
                                 uint16_t interface_version,
                                 uint32_t hcsparams1, uint32_t hccparams1,
                                 uint32_t doorbell_offset,
                                 uint32_t runtime_offset,
                                 uint64_t mapped_length,
                                 struct aiueos_xhci_capability *out);
int aiueos_xhci_extended_cap_next(uint32_t current_offset,
                                  uint32_t capability_header,
                                  uint64_t mapped_length,
                                  uint32_t *next_offset);
int aiueos_xhci_port_plan(const struct aiueos_xhci_capability *cap,
                          uint8_t port_number, uint64_t mapped_length,
                          struct aiueos_xhci_port_plan *out);
int aiueos_xhci_ring_plan(uint64_t command_ring_dma, uint16_t command_trbs,
                          uint64_t event_ring_dma, uint16_t event_trbs,
                          uint64_t erst_dma,
                          const struct aiueos_dma_window *window,
                          struct aiueos_xhci_ring_plan *out);
int aiueos_usb_boot_keyboard_plan(uint8_t configuration_value,
                                  uint8_t interface_number,
                                  uint8_t endpoint_address,
                                  uint16_t max_packet_size, uint8_t interval,
                                  struct aiueos_usb_boot_keyboard_plan *out);
int aiueos_usb_boot_report_parse(const uint8_t *bytes, size_t length,
                                  struct aiueos_usb_boot_report *out);
int aiueos_usb_boot_report_events(
    const struct aiueos_usb_boot_report *previous,
    const struct aiueos_usb_boot_report *current,
    struct aiueos_usb_key_event *events, size_t event_capacity,
    size_t *event_count);

#endif
