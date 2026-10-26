#include "xhci.h"

#define XHCI_PORTSC_BASE 0x400U
#define XHCI_PORT_REGISTER_STRIDE 0x10U
#define XHCI_TRB_BYTES 16U
#define XHCI_ERST_ENTRY_BYTES 16U

static int report_contains(const struct aiueos_usb_boot_report *report,
                           uint8_t usage) {
  size_t i;
  for (i = 0U; i < AIUEOS_USB_BOOT_KEY_CAPACITY; ++i) {
    if (report->keys[i] == usage) {
      return 1;
    }
  }
  return 0;
}

int aiueos_xhci_pci_admit(uint8_t class_code, uint8_t subclass,
                          uint8_t programming_interface) {
  return class_code == AIUEOS_XHCI_CLASS_SERIAL_BUS &&
         subclass == AIUEOS_XHCI_SUBCLASS_USB &&
         programming_interface == AIUEOS_XHCI_PROGIF_XHCI;
}

int aiueos_xhci_capability_parse(uint8_t capability_length,
                                 uint16_t interface_version,
                                 uint32_t hcsparams1, uint32_t hccparams1,
                                 uint32_t doorbell_offset,
                                 uint32_t runtime_offset,
                                 uint64_t mapped_length,
                                 struct aiueos_xhci_capability *out) {
  uint32_t max_slots = hcsparams1 & 0xffU;
  uint32_t max_interrupters = (hcsparams1 >> 8U) & 0x7ffU;
  uint32_t max_ports = (hcsparams1 >> 24U) & 0xffU;
  uint32_t ext = ((hccparams1 >> 16U) & 0xffffU) * 4U;
  uint32_t db = doorbell_offset & ~UINT32_C(3);
  uint32_t runtime = runtime_offset & ~UINT32_C(0x1f);

  if (out == NULL || capability_length < 0x20U ||
      interface_version < 0x0096U || interface_version >= 0x0200U ||
      max_slots == 0U || max_interrupters == 0U || max_ports == 0U ||
      db < capability_length || runtime < capability_length ||
      (uint64_t)db + 4U > mapped_length ||
      (uint64_t)runtime + 0x20U > mapped_length ||
      (ext != 0U && ((uint64_t)ext + 4U > mapped_length ||
                     ext < capability_length))) {
    return 0;
  }
  out->capability_length = capability_length;
  out->interface_version = interface_version;
  out->max_slots = (uint8_t)max_slots;
  out->max_interrupters = (uint16_t)max_interrupters;
  out->max_ports = (uint8_t)max_ports;
  out->doorbell_offset = db;
  out->runtime_offset = runtime;
  out->extended_capability_offset = ext;
  return 1;
}

int aiueos_xhci_extended_cap_next(uint32_t current_offset,
                                  uint32_t capability_header,
                                  uint64_t mapped_length,
                                  uint32_t *next_offset) {
  uint32_t delta = ((capability_header >> 8U) & 0xffU) * 4U;
  uint32_t next;

  if (next_offset == NULL || (current_offset & 3U) != 0U ||
      (uint64_t)current_offset + 4U > mapped_length) {
    return 0;
  }
  if (delta == 0U) {
    *next_offset = 0U;
    return 1;
  }
  if (delta > UINT32_MAX - current_offset) {
    return 0;
  }
  next = current_offset + delta;
  if (next <= current_offset || (uint64_t)next + 4U > mapped_length) {
    return 0;
  }
  *next_offset = next;
  return 1;
}

int aiueos_xhci_port_plan(const struct aiueos_xhci_capability *cap,
                          uint8_t port_number, uint64_t mapped_length,
                          struct aiueos_xhci_port_plan *out) {
  uint32_t offset;
  if (cap == NULL || out == NULL || port_number == 0U ||
      port_number > cap->max_ports) {
    return 0;
  }
  offset = XHCI_PORTSC_BASE +
           ((uint32_t)port_number - 1U) * XHCI_PORT_REGISTER_STRIDE;
  if ((uint64_t)offset + 4U > mapped_length) {
    return 0;
  }
  out->port_number = port_number;
  out->portsc_offset = offset;
  return 1;
}

