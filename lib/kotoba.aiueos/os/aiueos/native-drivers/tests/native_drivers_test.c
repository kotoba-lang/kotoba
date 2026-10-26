#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "ethernet.h"
#include "nvme.h"
#include "xhci.h"

static unsigned failures;
static unsigned checks;

#define CHECK(condition)                                                        \
  do {                                                                          \
    ++checks;                                                                    \
    if (!(condition)) {                                                         \
      fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #condition);    \
      ++failures;                                                               \
    }                                                                           \
  } while (0)

static struct aiueos_dma_window test_window(void) {
  return (struct aiueos_dma_window){UINT64_C(0x100000), UINT64_C(0x1fffff), 1U};
}

static void test_dma(void) {
  struct aiueos_dma_window window = test_window();
  CHECK(aiueos_dma_range_admit(&window, UINT64_C(0x101000), 4096U, 4096U));
  CHECK(!aiueos_dma_range_admit(&window, UINT64_C(0x101001), 4096U, 4096U));
  CHECK(!aiueos_dma_range_admit(&window, UINT64_MAX - 7U, 16U, 1U));
  CHECK(!aiueos_dma_range_admit(&window, UINT64_C(0x100000), 4096U, 3U));
  CHECK(aiueos_dma_ranges_disjoint(UINT64_C(0x1000), 16U,
                                   UINT64_C(0x1010), 16U));
  CHECK(!aiueos_dma_ranges_disjoint(UINT64_C(0x1000), 16U,
                                    UINT64_C(0x100f), 16U));
  window.translated = 0U;
  CHECK(!aiueos_dma_range_admit(&window, UINT64_C(0x101000), 4096U, 4096U));
}

static void test_nvme(void) {
  struct aiueos_nvme_capability cap;
  struct aiueos_nvme_queue_plan queue;
  struct aiueos_nvme_command_plan command;
  struct aiueos_dma_window window = test_window();
  uint64_t base = 0U;
  uint64_t raw = UINT64_C(63) | (UINT64_C(1) << 16U) |
                 (UINT64_C(10) << 24U) | (UINT64_C(1) << 32U) |
                 (UINT64_C(1) << 37U) | (UINT64_C(2) << 52U);

  CHECK(aiueos_nvme_pci_admit(0x01U, 0x08U, 0x02U));
  CHECK(!aiueos_nvme_pci_admit(0x01U, 0x06U, 0x01U));
  CHECK(aiueos_nvme_bar0_admit(0x00004004U, 0x00000001U, 0x4000U, &base));
  CHECK(base == UINT64_C(0x100004000));
  CHECK(!aiueos_nvme_bar0_admit(0x0000c001U, 0U, 0x4000U, &base));
  CHECK(!aiueos_nvme_bar0_admit(0x00004002U, 0U, 0x4000U, &base));
  CHECK(!aiueos_nvme_bar0_admit(0xfffff004U, 0xffffffffU, 0x4000U, &base));

  CHECK(aiueos_nvme_capability_parse(raw, &cap));
  CHECK(cap.max_queue_entries == 64U);
  CHECK(cap.doorbell_stride == 8U);
  CHECK(cap.min_page_size == 4096U && cap.max_page_size == 16384U);
  CHECK(!aiueos_nvme_capability_parse(raw & ~(UINT64_C(1) << 37U), &cap));
  CHECK(!aiueos_nvme_capability_parse(
      (raw & ~(UINT64_C(0xff) << 48U)) | (UINT64_C(3) << 48U) |
          (UINT64_C(2) << 52U),
      &cap));
  CHECK(!aiueos_nvme_capability_parse(
      (raw & ~(UINT64_C(0xf) << 32U)) | (UINT64_C(7) << 32U), &cap));

  CHECK(aiueos_nvme_queue_plan(&cap, 4096U, 32U, UINT64_C(0x101000),
                               UINT64_C(0x102000), &window, &queue));
  CHECK(queue.submission_bytes == 2048U && queue.completion_bytes == 512U);
  CHECK(!aiueos_nvme_queue_plan(&cap, 4096U, 65U, UINT64_C(0x101000),
                                UINT64_C(0x102000), &window, &queue));
  CHECK(!aiueos_nvme_queue_plan(&cap, 4096U, 32U, UINT64_C(0x101001),
                                UINT64_C(0x102000), &window, &queue));
  CHECK(!aiueos_nvme_queue_plan(&cap, 4096U, 64U, UINT64_C(0x101000),
                                UINT64_C(0x101000), &window, &queue));
  window.translated = 0U;
  CHECK(!aiueos_nvme_queue_plan(&cap, 4096U, 32U, UINT64_C(0x101000),
                                UINT64_C(0x102000), &window, &queue));
  window = test_window();

  CHECK(aiueos_nvme_identify_plan(0U, 1U, UINT64_C(0x104000), &window,
                                  &command));
  CHECK(command.opcode == AIUEOS_NVME_ADMIN_IDENTIFY && command.cdw10 == 1U);
  CHECK(!aiueos_nvme_identify_plan(7U, 1U, UINT64_C(0x104000), &window,
                                   &command));
  CHECK(aiueos_nvme_read_plan(1U, UINT64_C(0x100000002), 8U, 512U, 4096U,
                              UINT64_C(0x105e00), &window, &command));
  CHECK(command.prp2 == UINT64_C(0x106000));
  CHECK(command.cdw10 == 2U && command.cdw11 == 1U && command.cdw12 == 7U);
  CHECK(!aiueos_nvme_read_plan(1U, UINT64_MAX, 2U, 512U, 4096U,
                               UINT64_C(0x105000), &window, &command));
  CHECK(!aiueos_nvme_read_plan(1U, 0U, 24U, 512U, 4096U,
                               UINT64_C(0x105000), &window, &command));
}

