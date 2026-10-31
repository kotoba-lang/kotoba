/* inference-status-valid built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object.
   Valid 200-byte aiueos-inference-status-record/v1 records (every phase, printable model/quant/detail texts of 1 .. 32
   bytes, measured and unmeasured durations, decode counts zero and not), then one field mutated in turn (each u32 and
   u64 field to an edge value, decode at or one past generated, a text byte out of range or a missing NUL, each non-null flag, a random byte), plus random
   records, lengths other than 200 and a null base; answers and traps compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_inference_status_valid(int64_t, int64_t);
extern int64_t kotoba_aiueos_inference_status_valid_native(int64_t, int64_t);
static uint8_t rec[512] __attribute__((aligned(16)));
static void put32(int o, uint32_t v) { for (int i = 0; i < 4; i++) rec[o + i] = (uint8_t)(v >> (8 * i)); }
static void put64(int o, uint64_t v) { put32(o, (uint32_t)v); put32(o + 4, (uint32_t)(v >> 32)); }
static void text(int at, int required) {
  int n = (int)(rnd() % 34); if (required && n == 0 && rnd() % 2) n = 1;
  for (int i = 0; i < 33; i++) rec[at + i] = i < n ? (uint8_t)(32 + rnd() % 95) : 0;
}
static uint64_t dur(void) { unsigned k = (unsigned)(rnd() % 5); return k == 0 ? ~0ull : k == 1 ? 1 : (uint64_t)rnd(); }
static uint32_t edge32(void) { static const uint32_t E[] = {0, 1, 2, 5, 7, 8, 9999999, 10000000, 10000001, 0xffffffffu}; return rnd() % 3 ? E[rnd() % 10] : (uint32_t)rnd(); }
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)rec;
  void *o = (void *)kotoba_aiueos_inference_status_valid, *n = (void *)kotoba_aiueos_inference_status_valid_native;
  for (unsigned k = 0; k < 40000; k++) {
    for (int i = 0; i < 512; i++) rec[i] = (uint8_t)rnd();
    put32(0, 2); uint32_t sz = (uint32_t)rnd(); put32(4, sz); put32(8, sz); put32(12, 1 + (uint32_t)(rnd() % 7));
    uint32_t gen = (uint32_t)(rnd() % 1000), dec = rnd() % 3 ? (uint32_t)(rnd() % (gen + 1)) : 0, tgt = rnd() % 2 ? gen + (uint32_t)(rnd() % 50) : 0;
    put32(16, (uint32_t)(rnd() % 100000)); put32(20, gen); put32(24, dec); put32(28, tgt);
    put64(48, dur()); put64(56, dur()); put64(64, dec ? 1 + (uint64_t)(rnd() >> 4) : ~0ull); put64(72, dur()); put64(80, rnd() % 4 ? (uint64_t)rnd() : 0);
    rec[88] = 1; rec[89] = 1; rec[90] = 1; rec[91] = (uint8_t)(rnd() % 2);
    text(96, 1); text(129, 1); text(162, 0);
    unsigned m = (unsigned)(rnd() % 14); int64_t len = 200;
    if (m == 1) put32(0, edge32());
    if (m == 2) put32(4 + 4 * (int)(rnd() % 2), edge32());
    if (m == 3) put32(12, edge32());
    if (m == 4) put32(16 + 4 * (int)(rnd() % 4), edge32());
    if (m == 5) put64(48 + 8 * (int)(rnd() % 5), rnd() % 2 ? 0 : ~0ull);
    if (m == 6) rec[88 + rnd() % 4] = rnd() % 2 ? 0 : (uint8_t)rnd();
    if (m == 7) rec[96 + 33 * (int)(rnd() % 3) + (int)(rnd() % 33)] = (uint8_t)(rnd() % 2 ? rnd() % 32 : 127 + rnd() % 129);
    if (m == 8) for (int i = 0; i < 33; i++) rec[96 + 33 * (int)(k % 3) + i] = (uint8_t)(32 + rnd() % 95);
    if (m == 9) rec[rnd() % 200] = (uint8_t)rnd();
    if (m == 10) for (int i = 0; i < 200; i++) rec[i] = (uint8_t)rnd();
    if (m == 11) len = rnd() % 2 ? 199 + (int64_t)(rnd() % 3) : (int64_t)(rnd() % 600);
    if (m == 12) { put32(12, 5); put32(20, rnd() % 2 ? 0 : gen); put64(80, 0); }
    if (m == 13) { put32(24, gen + (uint32_t)(rnd() % 2)); put64(64, 1); }
    same(o, n, k % 199 == 0 ? 0 : b, len, 0, 0, 0);
  }
  report();
}
