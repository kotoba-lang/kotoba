/* rtl8125-tx-submit built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object, behind
   the MMIO trap harness (../mmio-trap). The native export takes the descriptor's length after the descriptor (the old
   one had none and wrote through a literal 32-byte window), so the old object is called as (mmio len desc phys flen)
   and the native one as (mmio len desc 32 phys flen); each native call is repeated with a length other than 32, which
   must answer 1 (AIUEOS_RTL8125_INVALID) with no bus access and the descriptor untouched. Cases: the window at
   TRAP_WINDOW, null or negative, length 4096 or another; descriptors at a 256-aligned base, misaligned or null, with
   the OWN bit set or clear and random other bytes; frame addresses positive, zero or negative; frame lengths 0..2100.
   Both objects start from the same registers and descriptor bytes; the answers, every bus transaction in order (the
   FNV trace and the count), the registers after and every descriptor byte are compared. */
#include "../mmio-trap/trap.h"
extern uint64_t kotoba_aiueos_rtl8125_tx_submit(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
extern uint64_t kotoba_aiueos_rtl8125_tx_submit_native(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 708;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 13; }
void trap_model_after_write(unsigned offset) { (void)offset; }
static uint8_t start[4096], after[4096];
static uint8_t d0[768] __attribute__((aligned(256))), d1[768] __attribute__((aligned(256))), d2[768] __attribute__((aligned(256)));
static unsigned n_cases, n_zero, n_bad, n_len, n_len_bad;
void test_main(void) {
  puts_("RTL8125TXSUBMITDIFF\n");
  trap_init();
  for (unsigned k = 0; k < 8000; k++) {
    for (int i = 0; i < 4096; i++) start[i] = (uint8_t)rnd();
    for (int i = 0; i < 768; i++) d0[i] = (uint8_t)rnd();
    unsigned w = (unsigned)(rnd() % 12);
    uint64_t mmio = w < 10 ? TRAP_WINDOW : w == 10 ? 0 : (uint64_t)-(int64_t)(1 + rnd() % 4096);
    uint64_t mlen = rnd() % 8 ? 4096 : rnd() % 2 ? 4095 + rnd() % 3 : rnd() % 20000;
    unsigned b = (unsigned)(rnd() % 12);
    int64_t off = b < 9 ? 256 : b < 11 ? 256 + 4 * (int64_t)(1 + rnd() % 63) : -1;
    if (off >= 0) { if (rnd() % 3) d0[off + 3] &= 0x7f; else d0[off + 3] |= 0x80; }
    unsigned f = (unsigned)(rnd() % 8);
    uint64_t fp = f < 6 ? 0x100000 + (rnd() % 0x10000) * 16 : f == 6 ? 0 : (uint64_t)-(int64_t)(1 + rnd() % 100);
    uint64_t flen = rnd() % 4 ? 14 + rnd() % 2035 : rnd() % 2101;
    for (int i = 0; i < 768; i++) d1[i] = d2[i] = d0[i];
    uint64_t b1 = off < 0 ? 0 : (uint64_t)(uintptr_t)(d1 + off), b2 = off < 0 ? 0 : (uint64_t)(uintptr_t)(d2 + off);
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    trap_reset(); uint64_t r1 = kotoba_aiueos_rtl8125_tx_submit(mmio, mlen, b1, fp, flen);
    uint64_t t1 = trap_trace; unsigned a1 = trap_accesses; for (int i = 0; i < 4096; i++) after[i] = trap_regs[i];
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    trap_reset(); uint64_t r2 = kotoba_aiueos_rtl8125_tx_submit_native(mmio, mlen, b2, 32, fp, flen);
    int same = r1 == r2 && t1 == trap_trace && a1 == trap_accesses;
    for (int i = 0; i < 4096; i++) if (after[i] != trap_regs[i]) same = 0;
    for (int i = 0; i < 768; i++) if (d1[i] != d2[i]) same = 0;
    n_cases++; if (r1 == 0) n_zero++;
    if (!same && n_bad++ < 8) { puts_("DIFF "); hex(k, 4); hex(r1, 1); hex(r2, 1); hex(a1, 2); hex(trap_accesses, 2); putc_('\n'); }
    uint64_t bad = rnd() % 2 ? rnd() % 64 : rnd(); if (bad == 32) bad = 33;
    for (int i = 0; i < 768; i++) d2[i] = d0[i];
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    trap_reset(); uint64_t r3 = kotoba_aiueos_rtl8125_tx_submit_native(mmio, mlen, b2, bad, fp, flen);
    int ok = r3 == 1 && trap_accesses == 0;
    for (int i = 0; i < 4096; i++) if (trap_regs[i] != start[i]) ok = 0;
    for (int i = 0; i < 768; i++) if (d2[i] != d0[i]) ok = 0;
    n_len++; if (!ok && n_len_bad++ < 4) { puts_("LENDIFF "); hex(k, 4); hex(r3, 2); putc_('\n'); }
  }
  puts_("LENGTHS "); hex(n_len, 4); puts_("LENDIFFS "); hex(n_len_bad, 4); putc_('\n');
  if (n_len_bad) n_bad++;
  puts_("CASES "); hex(n_cases, 4); puts_("SUBMITTED "); hex(n_zero, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
