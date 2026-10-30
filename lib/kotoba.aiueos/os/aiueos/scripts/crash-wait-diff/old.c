/* crash_sector_io_polled's completion wait before JUN-598 moved it to kotoba/blk-wait.o: verbatim from kernel/pci.c
   (main 6d54950d) with its 10^8 budget made a parameter and the request already posted, as old_wait. */
#include "common.h"
int old_wait(struct crash_backend *b, uint32_t type, uint32_t budget_limit) {
  uint16_t old = b->submitted, target = old + 1;
  for (uint32_t budget = 0; budget < budget_limit; budget++) {
    __asm__ volatile("" ::: "memory");
    if (b->used->index == target) {
      struct virtq_used_element *completion = &b->used->ring[old & 3];
      uint32_t expected = type == VIRTIO_BLK_T_IN ? 513 : 1;
      if (completion->id != 0 || completion->length != expected ||
          *b->status != VIRTIO_BLK_S_OK) return 0;
      b->submitted = target;
      return 1;
    }
    __asm__ volatile("pause");
  }
  return 0;
}
