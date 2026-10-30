/* kbd_recycle's reap (JUN-598): old_recycle (verbatim) and new_recycle (over kotoba/kbd-reap.o) run from the same
   rings -- the used index up to 6 entries ahead of the position (or level with it), positions wrapping at 2^16, used
   ids 0..7 (past 3 names no buffer), events of type 0..2 with code 0 or not and values 0..4 or large, for want 0, 1
   and 2 -- and must answer the same key and leave the same position, event counter, available ring and doorbell
   count. 100000 cases. */
#include "common.h"
uint32_t old_recycle(int); uint32_t new_recycle(int);
extern uint16_t old_seen, new_seen; extern uint32_t old_events, new_events;
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint8_t used_page[4096] __attribute__((aligned(4096))), avail_page[4096] __attribute__((aligned(4096))),
  event_page[4096] __attribute__((aligned(4096)));
static uint8_t used0[4096], avail0[4096], event0[4096], avail1[16];
struct virtq_avail *kbd_avail = (struct virtq_avail *)avail_page;
struct virtq_used *kbd_used = (struct virtq_used *)used_page;
struct virtio_input_event *kbd_event = (struct virtio_input_event *)event_page;
static volatile uint16_t bell; volatile uint16_t *kbd_doorbell = &bell;
static uint64_t seed = 2020;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 21; }
static void restore(void) { for (int i = 0; i < 4096; i++) { used_page[i] = used0[i]; avail_page[i] = avail0[i]; event_page[i] = event0[i]; } }
void test_main(void) {
  puts_("KBDREAPDIFF\n");
  unsigned n_cases = 0, n_keys = 0, n_bad = 0;
  for (unsigned k = 0; k < 100000; k++) {
    for (int i = 0; i < 64; i++) { used0[i] = (uint8_t)rnd(); avail0[i] = (uint8_t)rnd(); event0[i] = (uint8_t)rnd(); }
    uint16_t seen = (uint16_t)(k % 17 == 0 ? 0xfffe + rnd() % 3 : rnd());
    struct virtq_used *u = (struct virtq_used *)used0;
    u->index = (uint16_t)(seen + rnd() % 7);
    for (int i = 0; i < 4; i++) u->ring[i].id = (uint32_t)(rnd() % 6 == 0 ? 4 + rnd() % 4 : rnd() % 4);
    struct virtio_input_event *e = (struct virtio_input_event *)event0;
    for (int i = 0; i < 4; i++) {
      e[i].type = (uint16_t)(rnd() % 3); e[i].code = (uint16_t)(rnd() % 4 == 0 ? 0 : rnd());
      e[i].value = (uint32_t)(rnd() % 5 == 0 ? rnd() : rnd() % 5);
    }
    int want = (int)(k % 3);
    uint32_t events = (uint32_t)rnd();
    restore(); old_seen = seen; old_events = events; bell = 1; unsigned bells_old = 0;
    uint32_t r1 = old_recycle(want);
    for (int i = 0; i < 16; i++) avail1[i] = avail_page[i];
    int used_same1 = 1; for (int i = 0; i < 4096; i++) if (used_page[i] != used0[i] || event_page[i] != event0[i]) used_same1 = 0;
    bells_old = bell == 0;
    restore(); new_seen = seen; new_events = events; bell = 1;
    uint32_t r2 = new_recycle(want);
    int same = r1 == r2 && old_seen == new_seen && old_events == new_events && (bell == 0) == bells_old && used_same1;
    for (int i = 0; i < 4096; i++) if (avail_page[i] != (i < 16 ? avail1[i] : avail0[i]) || used_page[i] != used0[i] ||
                                        event_page[i] != event0[i]) same = 0;
    n_cases++; if (r1) n_keys++;
    if (!same && n_bad++ < 8) { puts_("REAP-DIFF "); hex(k, 5); hex(r1, 8); hex(r2, 8); hex(old_seen, 4); hex(new_seen, 4); putc_('\n'); }
  }
  puts_("CASES "); hex(n_cases, 5); puts_("KEYS "); hex(n_keys, 5); puts_("DIFFS "); hex(n_bad, 5); putc_('\n'); puts_("DONE\n");
}
