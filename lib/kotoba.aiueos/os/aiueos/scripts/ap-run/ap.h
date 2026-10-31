/* Run one CPUID-reading object on every processor (JUN-552): the bootstrap processor and each application processor
   the INIT-SIPI-SIPI wakes (entry.S's trampoline) call OLD and NEW REPS times each, one processor at a time, and the
   bootstrap processor prints, per processor, its Local APIC id (the xAPIC ID register, as an oracle) and the two
   answers, and counts the differences. NCPU is the -smp count run.sh boots with. */
#include <stdint.h>
#ifndef NCPU
#error NCPU
#endif
#define REPS 16
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static volatile uint32_t *const lapic = (volatile uint32_t *)0xfee00000ull;
extern char ap_tramp_start[], ap_tramp_end[];
extern volatile uint32_t ap_count;
static volatile uint32_t lock_, done_;
static struct { uint64_t id, old[REPS], new_[REPS]; volatile int seen; } slot[NCPU];
static void run_on(unsigned i) {
  while (__atomic_exchange_n(&lock_, 1, __ATOMIC_ACQUIRE)) __asm__ volatile("pause");
  slot[i].id = lapic[0x20 / 4] >> 24;
  for (int r = 0; r < REPS; r++) { slot[i].old[r] = (uint64_t)OLD(); slot[i].new_[r] = (uint64_t)NEW(); }
  slot[i].seen = 1;
  __atomic_store_n(&lock_, 0, __ATOMIC_RELEASE);
  __atomic_add_fetch(&done_, 1, __ATOMIC_SEQ_CST);
}
void ap_main(uint64_t index) { if (index + 1 < NCPU) run_on((unsigned)index + 1); }
static void delay(unsigned n) { for (volatile unsigned i = 0; i < n; i++) __asm__ volatile("pause"); }
static void icr(uint32_t lo) { lapic[0x310 / 4] = 0; lapic[0x300 / 4] = lo; while (lapic[0x300 / 4] & (1u << 12)) __asm__ volatile("pause"); }
void test_main(void) {
  puts_("CPUDIFF\n");
  run_on(0);
  if (NCPU > 1) {
    for (char *s = ap_tramp_start, *d = (char *)0x8000; s < ap_tramp_end; ) *d++ = *s++;
    icr(0x000c4500); delay(200000); icr(0x000c4608); delay(20000); icr(0x000c4608);
    for (unsigned t = 0; t < 2000000000u && __atomic_load_n(&done_, __ATOMIC_SEQ_CST) < NCPU; t++) __asm__ volatile("pause");
  }
  unsigned n_all = 0, n_nz = 0, n_bad = 0, n_cpu = 0;
  for (unsigned i = 0; i < NCPU; i++) {
    if (!slot[i].seen) continue;
    n_cpu++; puts_("CPU "); hex(slot[i].id, 2); hex(slot[i].old[0], 8); hex(slot[i].new_[0], 8); putc_('\n');
    for (int r = 0; r < REPS; r++) { n_all++; if (slot[i].old[r]) n_nz++; if (slot[i].old[r] != slot[i].new_[r]) n_bad++; }
  }
  puts_("CPUS "); hex(n_cpu, 2); puts_("CASES "); hex(n_all, 4); puts_("NONZERO "); hex(n_nz, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n');
  puts_("DONE\n");
}
