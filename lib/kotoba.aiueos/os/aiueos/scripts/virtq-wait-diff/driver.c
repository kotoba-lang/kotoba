/* The RNG completion wait under a real PIT interrupt (JUN-598): the IRQ0 gate counts ticks, one per halt, and plays a
   scripted device -- on tick irq_at the RNG interrupt counter moves, on tick used_at the used index becomes the
   wanted one. old_wait (verbatim) and new_wait (over kotoba/virtq-wait.o) run the same script from the same state;
   the answer and the ticks each consumed must match. */
#include <stdint.h>
int old_wait(void *, uint64_t, uint16_t, uint32_t); int new_wait(void *, uint64_t, uint16_t, uint32_t);
int64_t kotoba_aiueos_virtq_used_index(uint64_t used, uint64_t used_length) {
  return *(volatile uint16_t *)(uintptr_t)(used + 2) + 0 * (int64_t)used_length;
}
int64_t kotoba_aiueos_virtq_used_elem(uint64_t used, uint64_t used_length, uint64_t slot) { (void)used; (void)used_length; (void)slot; return 32; }
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
volatile uint64_t aiueos_virtio_rng_irq_count;
static uint8_t used[4096] __attribute__((aligned(4096)));
volatile uint64_t ticks, irq_at, used_at; volatile uint16_t want_index;
void tick_c(void) {
  ticks++;
  if (ticks == irq_at) aiueos_virtio_rng_irq_count++;
  if (ticks == used_at) *(volatile uint16_t *)(used + 2) = want_index;
  outb(0x40, 0x2c); outb(0x40, 0x01);                       /* re-arm the one-shot: the next tick only after this one */
  outb(0x20, 0x20);
}
void irq0_stub(void);
__asm__(".globl irq0_stub\nirq0_stub:\n  pushq %rax; pushq %rcx; pushq %rdx; pushq %rsi; pushq %rdi; pushq %r8; pushq %r9; pushq %r10; pushq %r11\n"
        "  cld\n  call tick_c\n  popq %r11; popq %r10; popq %r9; popq %r8; popq %rdi; popq %rsi; popq %rdx; popq %rcx; popq %rax\n"
        "  andq $~0x200, 16(%rsp)\n  iretq\n");   /* return with IF clear: the next tick waits for the next hlt */
struct gate { uint16_t lo, sel; uint8_t ist, attr; uint16_t mid; uint32_t hi, zero; } __attribute__((packed));
static struct gate idt[48] __attribute__((aligned(16)));
static uint64_t seed = 1362;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 21; }
static unsigned n_cases, n_done, n_bad;
static void run(int (*fn)(void *, uint64_t, uint16_t, uint32_t), uint64_t start_count, uint16_t start_index, uint64_t before,
                uint16_t want, uint64_t ia, uint64_t ua, uint32_t budget, int *res, uint64_t *took) {
  aiueos_virtio_rng_irq_count = start_count; *(volatile uint16_t *)(used + 2) = start_index;
  want_index = want; ticks = 0; irq_at = ia; used_at = ua;
  *res = fn(used, before, want, budget); *took = ticks;
}
void test_main(void) {
  puts_("VIRTQWAITDIFF\n");
  uint64_t a = (uint64_t)(uintptr_t)irq0_stub;
  idt[32] = (struct gate){(uint16_t)a, 0x08, 0, 0x8e, (uint16_t)(a >> 16), (uint32_t)(a >> 32), 0};
  struct { uint16_t limit; uint64_t base; } __attribute__((packed)) idtr = {sizeof idt - 1, (uint64_t)(uintptr_t)idt};
  __asm__ volatile("lidt %0" :: "m"(idtr));
  outb(0x20, 0x11); outb(0xa0, 0x11); outb(0x21, 32); outb(0xa1, 40); outb(0x21, 4); outb(0xa1, 2);
  outb(0x21, 1); outb(0xa1, 1); outb(0x21, 0xfe); outb(0xa1, 0xff);
  /* PIT channel 0 in mode 0 (one-shot), re-armed by each tick's handler, which returns with RFLAGS.IF clear (so the
     instant between the hlt's wake and the cli after it cannot take a second tick): at most one interrupt is ever
     pending and it is taken only at a hlt, so every halt consumes exactly one tick whatever the emulation's timing (a periodic PIT under TCG catches up lost periods
     back to back, which made the tick a scripted event lands on depend on host speed). 300 counts ~ 4 kHz. */
  outb(0x43, 0x30); outb(0x40, 0x2c); outb(0x40, 0x01);
  for (unsigned k = 0; k < 300; k++) {
    uint64_t before = rnd() % 1000, start = k % 7 == 0 ? before + 1 : before;   /* sometimes the interrupt already came */
    uint16_t want = (uint16_t)rnd(), start_index = (uint16_t)(k % 5 == 0 ? want : want - 1);
    uint64_t ia = 1 + rnd() % 6, ua = 1 + rnd() % 6; if (k % 11 == 0) ua = 1000000;            /* never completes */
    uint32_t budget = (uint32_t)(k % 3 == 0 ? 1 + rnd() % 5 : 20 + rnd() % 70000);          /* across a 65536 boundary */
    if (ua == 1000000) budget = 1 + (uint32_t)(rnd() % 9);                                    /* a stall runs its budget out */
    if (k == 150 || k == 151) { ua = 1000000; budget = 65535 + (k - 150) * 2; }               /* stalls across the boundary */
    int r1, r2; uint64_t t1, t2;
    run(old_wait, start, start_index, before, want, ia, ua, budget, &r1, &t1);
    run(new_wait, start, start_index, before, want, ia, ua, budget, &r2, &t2);
    n_cases++; if (r1) n_done++;
    if (r1 != r2 || t1 != t2) { if (n_bad++ < 8) { puts_("WAIT-DIFF "); hex(k, 3); hex(r1, 1); hex(r2, 1); hex(t1, 5); hex(t2, 5); putc_('\n'); } }
  }
  puts_("CASES "); hex(n_cases, 4); puts_("COMPLETED "); hex(n_done, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
