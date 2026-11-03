/* kbd_recycle before JUN-598 moved its reap step to kotoba/kbd-reap.o: verbatim from kernel/pci.c (main 3f9acccd) as
   old_recycle, with its position and event counter renamed old_* so new_recycle's can be compared with them. */
#include "common.h"
#define kbd_seen old_seen
#define aiueos_input_ring_events old_events
uint16_t kbd_seen; uint32_t aiueos_input_ring_events;
uint32_t old_recycle(int want_press) {
  uint32_t press = 0;
  __asm__ volatile("" ::: "memory");
  uint16_t n = kbd_used->index;
  while (kbd_seen != n) {
    uint32_t id = kbd_used->ring[kbd_seen % 4].id;
    kbd_seen++;
    if (id > 3) continue;
    struct virtio_input_event *ev = kbd_event + id;
    /* Every used entry the reap path touches is counted here, and only here
       (JUN-34, measured 2026-10-23: the boot probe used to count its own read
       of ring slot 0 and the poll path then re-read the same entry, so the
       ring evidence double-counted and lagged what the desktop actually saw). */
    aiueos_input_ring_events++;
    if (want_press == 1 && !press && ev->type == 1 && ev->value == 1 && ev->code)
      press = ev->code;
    if (want_press == 2 && !press && ev->type == 1 && ev->value <= 2 && ev->code)
      press = (uint32_t)ev->code * 4U + ev->value;
    kbd_avail->ring[kbd_avail->index % 4] = (uint16_t)id;
    __asm__ volatile("" ::: "memory");
    kbd_avail->index++;
    *kbd_doorbell = 0;
    if (press) break;
  }
  return press;
}
