/* device-worker-canonical built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object
   (same ABI). Random 576-byte worker contexts in the device-result-v1 layout (kernel/device_result.h): protocol 2, 3 or
   another byte; operation 1..3 or another; stop reason 0..4 or random; the thirteen 8-byte big-endian numbers below 2^56
   (0, small, 10^k - 1, 10^k, 2^56 - 1 or random) or with a nonzero top byte; the text fields printable or random; the
   protocol-3 fields set or left zero, so every clause (-1..-7) and both protocols' records are reached; context lengths
   576, 575 or up to 9000 and output capacities 1024, 1023 or up to 9000; a null context or output. Both objects start
   from the same context and the same random output bytes; answers, traps (through the #UD guard) and every output and
   context byte are compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_device_worker_canonical(int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_device_worker_canonical_native(int64_t, int64_t, int64_t, int64_t);
static uint8_t c0[9000], c1[9000], c2[9000], o1[9064], o2[9064];
static unsigned n_rec2, n_rec3;
static uint64_t num(void) {
  static const uint64_t P[] = {1ull, 10ull, 100ull, 1000ull, 100000ull, 10000000000ull, 10000000000000000ull};
  unsigned m = (unsigned)(rnd() % 7);
  return m == 0 ? 0 : m == 1 ? rnd() % 1000 : m == 2 ? P[rnd() % 7] - 1 : m == 3 ? P[rnd() % 7] : m == 4 ? (1ull << 56) - 1 : (rnd() << 20 ^ rnd()) & ((1ull << 56) - 1);
}
static void put(int at, uint64_t v) { for (int i = 0; i < 8; i++) c0[at + i] = (uint8_t)(v >> (56 - 8 * i)); }
void test_main(void) {
  guard_init(); puts_("DWCDIFF\n");
  void *fo = (void *)kotoba_aiueos_device_worker_canonical, *fn = (void *)kotoba_aiueos_device_worker_canonical_native;
  for (unsigned k = 0; k < 6000; k++) {
    for (int i = 0; i < 9000; i++) c0[i] = (uint8_t)rnd();
    for (int i = 128; i < 576; i++) if (rnd() % 8) c0[i] = (uint8_t)(32 + rnd() % 95);
    unsigned pr = (unsigned)(rnd() % 10);
    c0[0] = pr < 5 ? 2 : pr < 9 ? 3 : (uint8_t)rnd();
    c0[1] = rnd() % 8 ? (uint8_t)(1 + rnd() % 3) : (uint8_t)rnd();
    c0[2] = rnd() % 3 ? (c0[0] == 3 && c0[1] == 2 ? (uint8_t)(1 + rnd() % 3) : 0) : (uint8_t)(rnd() % 5);
    for (int s = 0; s < 13; s++) { put(8 + 8 * s, num()); if (rnd() % 40 == 0) c0[8 + 8 * s] = (uint8_t)(1 + rnd() % 255); }
    if (c0[0] == 2 && rnd() % 6) { for (int i = 368; i < 496; i++) c0[i] = 0; put(104, 0); if (rnd() % 2) c0[2] = 0; }
    for (int i = 3; i < 8; i++) if (rnd() % 2) c0[i] = 0;
    for (int i = 112; i < 128; i++) if (rnd() % 2) c0[i] = 0;
    unsigned lc = (unsigned)(rnd() % 10), lo = (unsigned)(rnd() % 10);
    int64_t cl = lc < 7 ? 576 : lc == 7 ? 575 : 576 + (int64_t)(rnd() % 8424);
    int64_t ol = lo < 7 ? 1024 : lo == 7 ? 1023 : 1024 + (int64_t)(rnd() % 8040);
    int nul = k % 97 == 5 ? 1 + (int)(k % 2) : 0;
    for (int i = 0; i < 9000; i++) c1[i] = c2[i] = c0[i];
    for (int i = 0; i < 9064; i++) o1[i] = o2[i] = (uint8_t)rnd();
    int64_t r1 = guarded_call(fo, nul == 1 ? 0 : (int64_t)(uintptr_t)c1, cl, nul == 2 ? 0 : (int64_t)(uintptr_t)o1, ol, 0); int t1 = (int)guard_trapped;
    int64_t r2 = guarded_call(fn, nul == 1 ? 0 : (int64_t)(uintptr_t)c2, cl, nul == 2 ? 0 : (int64_t)(uintptr_t)o2, ol, 0); int t2 = (int)guard_trapped;
    int eq = r1 == r2 && t1 == t2;
    for (int i = 0; i < 9064; i++) if (o1[i] != o2[i]) eq = 0;
    for (int i = 0; i < 9000; i++) if (c1[i] != c2[i] || c1[i] != c0[i]) eq = 0;
    n_all++; if (t1) n_trap++; else if (r1 > 0) { n_nz++; if (c0[0] == 2) n_rec2++; else n_rec3++; }
    if (!eq && n_bad++ < 10) { puts_("DIFF "); hex(k, 4); hex((uint64_t)r1, 16); hex((uint64_t)t1, 1); hex((uint64_t)r2, 16); hex((uint64_t)t2, 1); putc_('\n'); }
  }
  puts_("RECORDS-V2 "); hex(n_rec2, 4); puts_("RECORDS-V3 "); hex(n_rec3, 4); putc_('\n');
  report();
}