static void test_xhci(void) {
  struct aiueos_xhci_capability cap;
  struct aiueos_xhci_port_plan port;
  struct aiueos_xhci_ring_plan rings;
  struct aiueos_usb_boot_keyboard_plan keyboard;
  struct aiueos_usb_boot_report previous = {0};
  struct aiueos_usb_boot_report current;
  struct aiueos_usb_key_event events[AIUEOS_USB_KEY_EVENT_CAPACITY];
  struct aiueos_dma_window window = test_window();
  size_t count = 0U;
  uint8_t report[8] = {0x02U, 0U, 0x04U, 0U, 0U, 0U, 0U, 0U};
  uint32_t hcsparams1 = 32U | (4U << 8U) | (8U << 24U);
  uint32_t hccparams1 = 0x20U << 16U;
  uint32_t next = 0U;

  CHECK(aiueos_xhci_pci_admit(0x0cU, 0x03U, 0x30U));
  CHECK(!aiueos_xhci_pci_admit(0x0cU, 0x03U, 0x20U));
  CHECK(aiueos_xhci_capability_parse(0x40U, 0x0110U, hcsparams1,
                                     hccparams1, 0x1003U, 0x201fU, 0x4000U,
                                     &cap));
  CHECK(cap.max_slots == 32U && cap.max_ports == 8U);
  CHECK(cap.doorbell_offset == 0x1000U && cap.runtime_offset == 0x2000U);
  CHECK(!aiueos_xhci_capability_parse(0x10U, 0x0110U, hcsparams1,
                                      hccparams1, 0x1000U, 0x2000U, 0x4000U,
                                      &cap));
  CHECK(!aiueos_xhci_capability_parse(0x40U, 0x0110U, 0U, hccparams1,
                                      0x1000U, 0x2000U, 0x4000U, &cap));
  CHECK(!aiueos_xhci_capability_parse(0x40U, 0x0110U, hcsparams1,
                                      hccparams1, 0x5000U, 0x2000U, 0x4000U,
                                      &cap));
  CHECK(aiueos_xhci_extended_cap_next(0x80U, 2U | (4U << 8U), 0x4000U,
                                      &next));
  CHECK(next == 0x90U);
  CHECK(!aiueos_xhci_extended_cap_next(0xfffffffcU, 2U | (255U << 8U),
                                       UINT64_C(0x100000100), &next));
  CHECK(aiueos_xhci_port_plan(&cap, 8U, 0x1000U, &port));
  CHECK(port.portsc_offset == 0x470U);
  CHECK(!aiueos_xhci_port_plan(&cap, 9U, 0x1000U, &port));

  CHECK(aiueos_xhci_ring_plan(UINT64_C(0x110000), 64U,
                              UINT64_C(0x112000), 64U,
                              UINT64_C(0x114000), &window, &rings));
  window.translated = 0U;
  CHECK(!aiueos_xhci_ring_plan(UINT64_C(0x110000), 64U,
                               UINT64_C(0x112000), 64U,
                               UINT64_C(0x114000), &window, &rings));
  window = test_window();
  CHECK(!aiueos_xhci_ring_plan(UINT64_MAX - 31U, 64U,
                               UINT64_C(0x112000), 64U,
                               UINT64_C(0x114000), &window, &rings));
  CHECK(!aiueos_xhci_ring_plan(UINT64_C(0x110000), 64U,
                               UINT64_C(0x110000), 64U,
                               UINT64_C(0x114000), &window, &rings));
  CHECK(!aiueos_xhci_ring_plan(UINT64_C(0x11ffc0), 16U,
                               UINT64_C(0x112000), 64U,
                               UINT64_C(0x114000), &window, &rings));

  CHECK(aiueos_usb_boot_keyboard_plan(1U, 0U, 0x81U, 8U, 10U, &keyboard));
  CHECK(keyboard.set_protocol_value == 0U);
  CHECK(!aiueos_usb_boot_keyboard_plan(1U, 0U, 0x01U, 8U, 10U, &keyboard));
  CHECK(!aiueos_usb_boot_keyboard_plan(1U, 0U, 0x81U, 7U, 10U, &keyboard));
  CHECK(aiueos_usb_boot_report_parse(report, sizeof(report), &current));
  CHECK(aiueos_usb_boot_report_events(&previous, &current, events,
                                      AIUEOS_USB_KEY_EVENT_CAPACITY, &count));
  CHECK(count == 2U && events[0].usage == 0xe1U && events[0].pressed == 1U &&
        events[1].usage == 0x04U && events[1].pressed == 1U);
  report[1] = 1U;
  CHECK(!aiueos_usb_boot_report_parse(report, sizeof(report), &current));
  report[1] = 0U;
  report[2] = 1U;
  CHECK(!aiueos_usb_boot_report_parse(report, sizeof(report), &current));
  report[2] = 4U;
  report[3] = 4U;
  CHECK(!aiueos_usb_boot_report_parse(report, sizeof(report), &current));
}

