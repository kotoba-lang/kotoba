/* task-exit-route built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object.
   Random 9-slot, 40-byte task tables (the owner at 36 from {2..5, 0, 1, 65534, 65535, random}, the active byte at 38
   from {0, 1, random}, every other byte random), called with the shipped geometry (360, 9, 40) or one argument
   disturbed, domains around 2 .. 5, 0 .. 2 and 65535, and a null base; answers and traps compared. */
#include "diff.h"
static uint8_t tb[1024] __attribute__((aligned(16)));
__attribute__((unused)) static void put16(int o, unsigned v) { tb[o] = (uint8_t)v; tb[o + 1] = (uint8_t)(v >> 8); }
__attribute__((unused)) static unsigned pick16(void) { unsigned k = (unsigned)(rnd() % 6); return k == 0 ? 0 : k == 1 ? 1 : k == 2 ? 65534 : k == 3 ? 65535 : k == 4 ? 2 + (unsigned)(rnd() % 4) : (unsigned)(rnd() & 0xffff); }
__attribute__((unused)) static uint8_t pick_flag(void) { unsigned k = (unsigned)(rnd() % 8); return k < 3 ? 0 : k < 6 ? 1 : (uint8_t)rnd(); }
__attribute__((unused)) static int64_t pick_len(int64_t good) { unsigned k = (unsigned)(rnd() % 10); return k < 7 ? good : k == 7 ? good + (int64_t)(rnd() % 3) - 1 : k == 8 ? (int64_t)(rnd() % 700) : (int64_t)rnd(); }
__attribute__((unused)) static int64_t pick_dom(void) { unsigned k = (unsigned)(rnd() % 8); return k < 5 ? 2 + (int64_t)(rnd() % 4) : k == 5 ? (int64_t)(rnd() % 3) : k == 6 ? 65535 + (int64_t)(rnd() % 3) - 1 : (int64_t)rnd(); }
extern int64_t kotoba_aiueos_task_exit_route(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_task_exit_route_native(int64_t, int64_t, int64_t, int64_t, int64_t);
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)tb;
  void *o = (void *)kotoba_aiueos_task_exit_route, *n = (void *)kotoba_aiueos_task_exit_route_native;
  for (unsigned k = 0; k < 40000; k++) {
    for (int i = 0; i < 1024; i++) tb[i] = (uint8_t)rnd();
    for (int s = 0; s < 9; s++) {
      put16(s * 40 + 36, rnd() % 3 ? 2 + (unsigned)(rnd() % 4) : pick16());
      tb[s * 40 + 38] = rnd() % 3 ? (rnd() % 4 == 0) : pick_flag();
    }
    int64_t len = 360, cnt = 9, str = 40, dom = pick_dom();
    unsigned m = (unsigned)(rnd() % 8);
    if (m == 1) len = pick_len(360);
    if (m == 2) cnt = (int64_t)(rnd() % 12);
    if (m == 3) str = (int64_t)(rnd() % 3 ? 32 + rnd() % 16 : rnd());
    same(o, n, k % 211 == 0 ? 0 : b, len, cnt, str, dom);
  }
  report();
}
