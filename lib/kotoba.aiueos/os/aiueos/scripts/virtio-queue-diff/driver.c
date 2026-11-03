/* prepare_queue_index against an emulated virtio device behind the MMIO trap harness: four queues, each with its own
   maximum size, enable bit, notify offset and ring addresses; writing queue_select shows the selected queue's registers,
   writes to them update that queue. JUN-598. */
#include "../mmio-trap/trap.h"
struct virtio_pci_cap { uint8_t bar; uint32_t offset, length, notify_multiplier; };
struct virtio_caps { struct virtio_pci_cap common, notify, device; int have_common, have_notify, have_device; uint8_t msix_pointer; };
struct virtio_common_cfg; struct virtq_desc; struct virtq_avail; struct virtq_used;
volatile uint16_t *old_prepare_queue_index(volatile struct virtio_common_cfg *, const struct virtio_caps *, uint64_t, uint16_t, uint16_t,
                                           struct virtq_desc *, struct virtq_avail *, struct virtq_used *);
volatile uint16_t *new_prepare_queue_index(volatile struct virtio_common_cfg *, const struct virtio_caps *, uint64_t, uint16_t, uint16_t,
                                           struct virtq_desc *, struct virtq_avail *, struct virtq_used *);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 1522;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 11; }
struct queue { uint16_t max, size, enable, notify_off; uint64_t desc, driver, device; };
static struct queue q[4], q0[4];
static unsigned selected;
static uint16_t r16(unsigned o) { return (uint16_t)(trap_regs[o] | trap_regs[o + 1] << 8); }
static uint64_t r64(unsigned o) { uint64_t v = 0; for (int i = 7; i >= 0; i--) v = v << 8 | trap_regs[o + i]; return v; }
static void w16(unsigned o, uint16_t v) { trap_regs[o] = (uint8_t)v; trap_regs[o + 1] = (uint8_t)(v >> 8); }
static void w64(unsigned o, uint64_t v) { for (int i = 0; i < 8; i++) trap_regs[o + i] = (uint8_t)(v >> (8 * i)); }
static void show(void) {
  struct queue *x = selected < 4 ? &q[selected] : 0;
  w16(24, x ? x->size : 0); w16(28, x ? x->enable : 0); w16(30, x ? x->notify_off : 0);
  w64(32, x ? x->desc : 0); w64(40, x ? x->driver : 0); w64(48, x ? x->device : 0);
}
void trap_model_after_write(unsigned offset) {
  if (offset >= 22 && offset < 24) { selected = r16(22); show(); return; }
  if (selected >= 4) { show(); return; }
  struct queue *x = &q[selected];
  if (offset >= 24 && offset < 26) { uint16_t v = r16(24); x->size = v > x->max ? x->max : v; }   /* a device clamps */
  if (offset >= 28 && offset < 30) x->enable = r16(28) ? 1 : 0;
  if (offset >= 32 && offset < 40) x->desc = r64(32);
  if (offset >= 40 && offset < 48) x->driver = r64(40);
  if (offset >= 48 && offset < 56) x->device = r64(48);
  show();
}
static uint8_t start[4096];
static unsigned n_cases, n_ok, n_bad;
void test_main(void) {
  puts_("VIRTIOQUEUEDIFF\n");
  trap_init();
  for (unsigned k = 0; k < 6000; k++) {
    for (int i = 0; i < 4096; i++) start[i] = (uint8_t)rnd();
    for (int i = 0; i < 4; i++) {
      q0[i].max = (uint16_t)(k % 4 == 0 ? rnd() : 1u << (rnd() % 10)); q0[i].size = q0[i].max;
      q0[i].enable = (uint16_t)(rnd() % 5 == 0); q0[i].notify_off = (uint16_t)(k % 6 == 0 ? rnd() : rnd() % 8);
      q0[i].desc = rnd(); q0[i].driver = rnd(); q0[i].device = rnd();
    }
    struct virtio_caps caps = {0};
    caps.notify.notify_multiplier = (uint32_t)(k % 5 == 0 ? rnd() : 4u << (rnd() % 3));
    caps.notify.length = (uint32_t)(k % 7 == 0 ? rnd() % 64 : 0x1000);
    uint16_t index = (uint16_t)(k % 9 == 0 ? rnd() % 6 : rnd() % 2), size = (uint16_t)(k % 3 == 0 ? rnd() % 2048 : 1u << (rnd() % 9));
    uint64_t base = rnd() << 12;
    struct virtq_desc *d = (void *)(uintptr_t)(rnd() << 12); struct virtq_avail *av = (void *)(uintptr_t)(rnd() << 12);
    struct virtq_used *u = (void *)(uintptr_t)(rnd() << 12);
    volatile uint16_t *p1, *p2; uint64_t t1; unsigned a1; struct queue after[4]; uint8_t regs1[64];
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    for (int i = 0; i < 4; i++) q[i] = q0[i]; selected = 99;
    trap_reset(); p1 = old_prepare_queue_index((void *)TRAP_WINDOW, &caps, base, index, size, d, av, u);
    t1 = trap_trace; a1 = trap_accesses; for (int i = 0; i < 4; i++) after[i] = q[i]; for (int i = 0; i < 64; i++) regs1[i] = trap_regs[i];
    for (int i = 0; i < 4096; i++) trap_regs[i] = start[i];
    for (int i = 0; i < 4; i++) q[i] = q0[i]; selected = 99;
    trap_reset(); p2 = new_prepare_queue_index((void *)TRAP_WINDOW, &caps, base, index, size, d, av, u);
    int same = p1 == p2 && t1 == trap_trace && a1 == trap_accesses;
    for (int i = 0; i < 64; i++) if (regs1[i] != trap_regs[i]) same = 0;
    for (int i = 0; i < 4; i++) { const uint8_t *x = (const uint8_t *)&after[i], *y = (const uint8_t *)&q[i]; for (unsigned j = 0; j < sizeof q[i]; j++) if (x[j] != y[j]) same = 0; }
    n_cases++; if (p1) n_ok++;
    if (!same && n_bad++ < 8) { puts_("QUEUE-DIFF "); hex(k, 4); hex((uint64_t)(uintptr_t)p1, 12); hex((uint64_t)(uintptr_t)p2, 12); hex(a1, 2); hex(trap_accesses, 2); putc_('\n'); }
  }
  puts_("CASES "); hex(n_cases, 4); puts_("PROGRAMMED "); hex(n_ok, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
