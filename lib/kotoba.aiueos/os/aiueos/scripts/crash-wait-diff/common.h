/* Shared by old.c, new.c and driver.c (JUN-598): the ring layout and constants of kernel/pci.c, and the fields of
   struct aiueos_blk_backend that crash_sector_io_polled's wait uses. */
#include <stdint.h>
#define VIRTIO_BLK_T_IN 0
#define VIRTIO_BLK_S_OK 0
struct virtq_used_element { uint32_t id, length; } __attribute__((packed));
struct virtq_used { uint16_t flags, index; struct virtq_used_element ring[4]; uint16_t avail_event; } __attribute__((packed));
struct crash_backend { struct virtq_used *used; uint8_t *status; uint16_t submitted; };
extern volatile uint64_t aiueos_virtio_blk_irq_count;
