/* setup_rng_msix's and setup_blk_msix's MSI-X programming against an emulated device behind the MMIO trap harness
   (JUN-598): the common configuration at the window's start, the MSI-X table at +0x800. The device keeps the queue
   vector it is given, or refuses it (NO_VECTOR, 0xffff) as a device out of vectors does, or answers some other value.
   old (verbatim) and new (over kotoba/msix-entry.o) run from the same register file and must answer the same, make
   the same bus transactions in the same order (reads, writes and their values) and leave the same registers. */
#include "../mmio-trap/trap.h"
#include "common.h"
int old_rng(volatile struct virtio_common_cfg *, struct msix_entry *); int new_rng(volatile struct virtio_common_cfg *, struct msix_entry *);
int old_blk(volatile struct virtio_common_cfg *, struct msix_entry *, uint32_t, uint32_t);
int new_blk(volatile struct virtio_common_cfg *, struct msix_entry *, uint32_t, uint32_t);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 1409;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 13; }
static uint64_t apic;
uint64_t kotoba_aiueos_cpu_apic_id(void) { return apic; }
static int refuse; static uint16_t other;
void trap_model_after_write(unsigned offset) {
  if (offset == 26 || offset == 27) {
    if (refuse == 1) { trap_regs[26] = 0xff; trap_regs[27] = 0xff; }
    if (refuse == 2) { trap_regs[26] = (uint8_t)other; trap_regs[27] = (uint8_t)(other >> 8); }
  }
}
static uint8_t start[4096], after[4096];
void test_main(void) {
  puts_("MSIXENTRYDIFF\n");
  trap_init();
  unsigned n_cases = 0, n_kept = 0, n_bad = 0;
  for (unsigned k = 0; k < 4000; k++) {
    for (int i = 0; i < 4096; i++) start[i] = (uint8_t)rnd();
    apic = rnd() & (k % 4 ? 0xff : 0xfffff);
    unsigned r = (unsigned)(rnd() % 6); refuse = r == 0 ? 1 : r == 1 ? 2 : 0; other = (uint16_t)(2 + rnd() % 3000);
    uint32_t address = (uint32_t)(k % 3 ? 0xfee00000U | (rnd() & 0xff) << 12 : rnd()), data = (uint32_t)(k % 5 ? 35 : rnd());
    int blk = k & 1;
    volatile struct virtio_common_cfg *cfg = (volatile struct virtio_common_cfg *)TRAP_WINDOW;
    struct msix_entry *table = (struct msix_entry *)(TRAP_WINDOW + 0x800);
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    trap_reset(); int r1 = blk ? old_blk(cfg, table, address, data) : old_rng(cfg, table);
    uint64_t t1 = trap_trace; unsigned a1 = trap_accesses; for (int i = 0; i < 4096; i++) after[i] = trap_regs[i];
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    trap_reset(); int r2 = blk ? new_blk(cfg, table, address, data) : new_rng(cfg, table);
    int same = r1 == r2 && t1 == trap_trace && a1 == trap_accesses;
    for (int i = 0; i < 4096; i++) if (after[i] != trap_regs[i]) same = 0;
    n_cases++; if (r1) n_kept++;
    if (!same && n_bad++ < 8) { puts_("MSIX-DIFF "); hex(k, 4); hex(r1, 1); hex(r2, 1); hex(a1, 2); hex(trap_accesses, 2); putc_('\n'); }
  }
  puts_("CASES "); hex(n_cases, 4); puts_("KEPT "); hex(n_kept, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