int aiueos_xhci_ring_plan(uint64_t command_ring_dma, uint16_t command_trbs,
                          uint64_t event_ring_dma, uint16_t event_trbs,
                          uint64_t erst_dma,
                          const struct aiueos_dma_window *window,
                          struct aiueos_xhci_ring_plan *out) {
  size_t command_bytes;
  size_t event_bytes;

  if (out == NULL || command_trbs < 16U || event_trbs < 16U ||
      command_trbs > 4096U || event_trbs > 4096U ||
      (size_t)command_trbs > SIZE_MAX / XHCI_TRB_BYTES ||
      (size_t)event_trbs > SIZE_MAX / XHCI_TRB_BYTES) {
    return 0;
  }
  command_bytes = (size_t)command_trbs * XHCI_TRB_BYTES;
  event_bytes = (size_t)event_trbs * XHCI_TRB_BYTES;
  if (!aiueos_dma_range_admit(window, command_ring_dma, command_bytes, 64U) ||
      !aiueos_dma_range_admit(window, event_ring_dma, event_bytes, 64U) ||
      !aiueos_dma_range_admit(window, erst_dma, XHCI_ERST_ENTRY_BYTES, 64U) ||
      (command_ring_dma & UINT64_C(0xffff)) + command_bytes > UINT64_C(0x10000) ||
      (event_ring_dma & UINT64_C(0xffff)) + event_bytes > UINT64_C(0x10000) ||
      !aiueos_dma_ranges_disjoint(command_ring_dma, command_bytes,
                                  event_ring_dma, event_bytes) ||
      !aiueos_dma_ranges_disjoint(command_ring_dma, command_bytes, erst_dma,
                                  XHCI_ERST_ENTRY_BYTES) ||
      !aiueos_dma_ranges_disjoint(event_ring_dma, event_bytes, erst_dma,
                                  XHCI_ERST_ENTRY_BYTES)) {
    return 0;
  }
  out->command_ring_dma = command_ring_dma;
  out->event_ring_dma = event_ring_dma;
  out->erst_dma = erst_dma;
  out->command_trbs = command_trbs;
  out->event_trbs = event_trbs;
  return 1;
}

int aiueos_usb_boot_keyboard_plan(uint8_t configuration_value,
                                  uint8_t interface_number,
                                  uint8_t endpoint_address,
                                  uint16_t max_packet_size, uint8_t interval,
                                  struct aiueos_usb_boot_keyboard_plan *out) {
  if (out == NULL || configuration_value == 0U ||
      (endpoint_address & 0x80U) == 0U || (endpoint_address & 0x70U) != 0U ||
      (endpoint_address & 0x0fU) == 0U || max_packet_size < 8U ||
      max_packet_size > 64U || interval == 0U) {
    return 0;
  }
  out->configuration_value = configuration_value;
  out->interface_number = interface_number;
  out->endpoint_address = endpoint_address;
  out->max_packet_size = max_packet_size;
  out->interval = interval;
  out->set_protocol_value = 0U; /* USB HID boot protocol. */
  return 1;
}

int aiueos_usb_boot_report_parse(const uint8_t *bytes, size_t length,
                                  struct aiueos_usb_boot_report *out) {
  size_t i;
  size_t j;
  if (bytes == NULL || out == NULL ||
      length != AIUEOS_USB_BOOT_KEYBOARD_REPORT_BYTES || bytes[1] != 0U) {
    return 0;
  }
  for (i = 2U; i < AIUEOS_USB_BOOT_KEYBOARD_REPORT_BYTES; ++i) {
    if (bytes[i] >= 1U && bytes[i] <= 3U) {
      return 0; /* ErrorRollOver, POSTFail, ErrorUndefined. */
    }
    if (bytes[i] == 0U) {
      continue;
    }
    for (j = i + 1U; j < AIUEOS_USB_BOOT_KEYBOARD_REPORT_BYTES; ++j) {
      if (bytes[i] == bytes[j]) {
        return 0;
      }
    }
  }
  out->modifiers = bytes[0];
  for (i = 0U; i < AIUEOS_USB_BOOT_KEY_CAPACITY; ++i) {
    out->keys[i] = bytes[i + 2U];
  }
  return 1;
}

int aiueos_usb_boot_report_events(
    const struct aiueos_usb_boot_report *previous,
    const struct aiueos_usb_boot_report *current,
    struct aiueos_usb_key_event *events, size_t event_capacity,
    size_t *event_count) {
  size_t needed = 0U;
  size_t i;
  uint8_t bit;

  if (previous == NULL || current == NULL || events == NULL ||
      event_count == NULL) {
    return 0;
  }
  for (bit = 0U; bit < 8U; ++bit) {
    if (((previous->modifiers ^ current->modifiers) & (uint8_t)(1U << bit)) != 0U) {
      ++needed;
    }
  }
  for (i = 0U; i < AIUEOS_USB_BOOT_KEY_CAPACITY; ++i) {
    if (previous->keys[i] != 0U && !report_contains(current, previous->keys[i])) {
      ++needed;
    }
    if (current->keys[i] != 0U && !report_contains(previous, current->keys[i])) {
      ++needed;
    }
  }
  if (needed > event_capacity) {
    return 0;
  }
  needed = 0U;
  for (bit = 0U; bit < 8U; ++bit) {
    uint8_t mask = (uint8_t)(1U << bit);
    if (((previous->modifiers ^ current->modifiers) & mask) != 0U) {
      events[needed++] = (struct aiueos_usb_key_event){
          (uint8_t)(0xe0U + bit),
          (uint8_t)((current->modifiers & mask) != 0U)};
    }
  }
  for (i = 0U; i < AIUEOS_USB_BOOT_KEY_CAPACITY; ++i) {
    if (previous->keys[i] != 0U && !report_contains(current, previous->keys[i])) {
      events[needed++] =
          (struct aiueos_usb_key_event){previous->keys[i], 0U};
    }
  }
  for (i = 0U; i < AIUEOS_USB_BOOT_KEY_CAPACITY; ++i) {
    if (current->keys[i] != 0U && !report_contains(previous, current->keys[i])) {
      events[needed++] =
          (struct aiueos_usb_key_event){current->keys[i], 1U};
    }
  }
  *event_count = needed;
  return 1;
}
