#ifndef AIUEOS_NATIVE_NVME_H
#define AIUEOS_NATIVE_NVME_H

#include <stddef.h>
#include <stdint.h>

#include "native_dma.h"

#define AIUEOS_NVME_CLASS_MASS_STORAGE 0x01U
#define AIUEOS_NVME_SUBCLASS_NVM 0x08U
#define AIUEOS_NVME_PROGIF_NVM_EXPRESS 0x02U
#define AIUEOS_NVME_ADMIN_IDENTIFY 0x06U
#define AIUEOS_NVME_IO_READ 0x02U

struct aiueos_nvme_capability {
  uint32_t max_queue_entries;
  uint32_t doorbell_stride;
  uint32_t timeout_ms;
  uint32_t min_page_size;
  uint32_t max_page_size;
  uint8_t contiguous_queues_required;
};

struct aiueos_nvme_queue_plan {
  uint16_t entries;
  size_t submission_bytes;
  size_t completion_bytes;
  uint64_t submission_dma;
  uint64_t completion_dma;
};

struct aiueos_nvme_command_plan {
  uint8_t opcode;
  uint32_t namespace_id;
  uint64_t prp1;
  uint64_t prp2;
  uint32_t cdw10;
  uint32_t cdw11;
  uint32_t cdw12;
  size_t transfer_bytes;
};

int aiueos_nvme_pci_admit(uint8_t class_code, uint8_t subclass,
                          uint8_t programming_interface);
int aiueos_nvme_bar0_admit(uint32_t bar0, uint32_t bar1,
                           uint64_t mapped_length, uint64_t *base_out);
int aiueos_nvme_capability_parse(uint64_t raw,
                                 struct aiueos_nvme_capability *out);
int aiueos_nvme_queue_plan(const struct aiueos_nvme_capability *cap,
                           uint32_t page_size, uint32_t requested_entries,
                           uint64_t submission_dma, uint64_t completion_dma,
                           const struct aiueos_dma_window *window,
                           struct aiueos_nvme_queue_plan *out);
int aiueos_nvme_identify_plan(uint32_t namespace_id, uint8_t controller,
                              uint64_t data_dma,
                              const struct aiueos_dma_window *window,
                              struct aiueos_nvme_command_plan *out);
int aiueos_nvme_read_plan(uint32_t namespace_id, uint64_t first_lba,
                          uint32_t block_count, uint32_t block_size,
                          uint32_t page_size, uint64_t data_dma,
                          const struct aiueos_dma_window *window,
                          struct aiueos_nvme_command_plan *out);

#endif
