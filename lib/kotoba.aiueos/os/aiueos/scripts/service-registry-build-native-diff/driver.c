/* service-registry-build built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object:
   the service-registry transaction each writes into a random-filled buffer, over lengths 512 (the one it admits), 0,
   511, 513 and random ones, sequences 0, 1, negative and random, and random service states (each state's three bytes
   spread over its 16-bit fields), and a null base; the answer, the trap outcome and all of both buffers compared. */
#include "diff.h"
#include "build.h"
extern int64_t kotoba_aiueos_service_registry_build(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_service_registry_build_native(int64_t, int64_t, int64_t, int64_t, int64_t);
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  void *o = (void *)kotoba_aiueos_service_registry_build, *n = (void *)kotoba_aiueos_service_registry_build_native;
  static const int64_t L[] = {512, 512, 512, 0, 511, 513, 64, -1};
  for (unsigned k = 0; k < 6000; k++) {
    int64_t len = k % 5 ? L[rnd() % 8] : (int64_t)(rnd() % 1000);
    int64_t seq = rnd() % 5 ? 1 + (int64_t)(rnd() % 1000) : (int64_t)(rnd() % 3) - 1;
    int64_t s0 = rnd() % 3 ? (int64_t)(rnd() % 256 | (rnd() % 256) << 16 | (rnd() % 256) << 32) : (int64_t)rnd() << 20 ^ (int64_t)rnd();
    int64_t s1 = rnd() % 3 ? (int64_t)(rnd() % 256 | (rnd() % 256) << 16 | (rnd() % 256) << 32) : (int64_t)rnd();
    built(o, n, 0, k % 199 == 0, 0, len, seq, s0, s1);
  }
  report();
}
