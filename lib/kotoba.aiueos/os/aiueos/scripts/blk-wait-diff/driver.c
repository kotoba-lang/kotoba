/* The block completion wait under a real PIT interrupt (JUN-598): the IRQ0 gate counts ticks, one per halt, and plays
   a scripted device -- on tick irq_at the block interrupt counter moves, on tick used_at the used index becomes the
   scripted one (the target, or past it). old_wait (verbatim) and new_wait (over kotoba/blk-wait.o) run the same
   script from the same state, with MSI-X (halting) and without (pause, nothing moves: the state is what it was); the
   answer, the ticks each consumed, the submitted index and every statistics global must match. */
#include "common.h"
int old_wait(struct virtq_used *, uint8_t *, uint16_t *, uint32_t, uint32_t);
int new_wait(struct virtq_used *, uint8_t *, uint16_t *, uint32_t, uint32_t);
extern uint32_t old_slowest_iters, new_slowest_iters; extern uint16_t old_slow_used, new_slow_used, old_slow_target,
  new_slow_target, old_wait_used, new_wait_used, old_wait_target, new_wait_target;
extern uint64_t old_wait_irq, new_wait_irq; extern int old_wait_overshot, new_wait_overshot;
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
volatile uint64_t aiueos_virtio_blk_irq_count; int blk_msix_active;
static uint8_t page[4096] __attribute__((aligned(4096)));
#define used ((volatile struct virtq_used *)page)
static uint8_t status;
volatile uint64_t ticks, irq_at, used_at, irq_step; volatile uint16_t used_value;
void tick_c(void) {
  ticks++;
  if (ticks == irq_at) aiueos_virtio_blk_irq_count += irq_step;
  if (ticks == used_at) used->index = used_value;
  outb(0x40, 0x3c); outb(0x40, 0x00);                       /* re-arm the one-shot: the next tick only after this one */
  outb(0x20, 0x20);
}
void irq0_stub(void);
__asm__(".globl irq0_stub\nirq0_stub:\n  pushq %rax; pushq %rcx; pushq %rdx; pushq %rsi; pushq %rdi; pushq %r8; pushq %r9; pushq %r10; pushq %r11\n"
        "  cld\n  call tick_c\n  popq %r11; popq %r10; popq %r9; popq %r8; popq %rdi; popq %rsi; popq %rdx; popq %rcx; popq %rax\n"
        "  andq $~0x200, 16(%rsp)\n  iretq\n");   /* return with IF clear: the next tick waits for the next hlt */
struct gate { uint16_t lo, sel; uint8_t ist, attr; uint16_t mid; uint32_t hi, zero; } __attribute__((packed));
static struct gate idt[48] __attribute__((aligned(16)));
static uint64_t seed = 598;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 21; }
static unsigned n_cases, n_done, n_over, n_bad;
struct script { int msix; uint16_t old, start_index, used_value; uint64_t count, ia, ua, step; uint32_t id, length, type, budget,
  slowest; uint8_t st; };
