#include "nvme.h"

#define NVME_SQ_ENTRY_BYTES 64U
#define NVME_CQ_ENTRY_BYTES 16U
#define NVME_IDENTIFY_BYTES 4096U
#define NVME_MIN_MMIO_BYTES 0x1000U

static int checked_size_multiply(uint32_t a, uint32_t b, size_t *out) {
  if (out == NULL || (a != 0U && (size_t)b > SIZE_MAX / (size_t)a)) {
    return 0;
  }
  *out = (size_t)a * (size_t)b;
  return 1;
}

int aiueos_nvme_pci_admit(uint8_t class_code, uint8_t subclass,
                          uint8_t programming_interface) {
  return class_code == AIUEOS_NVME_CLASS_MASS_STORAGE &&
         subclass == AIUEOS_NVME_SUBCLASS_NVM &&
         programming_interface == AIUEOS_NVME_PROGIF_NVM_EXPRESS;
}

int aiueos_nvme_bar0_admit(uint32_t bar0, uint32_t bar1,
                           uint64_t mapped_length, uint64_t *base_out) {
  uint32_t type;
  uint64_t base;

  if (base_out == NULL || (bar0 & 1U) != 0U || mapped_length < NVME_MIN_MMIO_BYTES) {
    return 0;
  }
  type = (bar0 >> 1U) & 3U;
  if (type == 0U) {
    base = (uint64_t)(bar0 & UINT32_C(0xfffffff0));
  } else if (type == 2U) {
    base = ((uint64_t)bar1 << 32U) | (uint64_t)(bar0 & UINT32_C(0xfffffff0));
  } else {
    return 0;
  }
  if (base == 0U || (base & UINT64_C(0xfff)) != 0U ||
      mapped_length - 1U > UINT64_MAX - base) {
    return 0;
  }
  *base_out = base;
  return 1;
}

int aiueos_nvme_capability_parse(uint64_t raw,
                                 struct aiueos_nvme_capability *out) {
  uint32_t min_shift;
  uint32_t max_shift;
  uint32_t stride_shift;

  if (out == NULL || (raw & (UINT64_C(1) << 37U)) == 0U) {
    return 0;
  }
  min_shift = (uint32_t)((raw >> 48U) & 0xfU);
  max_shift = (uint32_t)((raw >> 52U) & 0xfU);
  stride_shift = (uint32_t)((raw >> 32U) & 0xfU);
  if (min_shift > max_shift || max_shift > 12U || stride_shift > 6U) {
    return 0;
  }
  out->max_queue_entries = (uint32_t)(raw & UINT64_C(0xffff)) + 1U;
  out->contiguous_queues_required = (uint8_t)((raw >> 16U) & 1U);
  out->timeout_ms = (uint32_t)((raw >> 24U) & 0xffU) * 500U;
  out->doorbell_stride = UINT32_C(4) << stride_shift;
  out->min_page_size = UINT32_C(4096) << min_shift;
  out->max_page_size = UINT32_C(4096) << max_shift;
  return out->max_queue_entries >= 2U;
}

int aiueos_nvme_queue_plan(const struct aiueos_nvme_capability *cap,
                           uint32_t page_size, uint32_t requested_entries,
                           uint64_t submission_dma, uint64_t completion_dma,
                           const struct aiueos_dma_window *window,
                           struct aiueos_nvme_queue_plan *out) {
  size_t sq_bytes;
  size_t cq_bytes;

  if (cap == NULL || out == NULL || requested_entries < 2U ||
      requested_entries > cap->max_queue_entries || requested_entries > UINT16_MAX ||
      page_size < cap->min_page_size || page_size > cap->max_page_size ||
      (page_size & (page_size - 1U)) != 0U ||
      !checked_size_multiply(requested_entries, NVME_SQ_ENTRY_BYTES, &sq_bytes) ||
      !checked_size_multiply(requested_entries, NVME_CQ_ENTRY_BYTES, &cq_bytes) ||
      !aiueos_dma_range_admit(window, submission_dma, sq_bytes, page_size) ||
      !aiueos_dma_range_admit(window, completion_dma, cq_bytes, page_size) ||
      !aiueos_dma_ranges_disjoint(submission_dma, sq_bytes, completion_dma,
                                  cq_bytes)) {
    return 0;
  }
  out->entries = (uint16_t)requested_entries;
  out->submission_bytes = sq_bytes;
  out->completion_bytes = cq_bytes;
  out->submission_dma = submission_dma;
  out->completion_dma = completion_dma;
  return 1;
}

int aiueos_nvme_identify_plan(uint32_t namespace_id, uint8_t controller,
                              uint64_t data_dma,
                              const struct aiueos_dma_window *window,
                              struct aiueos_nvme_command_plan *out) {
  if (out == NULL || controller > 1U ||
      (controller != 0U && namespace_id != 0U) ||
      (controller == 0U && namespace_id == 0U) ||
      !aiueos_dma_range_admit(window, data_dma, NVME_IDENTIFY_BYTES,
                              NVME_IDENTIFY_BYTES)) {
    return 0;
  }
  *out = (struct aiueos_nvme_command_plan){0};
  out->opcode = AIUEOS_NVME_ADMIN_IDENTIFY;
  out->namespace_id = namespace_id;
  out->prp1 = data_dma;
  out->cdw10 = controller != 0U ? 1U : 0U;
  out->transfer_bytes = NVME_IDENTIFY_BYTES;
  return 1;
}

int aiueos_nvme_read_plan(uint32_t namespace_id, uint64_t first_lba,
                          uint32_t block_count, uint32_t block_size,
                          uint32_t page_size, uint64_t data_dma,
                          const struct aiueos_dma_window *window,
                          struct aiueos_nvme_command_plan *out) {
  size_t bytes;
  uint64_t end_lba;
  uint64_t first_page_remaining;

  if (out == NULL || namespace_id == 0U || block_count == 0U ||
      block_count > 65536U || block_size < 512U ||
      (block_size & (block_size - 1U)) != 0U || page_size < 4096U ||
      (page_size & (page_size - 1U)) != 0U ||
      !checked_size_multiply(block_count, block_size, &bytes) ||
      (uint64_t)block_count - 1U > UINT64_MAX - first_lba ||
      !aiueos_dma_range_admit(window, data_dma, bytes, block_size)) {
    return 0;
  }
  end_lba = first_lba + (uint64_t)block_count - 1U;
  (void)end_lba;
  first_page_remaining = page_size - (data_dma & ((uint64_t)page_size - 1U));
  if ((uint64_t)bytes > first_page_remaining + (uint64_t)page_size) {
    return 0; /* A PRP list is deliberately outside this bounded foundation. */
  }
  *out = (struct aiueos_nvme_command_plan){0};
  out->opcode = AIUEOS_NVME_IO_READ;
  out->namespace_id = namespace_id;
  out->prp1 = data_dma;
  if ((uint64_t)bytes > first_page_remaining) {
    out->prp2 = data_dma + first_page_remaining;
  }
  out->cdw10 = (uint32_t)first_lba;
  out->cdw11 = (uint32_t)(first_lba >> 32U);
  out->cdw12 = block_count - 1U;
  out->transfer_bytes = bytes;
  return 1;
}
