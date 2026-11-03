/* Shared by old.c, new.c and driver.c (JUN-598): the ring and event layout of kernel/pci.c. */
#include <stdint.h>
struct virtq_avail { uint16_t flags, index, ring[4], used_event; } __attribute__((packed));
struct virtq_used_element { uint32_t id, length; } __attribute__((packed));
struct virtq_used { uint16_t flags, index; struct virtq_used_element ring[4]; uint16_t avail_event; } __attribute__((packed));
struct virtio_input_event { uint16_t type, code; uint32_t value; } __attribute__((packed));
extern struct virtq_avail *kbd_avail;
extern struct virtq_used *kbd_used;
extern volatile uint16_t *kbd_doorbell;
extern struct virtio_input_event *kbd_event;