static void test_ethernet(void) {
  struct aiueos_ethernet_inventory inventory;
  CHECK(aiueos_ethernet_inventory(0x8086U, 0x15f3U, 3U, 0x02U, 0x00U, 0U,
                                  &inventory));
  CHECK(inventory.supported == 1U &&
        inventory.driver_family == AIUEOS_ETHERNET_DRIVER_INTEL_IGC_FOUNDATION);
  CHECK(strcmp(aiueos_ethernet_driver_name(inventory.driver_family),
               "intel-igc-foundation") == 0);
  CHECK(aiueos_ethernet_inventory(0x10ecU, 0x8125U, 5U, 0x02U, 0x00U, 0U,
                                  &inventory));
  CHECK(inventory.supported == 1U &&
        inventory.driver_family == AIUEOS_ETHERNET_DRIVER_REALTEK_2P5G_FOUNDATION);
  CHECK(aiueos_ethernet_inventory(0x8086U, 0xffffU, 0U, 0x02U, 0x00U, 0U,
                                  &inventory));
  CHECK(inventory.supported == 0U &&
        inventory.driver_family == AIUEOS_ETHERNET_DRIVER_NONE);
  CHECK(!aiueos_ethernet_inventory(0x8086U, 0x15f3U, 0U, 0x01U, 0x08U, 2U,
                                   &inventory));
  CHECK(!aiueos_ethernet_inventory(0xffffU, 0xffffU, 0U, 0x02U, 0x00U, 0U,
                                   &inventory));
}

int main(void) {
  test_dma();
  test_nvme();
  test_xhci();
  test_ethernet();
  if (failures != 0U) {
    fprintf(stderr, "native-driver tests: %u failure(s)\n", failures);
    return 1;
  }
  printf("native-driver tests: PASS (%u checks)\n", checks);
  return 0;
}
