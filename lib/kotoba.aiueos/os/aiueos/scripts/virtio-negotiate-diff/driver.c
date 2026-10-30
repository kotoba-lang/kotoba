/* negotiate against an emulated virtio device behind the MMIO trap harness: device_feature reads the feature word the
   last select chose, status 0 resets the device, and a device that refuses the features clears FEATURES_OK. JUN-598. */
#include "../mmio-trap/trap.h"
struct virtio_common_cfg;
int old_negotiate(volatile struct virtio_common_cfg *); int new_negotiate(volatile struct virtio_common_cfg *);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 1510;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 13; }
static uint32_t feature[2]; static int refuse, ignore_reset;
static uint32_t r32(unsigned o) { return (uint32_t)trap_regs[o] | (uint32_t)trap_regs[o + 1] << 8 | (uint32_t)trap_regs[o + 2] << 16 | (uint32_t)trap_regs[o + 3] << 24; }
static void w32(unsigned o, uint32_t v) { for (int i = 0; i < 4; i++) trap_regs[o + i] = (uint8_t)(v >> (8 * i)); }
void trap_model_after_write(unsigned offset) {
  if (offset < 4) w32(4, feature[r32(0) & 1]);                    /* device_feature_select */
  if (offset == 20) {
    if (trap_regs[20] == 0 && !ignore_reset) for (int i = 0; i < 56; i++) if (i != 20) trap_regs[i] = 0;
    if (refuse && (trap_regs[20] & 8)) trap_regs[20] &= (uint8_t)~8;
  }
}
static uint8_t start[4096];
static unsigned n_cases, n_ok, n_bad;
void test_main(void) {
  puts_("VIRTIONEGOTIATEDIFF\n");
  trap_init();
  for (unsigned k = 0; k < 4000; k++) {
    for (int i = 0; i < 4096; i++) start[i] = (uint8_t)rnd();
    feature[0] = (uint32_t)rnd(); feature[1] = (uint32_t)rnd() | (k % 3 ? 1u : 0u);
    if (k % 3 == 0) feature[1] &= ~1u;
    refuse = k % 5 == 0; ignore_reset = k % 7 == 0;
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    trap_reset(); int r1 = old_negotiate((volatile struct virtio_common_cfg *)TRAP_WINDOW);
    uint64_t t1 = trap_trace; unsigned a1 = trap_accesses; uint8_t after[64]; for (int i = 0; i < 64; i++) after[i] = trap_regs[i];
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    trap_reset(); int r2 = new_negotiate((volatile struct virtio_common_cfg *)TRAP_WINDOW);
    int same = r1 == r2 && t1 == trap_trace && a1 == trap_accesses;
    for (int i = 0; i < 64; i++) if (after[i] != trap_regs[i]) same = 0;
    n_cases++; if (r1) n_ok++;
    if (!same && n_bad++ < 8) { puts_("NEG-DIFF "); hex(k, 4); hex(r1, 1); hex(r2, 1); hex(a1, 2); hex(trap_accesses, 2); putc_('\n'); }
  }
  puts_("CASES "); hex(n_cases, 4); puts_("NEGOTIATED "); hex(n_ok, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
