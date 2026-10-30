#include <stdint.h>
struct virtq_desc; struct virtq_avail; struct virtq_used;
void old_rng_first(struct virtq_desc *, struct virtq_avail *, uint8_t *);
void old_rng_refill_post(struct virtq_desc *, struct virtq_avail *, uint8_t *, uint16_t *);
void old_post(struct virtq_desc *, struct virtq_avail *, uint16_t, uint64_t, uint32_t, uint16_t, uint16_t, uint16_t, uint16_t);
uint16_t old_used_index(const struct virtq_used *); uint64_t old_used_elem(const struct virtq_used *, unsigned);
int64_t kotoba_aiueos_virtq_post(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
int64_t kotoba_aiueos_virtq_used_index(uint64_t, uint64_t); int64_t kotoba_aiueos_virtq_used_elem(uint64_t, uint64_t, uint64_t);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 1353;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 7; }
static uint8_t d1[4096] __attribute__((aligned(4096))), a1[4096] __attribute__((aligned(4096)));
static uint8_t d2[4096] __attribute__((aligned(4096))), a2[4096] __attribute__((aligned(4096))), u[4096] __attribute__((aligned(4096)));
static unsigned n_cases, n_bad;
static void fill(void) { for (int i = 0; i < 4096; i++) { d1[i] = d2[i] = (uint8_t)rnd(); a1[i] = a2[i] = (uint8_t)rnd(); } }
static int same(void) { for (int i = 0; i < 4096; i++) if (d1[i] != d2[i] || a1[i] != a2[i]) return 0; return 1; }
static void check(int ok, unsigned tag) { n_cases++; if (!ok && n_bad++ < 8) { puts_("VIRTQ-DIFF "); hex(tag, 6); putc_('\n'); } }
static int post(uint8_t *d, uint8_t *a, uint64_t slot, uint64_t addr, uint64_t len, uint64_t flags, uint64_t next, uint64_t pos, uint64_t index) {
  uint64_t rec[6] = {slot, addr, len, flags, next, pos | index << 16};
  return (int)kotoba_aiueos_virtq_post((uint64_t)(uintptr_t)d, 4096, (uint64_t)(uintptr_t)a, 4096, (uint64_t)(uintptr_t)rec, sizeof rec);
}
void test_main(void) {
  puts_("VIRTQRINGDIFF\n");
  for (unsigned k = 0; k < 4000; k++) {
    /* virtio_rng's first request */
    fill(); uint8_t *page = (uint8_t *)(uintptr_t)(rnd() << 12);
    old_rng_first((void *)d1, (void *)a1, page);
    int r = post(d2, a2, 0, (uint64_t)(uintptr_t)page, 32, 2, 0, 0, 1);
    check(r == 1 && same(), k * 8);
    /* rng_refill's, with posted wrapping through 0xffff */
    fill(); uint16_t posted1 = (uint16_t)(k % 10 == 0 ? 0xffff : rnd()), posted2 = posted1;
    old_rng_refill_post((void *)d1, (void *)a1, page, &posted1);
    posted2++; r = post(d2, a2, 0, (uint64_t)(uintptr_t)page, 32, 2, 0, 0, posted2);
    check(r == 1 && same() && posted1 == posted2, k * 8 + 1);
    /* any slot, position, length, flags, next, index */
    for (unsigned j = 0; j < 8; j++) {
      fill();
      uint16_t slot = (uint16_t)(rnd() % 256), pos = (uint16_t)(rnd() % 2046), index = (uint16_t)rnd(), flags = (uint16_t)rnd(), next = (uint16_t)rnd();
      uint64_t addr = rnd() << 3 ^ rnd(); uint32_t len = (uint32_t)rnd();
      old_post((void *)d1, (void *)a1, slot, addr, len, flags, next, pos, index);
      r = post(d2, a2, slot, addr, len, flags, next, pos, index);
      check(r == 1 && same(), k * 8 + 2);
    }
    /* refusals write nothing */
    fill(); r = post(d2, a2, 256 + rnd() % 100, 1, 1, 1, 1, 0, 1); check(r == 0 && same(), k * 8 + 3);
    fill(); r = post(d2, a2, 0, 1, 1, 1, 1, 2046 + rnd() % 100, 1); check(r == 0 && same(), k * 8 + 4);
    /* used ring reads */
    for (int i = 0; i < 4096; i++) u[i] = (uint8_t)rnd();
    check(old_used_index((void *)u) == (uint16_t)kotoba_aiueos_virtq_used_index((uint64_t)(uintptr_t)u, 4096), k * 8 + 5);
    for (unsigned j = 0; j < 8; j++) { unsigned s = (unsigned)(rnd() % 511);
      check(old_used_elem((void *)u, s) == (uint64_t)kotoba_aiueos_virtq_used_elem((uint64_t)(uintptr_t)u, 4096, s), k * 8 + 6); }
    check(kotoba_aiueos_virtq_used_elem((uint64_t)(uintptr_t)u, 4096, 511 + rnd() % 50) == -1, k * 8 + 7);
  }
  puts_("CASES "); hex(n_cases, 5); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
