/* The PLC release wait under a real PIT interrupt (JUN-554): the IRQ0 gate is the APIC timer's tick counter, one tick
   per halt (the one-shot PIT of scripts/virtq-wait-diff, re-armed by its handler, which returns with IF clear).
   old_wait (verbatim) and new_wait (over kotoba/tick-wait.o) start from the same counter and release and must stop on
   the same tick. 400 waits: the release already passed or reached, 1..300 ticks away, and 65535 and 65537 ticks away,
   across the object's 65536-round chunk. */
#include <stdint.h>
void old_wait(uint64_t); void new_wait(uint64_t);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
volatile uint64_t aiueos_apic_timer_ticks;
void tick_c(void) {
  aiueos_apic_timer_ticks++;
  outb(0x40, 0x3c); outb(0x40, 0x00);                       /* re-arm the one-shot: the next tick only after this one */
  outb(0x20, 0x20);
}
void irq0_stub(void);
__asm__(".globl irq0_stub\nirq0_stub:\n  pushq %rax; pushq %rcx; pushq %rdx; pushq %rsi; pushq %rdi; pushq %r8; pushq %r9; pushq %r10; pushq %r11\n"
        "  cld\n  call tick_c\n  popq %r11; popq %r10; popq %r9; popq %r8; popq %rdi; popq %rsi; popq %rdx; popq %rcx; popq %rax\n"
        "  andq $~0x200, 16(%rsp)\n  iretq\n");
struct gate { uint16_t lo, sel; uint8_t ist, attr; uint16_t mid; uint32_t hi, zero; } __attribute__((packed));
static struct gate idt[48] __attribute__((aligned(16)));
static uint64_t seed = 125;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 21; }
void test_main(void) {
  puts_("TICKWAITDIFF\n");
  uint64_t a = (uint64_t)(uintptr_t)irq0_stub;
  idt[32] = (struct gate){(uint16_t)a, 0x08, 0, 0x8e, (uint16_t)(a >> 16), (uint32_t)(a >> 32), 0};
  struct { uint16_t limit; uint64_t base; } __attribute__((packed)) idtr = {sizeof idt - 1, (uint64_t)(uintptr_t)idt};
  __asm__ volatile("lidt %0" :: "m"(idtr));
  outb(0x20, 0x11); outb(0xa0, 0x11); outb(0x21, 32); outb(0xa1, 40); outb(0x21, 4); outb(0xa1, 2);
  outb(0x21, 1); outb(0xa1, 1); outb(0x21, 0xfe); outb(0xa1, 0xff);
  outb(0x43, 0x30); outb(0x40, 0x3c); outb(0x40, 0x00);
  unsigned n_cases = 0, n_bad = 0; uint64_t total = 0;
  for (unsigned k = 0; k < 400; k++) {
    uint64_t start = rnd() % 1000000000ull, release;
    unsigned shape = k % 5;
    release = shape == 0 ? start - (rnd() % 3) : shape == 1 ? start : start + 1 + rnd() % 300;
    if (k >= 398) release = start + 65535 + (k - 398) * 2;         /* 65535 and 65537: across the chunk */
    aiueos_apic_timer_ticks = start; old_wait(release); uint64_t t1 = aiueos_apic_timer_ticks;
    aiueos_apic_timer_ticks = start; new_wait(release); uint64_t t2 = aiueos_apic_timer_ticks;
    n_cases++; total += t1 - start;
    if (k % 100 == 99) { puts_("AT "); hex(k + 1, 3); putc_('\n'); }
    if (t1 != t2 && n_bad++ < 8) { puts_("TICK-DIFF "); hex(k, 3); hex(t1 - start, 6); hex(t2 - start, 6); putc_('\n'); }
  }
  puts_("CASES "); hex(n_cases, 4); puts_("TICKS "); hex(total, 8); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
