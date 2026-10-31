/* allocator-plan built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object. Random
   256-record, 16-byte allocation tables (page words zero, small, near 2^32 or random; active bytes 0, 1 or random; one
   free record at a random place or none), called with the shipped geometry (4096, 256, 16) or one argument disturbed,
   claim requests (0) and release requests naming every slot with its own page, another page or page 0, and a null
   table; answers and traps compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_allocator_plan(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_allocator_plan_native(int64_t, int64_t, int64_t, int64_t, int64_t);
static uint8_t tb[4096 + 64] __attribute__((aligned(16)));
static void put64(int o, uint64_t v) { for (int i = 0; i < 8; i++) tb[o + i] = (uint8_t)(v >> (8 * i)); }
static uint64_t get64(int o) { uint64_t v = 0; for (int i = 7; i >= 0; i--) v = v << 8 | tb[o + i]; return v; }
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)tb;
  void *o = (void *)kotoba_aiueos_allocator_plan, *n = (void *)kotoba_aiueos_allocator_plan_native;
  for (unsigned k = 0; k < 12000; k++) {
    for (int i = 0; i < 4096 + 64; i++) tb[i] = (uint8_t)rnd();
    unsigned full = (unsigned)(rnd() % 4);
    for (int r = 0; r < 256; r++) {
      unsigned m = (unsigned)(rnd() % 8);
      put64(r * 16, m == 0 ? 0 : m < 4 ? 0x100000ull + 0x1000ull * (uint64_t)r : m == 4 ? 0xfffff000ull : (uint64_t)rnd() << 12);
      tb[r * 16 + 8] = full ? 1 : rnd() % 4 ? (uint8_t)(rnd() % 2) : (uint8_t)rnd();
      if (full && get64(r * 16) == 0) put64(r * 16, 0x1000);
    }
    if (full == 1) { int r = (int)(rnd() % 256); put64(r * 16, 0); tb[r * 16 + 8] = (uint8_t)(rnd() % 2); }
    int64_t len = 4096, cnt = 256, str = 16, req = 0;
    unsigned q = (unsigned)(rnd() % 3);
    if (q) {
      int64_t slot = (int64_t)(rnd() % 260), page;
      int64_t own = slot >= 1 && slot <= 256 ? (int64_t)get64((int)(slot - 1) * 16) : 0;
      unsigned p = (unsigned)(rnd() % 4);
      page = p < 2 ? own : p == 2 ? own + 0x1000 : 0;
      if (q == 2 && slot >= 1 && slot <= 256) tb[(slot - 1) * 16 + 8] = 1;
      req = (int64_t)(((uint64_t)(uint32_t)page) << 32) | slot;
      if (rnd() % 8 == 0) req = (int64_t)rnd();
    }
    unsigned d = (unsigned)(rnd() % 8);
    if (d == 1) len = rnd() % 2 ? 4095 + (int64_t)(rnd() % 3) : (int64_t)(rnd() % 20000);
    if (d == 2) cnt = 255 + (int64_t)(rnd() % 3);
    if (d == 3) str = 15 + (int64_t)(rnd() % 3);
    same(o, n, k % 211 == 0 ? 0 : b, len, cnt, str, req);
  }
  report();
}
