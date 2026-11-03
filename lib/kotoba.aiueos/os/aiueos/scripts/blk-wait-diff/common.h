/* Shared by old.c, new.c and driver.c (JUN-598): the ring layout and constants of kernel/pci.c. */
#include <stdint.h>
#define VIRTIO_BLK_T_IN 0
#define VIRTIO_BLK_S_OK 0
struct virtq_used_element { uint32_t id, length; } __attribute__((packed));
struct virtq_used { uint16_t flags, index; struct virtq_used_element ring[4]; uint16_t avail_event; } __attribute__((packed));
extern volatile uint64_t aiueos_virtio_blk_irq_count;
extern int blk_msix_active;
static inline void aiueos_storage_unwrap_sector(uint8_t *sector, uint64_t disk_sector) { (void)sector; (void)disk_sector; }
#define DECLARE_STATS uint32_t blk_slowest_iters; uint16_t blk_slow_used, blk_slow_target, blk_wait_used, blk_wait_target; \
  uint64_t blk_wait_irq; int blk_wait_overshot;
