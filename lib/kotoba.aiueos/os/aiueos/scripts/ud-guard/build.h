/* For the guarded builder differentials (JUN-552): `built` runs the kotoba-compiler/1 builder and the native one on two
   copies of the same output buffer (same random fill), through the #UD guard, and counts a difference when the answers,
   the trap outcomes or any byte of the buffers differ. The argument at OUT_ARG (0 or 3) is replaced by each copy's
   address, or by 0 when null is set. */
#define BUILD_BYTES 1024
static uint8_t out1[BUILD_BYTES + 64] __attribute__((aligned(16))), out2[BUILD_BYTES + 64] __attribute__((aligned(16)));
__attribute__((unused)) static int built(void *f_old, void *f_new, int out_arg, int null, int64_t a0, int64_t a1, int64_t a2, int64_t a3, int64_t a4) {
  for (int i = 0; i < BUILD_BYTES + 64; i++) out1[i] = out2[i] = (uint8_t)rnd();
  int64_t p1 = null ? 0 : (int64_t)(uintptr_t)out1, p2 = null ? 0 : (int64_t)(uintptr_t)out2;
  int64_t r1, r2; int t1, t2;
  if (out_arg == 0) { r1 = guarded_call(f_old, p1, a1, a2, a3, a4); t1 = (int)guard_trapped; r2 = guarded_call(f_new, p2, a1, a2, a3, a4); t2 = (int)guard_trapped; }
  else { r1 = guarded_call(f_old, a0, a1, a2, p1, a4); t1 = (int)guard_trapped; r2 = guarded_call(f_new, a0, a1, a2, p2, a4); t2 = (int)guard_trapped; }
  int eq = r1 == r2 && t1 == t2;
  for (int i = 0; i < BUILD_BYTES + 64; i++) if (out1[i] != out2[i]) eq = 0;
  n_all++; if (t1) n_trap++; else if (r1) n_nz++;
  if (!eq && n_bad++ < 10) { puts_("DIFF "); hex((uint64_t)a1, 8); hex((uint64_t)a2, 16); hex((uint64_t)r1, 8); hex((uint64_t)t1, 1); hex((uint64_t)r2, 8); hex((uint64_t)t2, 1); putc_('\n'); }
  return eq;
}
