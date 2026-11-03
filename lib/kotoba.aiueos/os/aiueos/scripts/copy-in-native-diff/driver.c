/* copy-in built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object. Random source
   bytes copied into a destination that starts identical for both objects, over source and destination lengths 0 .. 520
   (the guard admits at most 512 each) and counts 0 .. the larger length plus a few (negative, past either length),
   overlapping source and destination, and null bases; the answer, the trap outcome and all 1024 destination bytes are
   compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_copy_in(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_copy_in_native(int64_t, int64_t, int64_t, int64_t, int64_t);
static uint8_t src[1024] __attribute__((aligned(16))), d1[1024] __attribute__((aligned(16))), d2[1024] __attribute__((aligned(16)));
static uint8_t ov1[1600], ov2[1600];
static unsigned n_copied;
static int64_t len_pick(void) { unsigned k = (unsigned)(rnd() % 5); return k == 0 ? (int64_t)(rnd() % 521) : k == 1 ? 512 - (int64_t)(rnd() % 3) + 1 : (int64_t)(rnd() % 300); }
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  void *o = (void *)kotoba_aiueos_copy_in, *n = (void *)kotoba_aiueos_copy_in_native;
  for (unsigned k = 0; k < 6000; k++) {
    for (int i = 0; i < 1024; i++) { src[i] = (uint8_t)rnd(); d1[i] = d2[i] = (uint8_t)rnd(); }
    int64_t sl = len_pick(), dl = len_pick(), mx = sl > dl ? sl : dl;
    int64_t c = rnd() % 4 ? (sl < dl ? sl : dl) - (int64_t)(rnd() % 3) : (int64_t)(rnd() % (uint64_t)(mx + 4)) - 1;
    int64_t bs = (int64_t)(uintptr_t)src;
    if (k % 97 == 0) bs = 0;
    int64_t r1 = guarded_call(o, bs, sl, (int64_t)(uintptr_t)d1, dl, c); int t1 = (int)guard_trapped;
    int64_t r2 = guarded_call(n, bs, sl, (int64_t)(uintptr_t)d2, dl, c); int t2 = (int)guard_trapped;
    int eq = r1 == r2 && t1 == t2;
    for (int i = 0; i < 1024; i++) if (d1[i] != d2[i]) eq = 0;
    n_all++; if (t1) n_trap++; else if (r1) { n_nz++; n_copied += (unsigned)c; }
    if (!eq && n_bad++ < 10) { puts_("DIFF "); hex((uint64_t)sl, 8); hex((uint64_t)dl, 8); hex((uint64_t)c, 16); hex((uint64_t)r1, 2); hex((uint64_t)t1, 1); hex((uint64_t)r2, 2); hex((uint64_t)t2, 1); putc_('\n'); }
  }
  for (unsigned k = 0; k < 400; k++) {   /* source and destination overlap, the destination before or after the source */
    for (int i = 0; i < 1600; i++) ov1[i] = ov2[i] = (uint8_t)rnd();
    int64_t c = 1 + (int64_t)(rnd() % 512), shift = (int64_t)(rnd() % 64) - 32, at = 600;
    int64_t r1 = guarded_call(o, (int64_t)(uintptr_t)(ov1 + at), 512, (int64_t)(uintptr_t)(ov1 + at + shift), 512, c); int t1 = (int)guard_trapped;
    int64_t r2 = guarded_call(n, (int64_t)(uintptr_t)(ov2 + at), 512, (int64_t)(uintptr_t)(ov2 + at + shift), 512, c); int t2 = (int)guard_trapped;
    int eq = r1 == r2 && t1 == t2;
    for (int i = 0; i < 1600; i++) if (ov1[i] != ov2[i]) eq = 0;
    n_all++; if (t1) n_trap++; else if (r1) n_nz++;
    if (!eq && n_bad++ < 10) { puts_("ODIFF "); hex((uint64_t)c, 8); hex((uint64_t)shift, 16); putc_('\n'); }
  }
  puts_("COPIED "); hex(n_copied, 8); putc_('\n');
  report();
}
