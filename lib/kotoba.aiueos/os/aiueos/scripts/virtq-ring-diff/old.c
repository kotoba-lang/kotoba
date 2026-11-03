/* The ring writes and reads the virtio drivers made in C before JUN-598 moved them to kotoba/virtq-ring.o: virtio_rng's
   first request and rng_refill's, verbatim from kernel/pci.c (main 009bff71) with their pointers as parameters, and
   the same struct-field writes / reads for any slot, position and index (old_post, old_used_index, old_used_elem),
   over the structs as pci.c declares them. */
#include <stdint.h>
#define VIRTQ_DESC_F_WRITE 2
struct virtq_desc { uint64_t address; uint32_t length; uint16_t flags, next; } __attribute__((packed));
struct virtq_avail { uint16_t flags, index, ring[4], used_event; } __attribute__((packed));
struct virtq_used_element { uint32_t id, length; } __attribute__((packed));
struct virtq_used { uint16_t flags, index; struct virtq_used_element ring[4]; uint16_t avail_event; } __attribute__((packed));
void old_rng_first(struct virtq_desc *desc, struct virtq_avail *avail, uint8_t *random) {
  desc[0].address = (uint64_t)(uintptr_t)random; desc[0].length = 32;
  desc[0].flags = VIRTQ_DESC_F_WRITE; desc[0].next = 0;
  avail->ring[0] = 0; __asm__ volatile("" ::: "memory"); avail->index = 1;
}
void old_rng_refill_post(struct virtq_desc *desc, struct virtq_avail *avail, uint8_t *page, uint16_t *posted) {
  desc[0].address = (uint64_t)(uintptr_t)page;
  desc[0].length = 32;
  desc[0].flags = VIRTQ_DESC_F_WRITE;
  desc[0].next = 0;
  avail->ring[0] = 0;
  __asm__ volatile("" ::: "memory");
  (*posted)++;
  avail->index = *posted;
}
void old_post(struct virtq_desc *desc, struct virtq_avail *avail, uint16_t slot, uint64_t address, uint32_t length,
              uint16_t flags, uint16_t next, uint16_t position, uint16_t index) {
  desc[slot].address = address; desc[slot].length = length; desc[slot].flags = flags; desc[slot].next = next;
  ((volatile uint16_t *)avail)[2 + position] = slot; __asm__ volatile("" ::: "memory"); avail->index = index;
}
uint16_t old_used_index(const struct virtq_used *used) { return used->index; }
uint64_t old_used_elem(const struct virtq_used *used, unsigned slot) {
  const struct virtq_used_element *e = (const struct virtq_used_element *)((const uint8_t *)used + 4) + slot;
  return (uint64_t)e->id << 32 | e->length;
}
