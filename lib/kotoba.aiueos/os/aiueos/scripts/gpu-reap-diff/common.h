/* Shared by old.c, new.c and driver.c (JUN-598): kernel/pci.c's ring and virtio-gpu layouts, and the harness's
   stand-ins for what gpu_ctrl calls -- gpu_zero zeroes the response and then lets the scripted device write its
   header (the device's write after the doorbell, which a static ring cannot make later), and the serial marker
   folds its text into a hash. */
#include <stdint.h>
#define VIRTQ_DESC_F_NEXT 1
#define VIRTQ_DESC_F_WRITE 2
struct virtq_desc { uint64_t address; uint32_t length; uint16_t flags, next; } __attribute__((packed));
struct virtq_avail { uint16_t flags, index, ring[4], used_event; } __attribute__((packed));
struct virtq_used_element { uint32_t id, length; } __attribute__((packed));
struct virtq_used { uint16_t flags, index; struct virtq_used_element ring[4]; uint16_t avail_event; } __attribute__((packed));
struct virtio_gpu_ctrl_header {
  uint32_t type, flags; uint64_t fence_id; uint32_t context_id; uint8_t ring_index, padding[3];
} __attribute__((packed));
struct virtio_gpu_event { struct virtio_gpu_ctrl_header header; uint32_t events; };
extern uint32_t budget_limit;
void device_respond(void *p, uint32_t n);
static void gpu_zero(void *p, uint32_t n) { uint8_t *b = p; for (uint32_t i = 0; i < n; i++) b[i] = 0; device_respond(p, n); }
