/* scheduler-dispatch-plan built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object.
   Random 9-slot, 40-byte task tables (the active byte at 38 and exit-requested byte at 39 from {0, 1, random}, every
   other byte random), called with the shipped geometry (360, 9, 40) or one argument disturbed, a state word whose
   current slot is 0 .. 15 with the user-mode (16) and context-reset (32) bits and random high bits, and a null base;
   answers and traps compared. */
#include "diff.h"
static uint8_t tb[1024] __attribute__((aligned(16)));
__attribute__((unused)) static void put16(int o, unsigned v) { tb[o] = (uint8_t)v; tb[o + 1] = (uint8_t)(v >> 8); }
__attribute__((unused)) static unsigned pick16(void) { unsigned k = (unsigned)(rnd() % 6); return k == 0 ? 0 : k == 1 ? 1 : k == 2 ? 65534 : k == 3 ? 65535 : k == 4 ? 2 + (unsigned)(rnd() % 4) : (unsigned)(rnd() & 0xffff); }
__attribute__((unused)) static uint8_t pick_flag(void) { unsigned k = (unsigned)(rnd() % 8); return k < 3 ? 0 : k < 6 ? 1 : (uint8_t)rnd(); }
__attribute__((unused)) static int64_t pick_len(int64_t good) { unsigned k = (unsigned)(rnd() % 10); return k < 7 ? good : k == 7 ? good + (int64_t)(rnd() % 3) - 1 : k == 8 ? (int64_t)(rnd() % 700) : (int64_t)rnd(); }
__attribute__((unused)) static int64_t pick_dom(void) { unsigned k = (unsigned)(rnd() % 8); return k < 5 ? 2 + (int64_t)(rnd() % 4) : k == 5 ? (int64_t)(rnd() % 3) : k == 6 ? 65535 + (int64_t)(rnd() % 3) - 1 : (int64_t)rnd(); }
extern int64_t kotoba_aiueos_scheduler_dispatch_plan(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_scheduler_dispatch_plan_native(int64_t, int64_t, int64_t, int64_t, int64_t);
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)tb;
  void *o = (void *)kotoba_aiueos_scheduler_dispatch_plan, *n = (void *)kotoba_aiueos_scheduler_dispatch_plan_native;
  for (unsigned k = 0; k < 40000; k++) {
    for (int i = 0; i < 1024; i++) tb[i] = (uint8_t)rnd();
    unsigned sparse = (unsigned)(rnd() % 3);
    for (int s = 0; s < 9; s++) {
      tb[s * 40 + 38] = sparse == 0 ? (rnd() % 5 == 0) : pick_flag(); tb[s * 40 + 39] = pick_flag();
    }
    int64_t len = 360, cnt = 9, str = 40;
    int64_t st = (int64_t)(rnd() % 16) | (rnd() % 2 ? 16 : 0) | (rnd() % 2 ? 32 : 0);
    if (rnd() % 6 == 0) st |= (int64_t)(rnd() << 6);
    unsigned m = (unsigned)(rnd() % 8);
    if (m == 1) len = pick_len(360);
    if (m == 2) cnt = (int64_t)(rnd() % 12);
    if (m == 3) str = (int64_t)(rnd() % 3 ? 32 + rnd() % 16 : rnd());
    if (m == 4) st = (int64_t)rnd();
    same(o, n, k % 211 == 0 ? 0 : b, len, cnt, str, st);
  }
  report();
}
