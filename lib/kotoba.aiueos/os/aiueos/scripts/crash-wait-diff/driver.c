/* The crash receipt's polled block wait (JUN-598). old_wait (verbatim) and new_wait (over kotoba/blk-wait.o with MSI-X
   off: pause, no halt) run the same script from the same state. Static cases leave the ring as it starts: complete,
   with a wrong element or status, behind (the budget runs out), past the target, the target wrapping to 0. Moving cases
   take one PIT interrupt in the middle of the spin (interrupts enabled around the call; the handler returns with IF
   clear, so there is exactly one), which makes the used index the target or passes it. The answer and the submitted
   index must match. A pass of the target fails both: the C after spinning out its budget, the object at once. */
#include "common.h"
int old_wait(struct crash_backend *, uint32_t, uint32_t); int new_wait(struct crash_backend *, uint32_t, uint32_t);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
volatile uint64_t aiueos_virtio_blk_irq_count;
static uint8_t page[4096] __attribute__((aligned(4096)));
#define used ((volatile struct virtq_used *)page)
static uint8_t status;
volatile uint64_t ticks; volatile uint16_t used_value; volatile int move;
void tick_c(void) {
  ticks++;
  if (move) used->index = used_value;
  outb(0x20, 0x20);
}
void irq0_stub(void);
__asm__(".globl irq0_stub\nirq0_stub:\n  pushq %rax; pushq %rcx; pushq %rdx; pushq %rsi; pushq %rdi; pushq %r8; pushq %r9; pushq %r10; pushq %r11\n"
        "  cld\n  call tick_c\n  popq %r11; popq %r10; popq %r9; popq %r8; popq %rdi; popq %rsi; popq %rdx; popq %rcx; popq %rax\n"
        "  andq $~0x200, 16(%rsp)\n  iretq\n");   /* return with IF clear: one interrupt per call */
struct gate { uint16_t lo, sel; uint8_t ist, attr; uint16_t mid; uint32_t hi, zero; } __attribute__((packed));
static struct gate idt[48] __attribute__((aligned(16)));
static uint64_t seed = 750;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 21; }
static unsigned n_cases, n_done, n_moved, n_bad;
struct script { uint16_t old, start_index, used_value; int moving; uint32_t id, length, type, budget; uint8_t st; };
static void run(int (*fn)(struct crash_backend *, uint32_t, uint32_t), const struct script *s, int *res, uint16_t *sub,
                uint64_t *took) {
  used->index = s->start_index;
  for (int i = 0; i < 4; i++) { used->ring[i].id = 7; used->ring[i].length = 7; }
  used->ring[s->old & 3].id = s->id; used->ring[s->old & 3].length = s->length; status = s->st;
  used_value = s->used_value; move = s->moving; ticks = 0;
  struct crash_backend b = {(struct virtq_used *)page, &status, s->old};
  if (s->moving) { outb(0x43, 0x30); outb(0x40, 0x00); outb(0x40, 0x04); __asm__ volatile("sti"); }   /* ~1 ms */
  *res = fn(&b, s->type, s->budget);
  __asm__ volatile("cli");
  if (s->moving && !ticks) { while (!ticks) __asm__ volatile("sti; hlt; cli"); }         /* the tick, if it came late */
  *sub = b.submitted; *took = ticks;
}
void test_main(void) {
  puts_("CRASHWAITDIFF\n");
  uint64_t a = (uint64_t)(uintptr_t)irq0_stub;
  idt[32] = (struct gate){(uint16_t)a, 0x08, 0, 0x8e, (uint16_t)(a >> 16), (uint32_t)(a >> 32), 0};
  struct { uint16_t limit; uint64_t base; } __attribute__((packed)) idtr = {sizeof idt - 1, (uint64_t)(uintptr_t)idt};
  __asm__ volatile("lidt %0" :: "m"(idtr));
  outb(0x20, 0x11); outb(0xa0, 0x11); outb(0x21, 32); outb(0xa1, 40); outb(0x21, 4); outb(0xa1, 2);
  outb(0x21, 1); outb(0xa1, 1); outb(0x21, 0xfe); outb(0xa1, 0xff);
  for (unsigned k = 0; k < 300; k++) {
    struct script s;
    s.old = (uint16_t)(k % 13 == 0 ? 0xffff : rnd());
    uint16_t target = (uint16_t)(s.old + 1);
    s.moving = k % 3 == 0;
    unsigned shape = (unsigned)(rnd() % 4);
    s.start_index = (uint16_t)(s.moving ? s.old : shape == 0 ? target : shape == 1 ? target + 1 + rnd() % 0x7fff :
                               shape == 2 ? target + 0x8000 + rnd() % 0x7fff : s.old);
    s.used_value = (uint16_t)(rnd() % 4 == 0 ? target + 1 + rnd() % 3 : target);
    s.type = (uint32_t)(rnd() % 2); s.id = rnd() % 12 == 0 ? 1 : 0;
    s.length = rnd() % 12 == 0 ? 2 : (s.type == VIRTIO_BLK_T_IN ? 513 : 1); s.st = rnd() % 12 == 0 ? 1 : VIRTIO_BLK_S_OK;
    s.budget = s.moving ? 50000000U : (uint32_t)(1 + rnd() % 70000);   /* moving: long enough for the tick to land */
    if (k == 150 || k == 151) { s.moving = 0; s.start_index = s.old; s.budget = 65535 + (k - 150) * 2; } /* across a chunk */
    int r1, r2; uint16_t u1, u2; uint64_t t1, t2;
    run(old_wait, &s, &r1, &u1, &t1);
    run(new_wait, &s, &r2, &u2, &t2);
    n_cases++; if (r1) n_done++; if (s.moving) n_moved++;
    if (r1 != r2 || u1 != u2 || t1 != t2) {
      if (n_bad++ < 8) { puts_("WAIT-DIFF "); hex(k, 3); hex(r1, 1); hex(r2, 1); hex(u1, 4); hex(u2, 4); putc_('\n'); }
    }
  }
  puts_("CASES "); hex(n_cases, 4); puts_("COMPLETED "); hex(n_done, 4); puts_("MOVING "); hex(n_moved, 4);
  puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
