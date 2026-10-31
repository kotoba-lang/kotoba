/* rtl8125-program built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object, behind
   the MMIO trap harness (../mmio-trap). Random 4 KiB register files; the window at TRAP_WINDOW, null or negative, length
   4096 or another; revisions -2..6 (0 is the stop phase); transmit and receive descriptor addresses 256-aligned,
   misaligned, zero or negative. The device model drains the transmit FIFO (sets 0xd3 bits 4 and 5) on the write that
   sets the stop bit (0x37 bit 7), or already has it drained, so the stop phase's poll ends on its first read. Both objects
   start from the same registers; the answers, every bus transaction in order (the FNV trace and the count) and the
   registers after are compared. Then the FIFO timeout: a register file in ordinary memory that never drains, so both
   poll until the 300000-read budget or the TSC deadline ends it (whichever comes first depends on the TSC, so the
   number of reads is not compared there); the answers (4) and the registers after are compared. */
#include "../mmio-trap/trap.h"
extern uint64_t kotoba_aiueos_rtl8125_program(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
extern uint64_t kotoba_aiueos_rtl8125_program_native(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 708;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 13; }
static int drain_on_stop;
void trap_model_after_write(unsigned offset) {
  if (drain_on_stop && offset == 0x37 && (trap_regs[0x37] & 0x80)) trap_regs[0xd3] |= 0x30;
}
static uint8_t start[4096], after[4096];
static uint8_t p1[4096] __attribute__((aligned(4096))), p2[4096] __attribute__((aligned(4096)));
static unsigned n_cases, n_zero, n_bad, n_to, n_to_bad;
static uint64_t desc(void) {
  unsigned f = (unsigned)(rnd() % 10);
  return f < 7 ? 0x100000 + (rnd() % 0x10000) * 256 : f == 7 ? 0x100000 + (rnd() % 0x100000) * 4 + 4 : f == 8 ? 0 : (uint64_t)-(int64_t)(256 * (1 + rnd() % 100));
}
void test_main(void) {
  puts_("RTL8125PROGRAMDIFF\n");
  trap_init();
  for (unsigned k = 0; k < 8000; k++) {
    for (int i = 0; i < 4096; i++) start[i] = (uint8_t)rnd();
    unsigned w = (unsigned)(rnd() % 14);
    uint64_t mmio = w < 12 ? TRAP_WINDOW : w == 12 ? 0 : (uint64_t)-(int64_t)(1 + rnd() % 4096);
    uint64_t mlen = rnd() % 8 ? 4096 : rnd() % 2 ? 4095 + rnd() % 3 : rnd() % 20000;
    unsigned r = (unsigned)(rnd() % 10);
    uint64_t rev = r < 3 ? 0 : r < 8 ? 1 + rnd() % 4 : (uint64_t)((int64_t)(rnd() % 9) - 2);
    uint64_t tx = desc(), rx = desc();
    drain_on_stop = 1;
    if (rnd() % 3 == 0) start[0xd3] |= 0x30; else start[0xd3] &= (uint8_t)~0x30;
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    trap_reset(); uint64_t r1 = kotoba_aiueos_rtl8125_program(mmio, mlen, tx, rx, rev);
    uint64_t t1 = trap_trace; unsigned a1 = trap_accesses; for (int i = 0; i < 4096; i++) after[i] = trap_regs[i];
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    trap_reset(); uint64_t r2 = kotoba_aiueos_rtl8125_program_native(mmio, mlen, tx, rx, rev);
    int same = r1 == r2 && t1 == trap_trace && a1 == trap_accesses;
    for (int i = 0; i < 4096; i++) if (after[i] != trap_regs[i]) same = 0;
    n_cases++; if (r1 == 0) n_zero++;
    if (!same && n_bad++ < 8) { puts_("DIFF "); hex(k, 4); hex(rev, 2); hex(r1, 1); hex(r2, 1); hex(a1, 2); hex(trap_accesses, 2); putc_('\n'); }
  }
  for (unsigned k = 0; k < 6; k++) {
    for (int i = 0; i < 4096; i++) p1[i] = p2[i] = (uint8_t)rnd();
    p1[0xd3] &= (uint8_t)~0x30; p2[0xd3] = p1[0xd3];
    if (k & 1) { p1[0xd3] |= 0x10; p2[0xd3] |= 0x10; }
    uint64_t r1 = kotoba_aiueos_rtl8125_program((uint64_t)(uintptr_t)p1, 4096, 0, 0, 0);
    uint64_t r2 = kotoba_aiueos_rtl8125_program_native((uint64_t)(uintptr_t)p2, 4096, 0, 0, 0);
    int same = r1 == 4 && r2 == 4;
    for (int i = 0; i < 4096; i++) if (p1[i] != p2[i]) same = 0;
    n_to++; if (!same && n_to_bad++ < 4) { puts_("TODIFF "); hex(k, 2); hex(r1, 1); hex(r2, 1); putc_('\n'); }
  }
  puts_("TIMEOUTS "); hex(n_to, 2); puts_("TODIFFS "); hex(n_to_bad, 2); putc_('\n');
  if (n_to_bad) n_bad++;
  puts_("CASES "); hex(n_cases, 4); puts_("PROGRAMMED "); hex(n_zero, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
