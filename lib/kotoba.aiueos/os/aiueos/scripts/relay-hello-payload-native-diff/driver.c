/* relay-hello-payload built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object. The
   native export takes the MAC's length after the MAC (6 here, as kernel/pci.c passes). Random and edge nonce halves
   (0, 2^31, 2^32 - 1, negative, past 2^32 - 1), random MACs, capacities 0 .. 512 (around 91 and 160 most often), and
   null out or MAC pointers; each object writes its own copy of the same random-filled buffer, and the answers, the trap
   outcomes and every byte of the two buffers (600 bytes) are compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_relay_hello_payload(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_relay_hello_payload_native(int64_t, int64_t, int64_t, int64_t, int64_t, int64_t);
static uint8_t o1[600] __attribute__((aligned(16))), o2[600] __attribute__((aligned(16))), mac[16];
/* the guard calls five arguments; the sixth (the MAC length) is passed by this shim */
static int64_t native6(int64_t a, int64_t b, int64_t c, int64_t d, int64_t e) { return kotoba_aiueos_relay_hello_payload_native(a, b, c, d, e, 6); }
static int64_t half(void) { static const int64_t E[] = {0, 1, 0x7fffffff, 0x80000000ll, 0xffffffffll, -1, 0x100000000ll}; return rnd() % 3 ? (int64_t)(rnd() & 0xffffffff) : E[rnd() % 7]; }
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  for (unsigned k = 0; k < 30000; k++) {
    for (int i = 0; i < 600; i++) o1[i] = o2[i] = (uint8_t)rnd();
    for (int i = 0; i < 16; i++) mac[i] = (uint8_t)rnd();
    unsigned c = (unsigned)(rnd() % 6);
    int64_t cap = c < 2 ? 160 : c == 2 ? 90 + (int64_t)(rnd() % 3) : c == 3 ? (int64_t)(rnd() % 513) : c == 4 ? 159 + (int64_t)(rnd() % 3) : 91 + (int64_t)(rnd() % 422);
    int64_t hi = half(), lo = half();
    int64_t p1 = k % 97 == 0 ? 0 : (int64_t)(uintptr_t)o1, p2 = k % 97 == 0 ? 0 : (int64_t)(uintptr_t)o2, pm = k % 89 == 0 ? 0 : (int64_t)(uintptr_t)mac;
    int64_t r1 = guarded_call((void *)kotoba_aiueos_relay_hello_payload, p1, cap, hi, lo, pm); int t1 = (int)guard_trapped;
    int64_t r2 = guarded_call((void *)native6, p2, cap, hi, lo, pm); int t2 = (int)guard_trapped;
    int eq = r1 == r2 && t1 == t2;
    for (int i = 0; i < 600; i++) if (o1[i] != o2[i]) eq = 0;
    n_all++; if (t1) n_trap++; else if (r1) n_nz++;
    if (!eq && n_bad++ < 10) { puts_("DIFF "); hex((uint64_t)cap, 8); hex((uint64_t)hi, 16); hex((uint64_t)lo, 16); hex((uint64_t)r1, 8); hex((uint64_t)t1, 1); hex((uint64_t)r2, 8); hex((uint64_t)t2, 1); putc_('\n'); }
  }
  report();
}
