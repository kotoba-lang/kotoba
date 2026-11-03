/* rtl8125-identify built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object, behind
   the MMIO trap harness (../mmio-trap). Random 4 KiB register files whose TXCFG (0x40) carries each supported revision
   mask, a near miss or random bits, and whose MAC0/MAC4 are random, zero, all-ones or multicast; the window length
   4096 or another, an out region of 16 bytes or another length, or a null out. For each case both objects start from
   the same registers and the same random out buffer; the answers, every bus transaction in order (the FNV trace and
   the count), the registers after and every byte of the out buffer are compared. */
#include "../mmio-trap/trap.h"
extern uint64_t kotoba_aiueos_rtl8125_identify(uint64_t, uint64_t, uint64_t, uint64_t);
extern uint64_t kotoba_aiueos_rtl8125_identify_native(uint64_t, uint64_t, uint64_t, uint64_t);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 708;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 13; }
void trap_model_after_write(unsigned offset) { (void)offset; }
static void w32(unsigned o, uint32_t v) { for (int i = 0; i < 4; i++) trap_regs[o + i] = (uint8_t)(v >> (8 * i)); }
static uint8_t start[4096], o1[64], o2[64], ob[64];
static unsigned n_cases, n_zero, n_bad;
void test_main(void) {
  puts_("RTL8125IDENTIFYDIFF\n");
  trap_init();
  static const uint32_t REV[] = {0x60900000u, 0x64100000u, 0x68800000u, 0x68900000u, 0x60800000u, 0x7cf00000u};
  for (unsigned k = 0; k < 6000; k++) {
    for (int i = 0; i < 4096; i++) start[i] = (uint8_t)rnd();
    uint32_t tx = rnd() % 5 ? REV[rnd() % 6] | ((uint32_t)rnd() & ~0x7cf00000u) : (uint32_t)rnd();
    for (int i = 0; i < 4; i++) start[0x40 + i] = (uint8_t)(tx >> (8 * i));
    unsigned m = (unsigned)(rnd() % 6);
    if (m == 1) for (int i = 0; i < 6; i++) start[i] = 0;
    if (m == 2) for (int i = 0; i < 6; i++) start[i] = 0xff;
    if (m == 3) start[0] |= 1;
    if (m == 4) start[0] &= 0xfe;
    uint64_t len = rnd() % 8 ? 4096 : rnd() % 2 ? 4095 + rnd() % 3 : rnd() % 20000;
    uint64_t olen = rnd() % 8 ? 16 : rnd() % 40;
    for (int i = 0; i < 64; i++) ob[i] = (uint8_t)rnd();
    int null_out = k % 53 == 0;
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    for (int i = 0; i < 64; i++) o1[i] = ob[i];
    trap_reset(); uint64_t r1 = kotoba_aiueos_rtl8125_identify(TRAP_WINDOW, len, null_out ? 0 : (uint64_t)(uintptr_t)(o1 + 16), olen);
    uint64_t t1 = trap_trace; unsigned a1 = trap_accesses; static uint8_t after[4096]; for (int i = 0; i < 4096; i++) after[i] = trap_regs[i];
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    for (int i = 0; i < 64; i++) o2[i] = ob[i];
    trap_reset(); uint64_t r2 = kotoba_aiueos_rtl8125_identify_native(TRAP_WINDOW, len, null_out ? 0 : (uint64_t)(uintptr_t)(o2 + 16), olen);
    int same = r1 == r2 && t1 == trap_trace && a1 == trap_accesses;
    for (int i = 0; i < 4096; i++) if (after[i] != trap_regs[i]) same = 0;
    for (int i = 0; i < 64; i++) if (o1[i] != o2[i]) same = 0;
    n_cases++; if (r1 == 0) n_zero++;
    if (!same && n_bad++ < 8) { puts_("DIFF "); hex(k, 4); hex(r1, 1); hex(r2, 1); hex(a1, 2); hex(trap_accesses, 2); putc_('\n'); }
  }
  (void)w32;
  puts_("CASES "); hex(n_cases, 4); puts_("ADMITTED "); hex(n_zero, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