struct outcome { int res, over; uint64_t took, wirq; uint32_t slowest; uint16_t sub, su, stg, wu, wt; };
static void run(int (*fn)(struct virtq_used *, uint8_t *, uint16_t *, uint32_t, uint32_t), const struct script *s,
                uint32_t *slowest, uint16_t *su, uint16_t *stg, uint16_t *wu, uint16_t *wt, uint64_t *wirq, int *over,
                struct outcome *o) {
  *slowest = s->slowest; *su = 0; *stg = 0; *wu = 0; *wt = 0; *wirq = 0; *over = 0;
  blk_msix_active = s->msix; aiueos_virtio_blk_irq_count = s->count; used->index = s->start_index;
  for (int i = 0; i < 4; i++) { used->ring[i].id = 7; used->ring[i].length = 7; }
  used->ring[s->old & 3].id = s->id; used->ring[s->old & 3].length = s->length; status = s->st;
  used_value = s->used_value; irq_step = s->step; ticks = 0; irq_at = s->ia; used_at = s->ua;
  uint16_t sub = s->old;
  o->res = fn((struct virtq_used *)page, &status, &sub, s->type, s->budget);
  o->took = ticks; o->sub = sub; o->slowest = *slowest; o->su = *su; o->stg = *stg; o->wu = *wu; o->wt = *wt; o->wirq = *wirq;
  o->over = *over;
}
void test_main(void) {
  puts_("BLKWAITDIFF\n");
  uint64_t a = (uint64_t)(uintptr_t)irq0_stub;
  idt[32] = (struct gate){(uint16_t)a, 0x08, 0, 0x8e, (uint16_t)(a >> 16), (uint32_t)(a >> 32), 0};
  struct { uint16_t limit; uint64_t base; } __attribute__((packed)) idtr = {sizeof idt - 1, (uint64_t)(uintptr_t)idt};
  __asm__ volatile("lidt %0" :: "m"(idtr));
  outb(0x20, 0x11); outb(0xa0, 0x11); outb(0x21, 32); outb(0xa1, 40); outb(0x21, 4); outb(0xa1, 2);
  outb(0x21, 1); outb(0xa1, 1); outb(0x21, 0xfe); outb(0xa1, 0xff);
  /* PIT channel 0 in mode 0 (one-shot), re-armed by each tick's handler, which returns with IF clear: every halt
     consumes exactly one tick whatever the emulation's timing (see scripts/virtq-wait-diff/driver.c). */
  outb(0x43, 0x30); outb(0x40, 0x3c); outb(0x40, 0x00);   /* 60 counts ~ 20 kHz */
  for (unsigned k = 0; k < 400; k++) {
    struct script s;
    s.msix = k % 4 != 3;
    s.old = (uint16_t)(k % 13 == 0 ? 0xffff : rnd());                     /* sometimes the target wraps to 0 */
    uint16_t target = (uint16_t)(s.old + 1);
    unsigned shape = (unsigned)(rnd() % 8);
    s.start_index = (uint16_t)(shape == 0 ? target : shape == 1 ? target + 1 + rnd() % 0x7fff : shape == 2 ?
                               target + 0x8000 + rnd() % 0x7fff : s.old);     /* there, past it, far behind, behind */
    s.used_value = (uint16_t)(rnd() % 4 == 0 ? target + 1 + rnd() % 3 : target);       /* the device overshoots */
    s.count = rnd() % 4 == 0 ? target + rnd() % 3 : (target > 2 ? target - 1 - rnd() % 2 : 0);
    s.step = 1 + rnd() % 2; s.ia = 1 + rnd() % 6; s.ua = 1 + rnd() % 6;
    if (k % 9 == 0) s.ua = 1000000;                                                     /* never completes */
    if (k % 17 == 0) s.ia = 1000000;                                       /* the interrupt is never counted */
    s.type = (uint32_t)(rnd() % 2); s.id = rnd() % 16 == 0 ? 1 : 0;
    s.length = rnd() % 16 == 0 ? 2 : (s.type == VIRTIO_BLK_T_IN ? 513 : 1); s.st = rnd() % 16 == 0 ? 1 : VIRTIO_BLK_S_OK;
    s.slowest = (uint32_t)(rnd() % 4 == 0 ? rnd() % 8 : 0);
    s.budget = (uint32_t)(k % 3 == 0 ? 1 + rnd() % 5 : 20 + rnd() % 1000);
    if (!s.msix || s.ua == 1000000 || s.ia == 1000000) s.budget = 1 + (uint32_t)(rnd() % 9);
    if (k >= 380 && k < 384) { s.msix = 1; s.ua = 65535 + (k - 380); s.ia = 1; s.used_value = target; s.count = target;
                               s.start_index = s.old; s.id = 0; s.length = s.type == VIRTIO_BLK_T_IN ? 513 : 1;
                               s.st = 0; s.budget = 70000; }        /* completions across the object's 65536 chunk */
    if (k == 384 || k == 385) { s.msix = 1; s.ua = 1000000; s.budget = 65535 + (k - 384) * 2; } /* stalls across it */
    struct outcome o1, o2;
    run(old_wait, &s, &old_slowest_iters, &old_slow_used, &old_slow_target, &old_wait_used, &old_wait_target,
        &old_wait_irq, &old_wait_overshot, &o1);
    run(new_wait, &s, &new_slowest_iters, &new_slow_used, &new_slow_target, &new_wait_used, &new_wait_target,
        &new_wait_irq, &new_wait_overshot, &o2);
    if (k % 50 == 49) { puts_("AT "); hex(k + 1, 3); putc_('\n'); }
    n_cases++; if (o1.res) n_done++; if (o1.over) n_over++;
    if (o1.res != o2.res || o1.took != o2.took || o1.sub != o2.sub || o1.slowest != o2.slowest || o1.su != o2.su ||
        o1.stg != o2.stg || o1.wu != o2.wu || o1.wt != o2.wt || o1.wirq != o2.wirq || o1.over != o2.over) {
      if (n_bad++ < 8) { puts_("WAIT-DIFF "); hex(k, 3); hex(o1.res, 1); hex(o2.res, 1); hex(o1.took, 5); hex(o2.took, 5);
                         hex(o1.slowest, 5); hex(o2.slowest, 5); hex(o1.wu, 4); hex(o2.wu, 4); putc_('\n'); }
    }
  }
  puts_("CASES "); hex(n_cases, 4); puts_("COMPLETED "); hex(n_done, 4); puts_("OVERSHOT "); hex(n_over, 4);
  puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
