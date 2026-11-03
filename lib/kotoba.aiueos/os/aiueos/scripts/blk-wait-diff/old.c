/* virtio_blk_sector_io_ex's completion wait before JUN-598 moved it to kotoba/blk-wait.o: verbatim from kernel/pci.c
   (main 91113fc1) with its 10^8 budget made a parameter and the request already posted, as old_wait; its statistics
   globals renamed old_* so new_wait's can be compared with them. raw is set, so no sector is unwrapped. */
#include "common.h"
#define blk_slowest_iters old_slowest_iters
#define blk_slow_used old_slow_used
#define blk_slow_target old_slow_target
#define blk_wait_used old_wait_used
#define blk_wait_target old_wait_target
#define blk_wait_irq old_wait_irq
#define blk_wait_overshot old_wait_overshot
DECLARE_STATS
int old_wait(struct virtq_used *used, uint8_t *status, uint16_t *submitted, uint32_t type, uint32_t budget_limit) {
  uint16_t old = *submitted, target = old + 1; int raw = 1; uint8_t *sector = 0; uint64_t disk_sector = 0;
  for (uint32_t budget = 0; budget < budget_limit; budget++) {
    __asm__ volatile("" ::: "memory");
    if ((!blk_msix_active || aiueos_virtio_blk_irq_count >= target) && used->index == target) {
      struct virtq_used_element *completion = &used->ring[old & 3];
      uint32_t expected = type == VIRTIO_BLK_T_IN ? 513 : 1;
      if (completion->id != 0 || completion->length != expected || *status != VIRTIO_BLK_S_OK)
        return 0;
      if (budget >= blk_slowest_iters) {
        blk_slowest_iters = budget; blk_slow_used = used->index;
        blk_slow_target = target;
      }
      *submitted = target;
      if (!raw && type == VIRTIO_BLK_T_IN)
        aiueos_storage_unwrap_sector(sector, disk_sector);
      return 1;
    }
    /* Futile, not slow: the used index has passed the value this wait is
       looking for, so no future completion can make the equality true. Fail
       now with the numbers instead of spinning until the harness times out. */
    if (used->index != target &&
        (uint16_t)(used->index - target) < 0x8000) {
      blk_wait_used = used->index; blk_wait_target = target;
      blk_wait_irq = aiueos_virtio_blk_irq_count; blk_wait_overshot = 1;
      return 0;
    }
    if (blk_msix_active) __asm__ volatile("sti; hlt; cli" ::: "memory");
    else __asm__ volatile("pause");
  }
  return 0;
}
