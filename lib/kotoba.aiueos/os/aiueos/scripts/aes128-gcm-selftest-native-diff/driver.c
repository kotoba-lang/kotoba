/* aes128-gcm-selftest built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object. The
   ABI is unchanged: (scratch length), answering 0 when all five McGrew-Viega steps pass, the failing step otherwise, or
   6 for a length below 1536. Cases: scratch regions of random bytes with lengths 1536 (both must answer 0), 1535
   (refused with 6), 1537, 4096 and 2^40; scratch regions of all zeros and all ones; and a null scratch. Both objects start from the same 1536 bytes and 64 past them; answers, traps (through the #UD guard) and every
   byte are compared. Built with -DSHARD=k -DNSHARD=n, an image takes cases k, k+n, ...; case 39 is the null scratch. */
#include "diff.h"
extern int64_t kotoba_aiueos_aes128_gcm_selftest(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_aes128_gcm_selftest_native(int64_t, int64_t, int64_t, int64_t, int64_t);
#define SB (1536 + 64)
static uint8_t s1[SB], s2[SB];
static unsigned n_kat, n_kat_bad;
#define I(p) ((int64_t)(uintptr_t)(p))
void test_main(void) {
  guard_init(); puts_("AESSELFTESTDIFF\n");
  static const int64_t L[5] = {1536, 1535, 1537, 4096, 1ll << 40};
  for (unsigned k = SHARD; k < 40; k += NSHARD) {
    for (int i = 0; i < SB; i++) s1[i] = s2[i] = (uint8_t)(k % 3 == 0 ? 0 : k % 3 == 1 ? 0xff : rnd());
    int64_t l = L[k % 5]; int null = k == 39;
    last_old = guarded_call((void *)kotoba_aiueos_aes128_gcm_selftest, null ? 0 : I(s1), l, 0, 0, 0); int t1 = (int)guard_trapped;
    last_new = guarded_call((void *)kotoba_aiueos_aes128_gcm_selftest_native, null ? 0 : I(s2), l, 0, 0, 0); int t2 = (int)guard_trapped;
    int eq = last_old == last_new && t1 == t2;
    for (int i = 0; i < SB; i++) if (s1[i] != s2[i]) eq = 0;
    n_all++; if (t1) n_trap++; else if (last_old) n_nz++;
    if (!eq && n_bad++ < 10) { puts_("DIFF "); hex(k, 4); hex((uint64_t)l, 12); hex((uint64_t)last_old, 2); hex((uint64_t)t1, 1); hex((uint64_t)last_new, 2); hex((uint64_t)t2, 1); putc_('\n'); }
    if (!null) { n_kat++; if ((t1 || last_old != (l < 1536 ? 6 : 0)) && n_kat_bad++ < 6) { puts_("KATFAIL "); hex(k, 4); hex((uint64_t)last_old, 2); putc_('\n'); } }
  }
  puts_("KATS "); hex(n_kat, 4); puts_("KATFAILS "); hex(n_kat_bad, 4); putc_('\n');
  if (n_kat_bad) n_bad++;
  report();
}
