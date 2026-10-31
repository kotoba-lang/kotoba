/* msr-write built on amu's native object route (JUN-552, amu ADR 0399) against the committed kotoba-compiler/1 object.
   Both are linked into one image. For each (index, value) the five admitted MSRs are read with rdmsr, the old object is
   called through the #UD guard, the five are read again and restored, then the same for the native object: the answers,
   the trap outcomes and all five registers after the call must agree. Indices: the five admitted ones, unlisted
   neighbours and architectural MSRs (no write may happen), the i64 extremes and the admitted indices plus 2^32. Values:
   STAR any 64 bits, LSTAR canonical (half in the upper half), FMASK 32 bits, and for EFER and APIC_BASE the
   read-modify-writes the kernel performs (the current value, | SCE, | NXE, | both; the current value, | global enable),
   with SCE first clear and then set. The BOUND section (not counted in DIFFS) writes EFER / APIC_BASE values the native
   route's run-time bound refuses -- a cleared SCE, a cleared global enable, a moved window -- and counts the old
   object's writes and the native object's #UD traps. */
#include <stdint.h>
#include "diff.h"
extern int64_t kotoba_aiueos_msr_write(int64_t, int64_t);
extern int64_t kotoba_aiueos_msr_write_native(int64_t, int64_t);
static uint64_t rdmsr(uint32_t i) { uint32_t lo, hi; __asm__ volatile("rdmsr" : "=a"(lo), "=d"(hi) : "c"(i)); return (uint64_t)hi << 32 | lo; }
static void wrmsr(uint32_t i, uint64_t v) { __asm__ volatile("wrmsr" :: "c"(i), "a"((uint32_t)v), "d"((uint32_t)(v >> 32))); }
static void cpuid(uint32_t l, uint32_t r[4]) { __asm__ volatile("cpuid" : "=a"(r[0]), "=b"(r[1]), "=c"(r[2]), "=d"(r[3]) : "a"(l), "c"(0)); }
static uint64_t rnd64(void) { return rnd() << 40 ^ rnd() << 20 ^ rnd(); }
static const uint32_t MSR[5] = {0x1b, 0xc0000080, 0xc0000081, 0xc0000082, 0xc0000084};
static uint64_t s0[5], s1[5];
static void snap(uint64_t *s) { for (int k = 0; k < 5; k++) s[k] = rdmsr(MSR[k]); }
static void restore(const uint64_t *s) { for (int k = 0; k < 5; k++) if (rdmsr(MSR[k]) != s[k]) wrmsr(MSR[k], s[k]); }
static unsigned n_written;
static void one(int64_t i, int64_t v) {
  uint64_t before[5]; snap(before);
  int64_t r0 = guarded_call(kotoba_aiueos_msr_write, i, v, 0, 0, 0); int t0 = (int)guard_trapped; snap(s0); restore(before);
  int64_t r1 = guarded_call(kotoba_aiueos_msr_write_native, i, v, 0, 0, 0); int t1 = (int)guard_trapped; snap(s1); restore(before);
  int eq = r0 == r1 && t0 == t1;
  for (int k = 0; k < 5; k++) if (s0[k] != s1[k]) eq = 0;
  n_all++; if (t0) n_trap++; else if (r0) n_nz++;
  for (int k = 0; k < 5; k++) if (s0[k] != before[k]) { n_written++; break; }
  if (!eq && n_bad++ < 10) { puts_("DIFF "); hex((uint64_t)i, 16); hex((uint64_t)v, 16); hex((uint64_t)r0, 2); hex((uint64_t)t0, 1); hex((uint64_t)r1, 2); hex((uint64_t)t1, 1); putc_('\n'); }
}
static const int64_t OTHER[] = {0, 1, 16, 26, 28, 0x1a0, 0x277, 0x3a, 0xc000007f, 0xc0000083, 0xc0000085, 0xc0000100,
  0xc0000101, 0xc0000102, -1, -27, INT64_MIN, INT64_MAX, (1ll << 32) + 27, (1ll << 32) + 3221225600, (1ll << 32) + 3221225601,
  (1ll << 32) + 3221225604, 4294967295, 3221225601 - (1ll << 32)};
void test_main(void) {
  guard_init();
  puts_("MSRWRITE\n");
  uint32_t c[4]; cpuid(0x80000001, c); int nx = (c[3] >> 20) & 1;
  for (int round = 0; round < 2; round++) {
    if (round) wrmsr(0xc0000080, rdmsr(0xc0000080) | 1);       /* the second round starts with SCE set */
    uint64_t efer = rdmsr(0xc0000080), apic = rdmsr(0x1b);
    one(0xc0000080, (int64_t)efer); one(0xc0000080, (int64_t)(efer | 1));
    if (nx) { one(0xc0000080, (int64_t)(efer | 0x800)); one(0xc0000080, (int64_t)(efer | 0x801)); }
    one(27, (int64_t)apic); one(27, (int64_t)(apic | 0x800));
  }
  for (int k = 0; k < 300; k++) {
    uint64_t v = rnd64(), a = rnd64() & 0x7fffffffffffull;
    one(3221225601, (int64_t)v);
    one(3221225602, (int64_t)((k & 1) ? a : (a | 0xffff800000000000ull)));
    one(3221225604, (int64_t)(v & 0xffffffffull));
    one(OTHER[k % (sizeof OTHER / 8)], (int64_t)v);
    one((int64_t)(rnd() & 0xffffffffu), (int64_t)v);
    one((int64_t)rnd64(), (int64_t)v);
  }
  puts_("WRITTEN "); hex(n_written, 8); putc_('\n');
  /* BOUND: old writes, native traps */
  unsigned b_all = 0, b_old = 0, b_new = 0;
  uint64_t efer = rdmsr(0xc0000080) | 1, apic = rdmsr(0x1b);
  wrmsr(0xc0000080, efer);
  const uint32_t BI[3] = {0xc0000080, 0x1b, 0x1b};
  const uint64_t BV[3] = {efer & ~1ull, apic & ~0x800ull, apic ^ 0x1000};
  for (int k = 0; k < 3; k++) {
    uint64_t before[5]; snap(before);
    int64_t r0 = guarded_call(kotoba_aiueos_msr_write, BI[k], (int64_t)BV[k], 0, 0, 0); int t0 = (int)guard_trapped; snap(s0); restore(before);
    guarded_call(kotoba_aiueos_msr_write_native, BI[k], (int64_t)BV[k], 0, 0, 0); int t1 = (int)guard_trapped; snap(s1); restore(before);
    b_all++; if (r0 == 1 && !t0 && s0[BI[k] == 0x1b ? 0 : 1] == BV[k]) b_old++;
    if (t1 && s1[0] == before[0] && s1[1] == before[1]) b_new++;
  }
  puts_("BOUND "); hex(b_all, 2); puts_("OLD-WROTE "); hex(b_old, 2); puts_("NATIVE-TRAPPED "); hex(b_new, 2); putc_('\n');
  report();
}
