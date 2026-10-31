/* model-mapping-plan built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object.
   Bases and sizes around every bound the plan checks (2 MiB alignment, 1 GiB, the 3 .. 4 GiB APIC hole, 64 GiB, 16
   directories) plus random ones; each object writes into its own copy of the same random-filled buffer, and the answers,
   the trap outcomes and every byte of the two buffers (the 32-byte record and 32 bytes either side) are compared. A null
   out pointer is included. */
#include "diff.h"
extern int64_t kotoba_aiueos_model_mapping_plan(int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_model_mapping_plan_native(int64_t, int64_t, int64_t);
static uint8_t o1[96] __attribute__((aligned(16))), o2[96] __attribute__((aligned(16)));
#define GIB (1ll << 30)
#define MIB2 (1ll << 21)
static const int64_t B[] = {0, MIB2, GIB - MIB2, GIB, GIB + MIB2, 2 * GIB, 3 * GIB - MIB2, 3 * GIB, 4 * GIB, 4 * GIB + MIB2,
  5 * GIB, 16 * GIB, 63 * GIB, 64 * GIB - MIB2, 64 * GIB, 65 * GIB, -MIB2, INT64_MIN};
static const int64_t Z[] = {0, 1, MIB2 - 1, MIB2, MIB2 + 1, GIB - 1, GIB, GIB + 1, 2 * GIB, 15 * GIB, 16 * GIB, 16 * GIB + 1,
  17 * GIB, 60 * GIB, 64 * GIB, -1, INT64_MAX};
static int64_t pick(const int64_t *v, unsigned nv) {
  unsigned k = (unsigned)(rnd() % 4);
  return k == 0 ? (int64_t)(rnd() << 6) : k == 1 ? v[rnd() % nv] + (int64_t)(rnd() % 3) - 1
       : k == 2 ? v[rnd() % nv] + (int64_t)(rnd() % 64) * MIB2 : v[rnd() % nv];
}
static void one(int64_t base, int64_t size, int null) {
  for (int i = 0; i < 96; i++) o1[i] = o2[i] = (uint8_t)rnd();
  int64_t p1 = null ? 0 : (int64_t)(uintptr_t)(o1 + 32), p2 = null ? 0 : (int64_t)(uintptr_t)(o2 + 32);
  int64_t r1 = guarded_call((void *)kotoba_aiueos_model_mapping_plan, base, size, p1, 0, 0); int t1 = (int)guard_trapped;
  int64_t r2 = guarded_call((void *)kotoba_aiueos_model_mapping_plan_native, base, size, p2, 0, 0); int t2 = (int)guard_trapped;
  int eq = r1 == r2 && t1 == t2;
  for (int i = 0; i < 96; i++) if (o1[i] != o2[i]) eq = 0;
  n_all++; if (t1) n_trap++; else if (r1) n_nz++;
  if (!eq && n_bad++ < 10) { puts_("DIFF "); hex((uint64_t)base, 16); hex((uint64_t)size, 16); hex((uint64_t)r1, 8); hex((uint64_t)t1, 1); hex((uint64_t)r2, 8); hex((uint64_t)t2, 1); putc_('\n'); }
}
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  for (unsigned i = 0; i < sizeof B / sizeof B[0]; i++)
    for (unsigned j = 0; j < sizeof Z / sizeof Z[0]; j++) one(B[i], Z[j], 0);
  for (unsigned k = 0; k < 40000; k++) one(pick(B, sizeof B / sizeof B[0]), pick(Z, sizeof Z / sizeof Z[0]), k % 101 == 0);
  report();
}
