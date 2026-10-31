/* kernel-probe built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object. The probe
   takes no argument; both are called 1000 times through the #UD guard with random values left in the argument registers,
   and the answers (42, which kernel/main.c checks) and the trap outcomes are compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_probe(void);
extern int64_t kotoba_aiueos_probe_native(void);
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  for (unsigned k = 0; k < 1000; k++)
    same((void *)kotoba_aiueos_probe, (void *)kotoba_aiueos_probe_native, (int64_t)rnd(), (int64_t)rnd(), (int64_t)rnd(), (int64_t)rnd(), (int64_t)rnd());
  report();
}
