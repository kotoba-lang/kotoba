/* rtl8125-link-up built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object, behind
   the MMIO trap harness (../mmio-trap). Random 4 KiB register files whose PHYSTATUS (0x6c) has the link bit set or
   clear, with the window length 4096 or another; both objects start from the same registers, and the answers, every bus
   transaction in order (the FNV trace and the count) and the registers after are compared. */
#include "../mmio-trap/trap.h"
extern uint64_t kotoba_aiueos_rtl8125_link_up(uint64_t, uint64_t);
extern uint64_t kotoba_aiueos_rtl8125_link_up_native(uint64_t, uint64_t);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 708;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 13; }
void trap_model_after_write(unsigned offset) { (void)offset; }
static uint8_t start[4096], after[4096];
static unsigned n_cases, n_up, n_bad;
void test_main(void) {
  puts_("RTL8125LINKUPDIFF\n");
  trap_init();
  for (unsigned k = 0; k < 6000; k++) {
    for (int i = 0; i < 4096; i++) start[i] = (uint8_t)rnd();
    if (rnd() % 2) start[0x6c] |= 2; else start[0x6c] &= (uint8_t)~2;
    uint64_t len = rnd() % 8 ? 4096 : rnd() % 2 ? 4095 + rnd() % 3 : rnd() % 20000;
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    trap_reset(); uint64_t r1 = kotoba_aiueos_rtl8125_link_up(TRAP_WINDOW, len);
    uint64_t t1 = trap_trace; unsigned a1 = trap_accesses; for (int i = 0; i < 4096; i++) after[i] = trap_regs[i];
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    trap_reset(); uint64_t r2 = kotoba_aiueos_rtl8125_link_up_native(TRAP_WINDOW, len);
    int same = r1 == r2 && t1 == trap_trace && a1 == trap_accesses;
    for (int i = 0; i < 4096; i++) if (after[i] != trap_regs[i]) same = 0;
    n_cases++; if (r1) n_up++;
    if (!same && n_bad++ < 8) { puts_("DIFF "); hex(k, 4); hex(r1, 1); hex(r2, 1); hex(a1, 2); hex(trap_accesses, 2); putc_('\n'); }
  }
  puts_("CASES "); hex(n_cases, 4); puts_("ADMITTED "); hex(n_up, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
