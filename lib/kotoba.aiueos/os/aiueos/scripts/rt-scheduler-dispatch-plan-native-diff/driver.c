/* rt-scheduler-dispatch-plan built on amu's native object route (JUN-722, JUN-708) against the amu 53799cb object of
   main 455b84fb it replaces. That object exports kotoba_aiueos_scheduler_dispatch_plan; the native one exports the RT
   kernel's name, kotoba_aiueos_rt_scheduler_plan, so the two link side by side unchanged.
   Random 16-slot, 16-byte RT descriptor tables (state from {0..3, random}, effective priority from a small pool or
   random, policy from {0, 1, random}, budget and deadline from {0, 1, random}, sequence random, reserved bytes random),
   called with the shipped geometry (256, 16, 16) or one argument disturbed, a state word whose current slot is
   0 .. 19 with the quantum-expired bit (256) and random high bits, and a null base; answers and traps compared. */
#include "diff.h"
static uint8_t tb[1024] __attribute__((aligned(16)));
static uint8_t pick_state(void) { unsigned k = (unsigned)(rnd() % 10); return k < 4 ? 1 : k < 6 ? 2 : k == 6 ? 0 : k == 7 ? 3 : (uint8_t)rnd(); }
static uint8_t pick_prio(void) { unsigned k = (unsigned)(rnd() % 6); return k < 4 ? (uint8_t)(1 + rnd() % 4) : k == 4 ? 255 : (uint8_t)rnd(); }
static uint8_t pick_flag(void) { unsigned k = (unsigned)(rnd() % 8); return k < 3 ? 0 : k < 6 ? 1 : (uint8_t)rnd(); }
static uint8_t pick_tick(void) { unsigned k = (unsigned)(rnd() % 8); return k < 1 ? 0 : k < 3 ? 1 : (uint8_t)rnd(); }
static int64_t pick_len(int64_t good) { unsigned k = (unsigned)(rnd() % 10); return k < 7 ? good : k == 7 ? good + (int64_t)(rnd() % 3) - 1 : k == 8 ? (int64_t)(rnd() % 700) : (int64_t)rnd(); }
extern int64_t kotoba_aiueos_scheduler_dispatch_plan(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_rt_scheduler_plan(int64_t, int64_t, int64_t, int64_t, int64_t);
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)tb;
  void *o = (void *)kotoba_aiueos_scheduler_dispatch_plan, *n = (void *)kotoba_aiueos_rt_scheduler_plan;
  for (unsigned k = 0; k < 40000; k++) {
    for (int i = 0; i < 1024; i++) tb[i] = (uint8_t)rnd();
    unsigned sparse = (unsigned)(rnd() % 3);
    for (int s = 0; s < 16; s++) {
      tb[s * 16] = sparse == 0 && rnd() % 3 ? 0 : pick_state();
      tb[s * 16 + 2] = pick_prio(); tb[s * 16 + 3] = pick_flag();
      tb[s * 16 + 4] = pick_tick(); tb[s * 16 + 5] = pick_tick();
      if (rnd() % 4 == 0) tb[s * 16 + 6] = (uint8_t)(rnd() % 4);
    }
    int64_t len = 256, cnt = 16, str = 16;
    int64_t st = (int64_t)(rnd() % 20) | (rnd() % 2 ? 256 : 0);
    if (rnd() % 6 == 0) st |= (int64_t)(rnd() << 9);
    unsigned m = (unsigned)(rnd() % 8);
    if (m == 1) len = pick_len(256);
    if (m == 2) cnt = (int64_t)(rnd() % 20);
    if (m == 3) str = (int64_t)(rnd() % 3 ? 8 + rnd() % 16 : rnd());
    if (m == 4) st = (int64_t)rnd();
    same(o, n, k % 211 == 0 ? 0 : b, len, cnt, str, st);
  }
  report();
}
