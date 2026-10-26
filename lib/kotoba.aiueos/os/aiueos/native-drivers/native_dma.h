#ifndef AIUEOS_NATIVE_DMA_H
#define AIUEOS_NATIVE_DMA_H

#include <stddef.h>
#include <stdint.h>

struct aiueos_dma_window {
  uint64_t first;
  uint64_t last;
  uint8_t translated;
};

static inline int aiueos_dma_range_admit(const struct aiueos_dma_window *window,
                                         uint64_t address, size_t length,
                                         uint64_t alignment) {
  uint64_t end;

  if (window == NULL || window->translated == 0U || length == 0U ||
      alignment == 0U || (alignment & (alignment - 1U)) != 0U ||
      (address & (alignment - 1U)) != 0U) {
    return 0;
  }
  if ((uint64_t)length - 1U > UINT64_MAX - address) {
    return 0;
  }
  end = address + (uint64_t)length - 1U;
  return address >= window->first && end <= window->last;
}

static inline int aiueos_dma_ranges_disjoint(uint64_t first_address,
                                             size_t first_length,
                                             uint64_t second_address,
                                             size_t second_length) {
  uint64_t first_end;
  uint64_t second_end;
  if (first_length == 0U || second_length == 0U ||
      (uint64_t)first_length - 1U > UINT64_MAX - first_address ||
      (uint64_t)second_length - 1U > UINT64_MAX - second_address) {
    return 0;
  }
  first_end = first_address + (uint64_t)first_length - 1U;
  second_end = second_address + (uint64_t)second_length - 1U;
  return first_end < second_address || second_end < first_address;
}

#endif
