/* service-registry-state built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object.
   Valid 32-byte service-registry transactions (sector 3, version 2, size 16, "SRV1", the two service ids, nonzero state
   bytes) with one field then mutated in turn (each header word, each tag byte, each id, a zero state byte), the service
   argument over 0, 1 and refusals, random records, lengths 0 .. 40 and past the 512-byte window, and a null base;
   answers and traps compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_service_registry_state(int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_service_registry_state_native(int64_t, int64_t, int64_t);
static uint8_t buf[1024] __attribute__((aligned(16)));
static void put32(int o, uint32_t v) { for (int i = 0; i < 4; i++) buf[o + i] = (uint8_t)(v >> (8 * i)); }
static const int64_t SVC[] = {0, 1, 0, 1, 2, -1, 3, INT64_MIN, 256};
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)buf;
  void *o = (void *)kotoba_aiueos_service_registry_state, *n = (void *)kotoba_aiueos_service_registry_state_native;
  for (unsigned k = 0; k < 20000; k++) {
    for (int i = 0; i < 1024; i++) buf[i] = (uint8_t)rnd();
    put32(0, 3); put32(4, 2); put32(8, 16);
    buf[16] = 83; buf[17] = 82; buf[18] = 86; buf[19] = 49; buf[20] = 1; buf[21] = 2;
    for (int i = 24; i < 30; i++) if (!buf[i] && (i != 26 && i != 29)) buf[i] = 1;
    unsigned m = (unsigned)(rnd() % 6);
    if (m == 1) { int f = (int)(rnd() % 22); buf[f] ^= (uint8_t)(1 + rnd() % 255); }   /* a header word or tag byte */
    if (m == 2) { static const int Z[] = {24, 25, 27, 28, 26, 29}; buf[Z[rnd() % 6]] = 0; }
    if (m == 3) for (int i = 0; i < 32; i++) buf[i] = (uint8_t)rnd();
    int64_t len = 32, svc = SVC[rnd() % 9];
    if (m == 4) len = (int64_t)(rnd() % 41);
    if (m == 5) len = (int64_t)(rnd() % 3 ? 512 + rnd() % 3 : rnd() % 1000);
    same(o, n, b, len, svc, 0, 0);
  }
  same(o, n, 0, 32, 0, 0, 0); same(o, n, b, -1, 0, 0, 0);
  report();
}
