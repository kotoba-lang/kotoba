/* idt-gate-build built on amu's native object route (JUN-599) against the committed kotoba-compiler/1 object. The
   native export takes OUT's length (the route admits a window only with its own length) and is called with 16; for
   every (handler, selector, ist, attributes) both answer the same and leave the same 24 bytes around the gate: random
   canonical and non-canonical handlers and every refusal boundary. The native object also refuses an out length other
   than 16 with nothing written. */
#include <stdint.h>
extern uint64_t kotoba_aiueos_idt_gate_build(uint64_t handler, uint64_t selector, uint64_t ist, uint64_t attributes, uint64_t out);
extern uint64_t kotoba_aiueos_idt_gate_build_native(uint64_t handler, uint64_t selector, uint64_t ist, uint64_t attributes, uint64_t out, uint64_t out_length);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 599;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed ^ (seed >> 29); }
static uint8_t g1[32], g2[32];
static unsigned n_all, n_built, n_bad, n_len;
static void one(uint64_t h, uint64_t sel, uint64_t ist, uint64_t attr) {
  for (int i = 0; i < 32; i++) g1[i] = g2[i] = 0x5a;
  uint64_t r1 = kotoba_aiueos_idt_gate_build(h, sel, ist, attr, (uint64_t)(uintptr_t)(g1 + 8));
  uint64_t r2 = kotoba_aiueos_idt_gate_build_native(h, sel, ist, attr, (uint64_t)(uintptr_t)(g2 + 8), 16);
  unsigned bad = r1 != r2; for (int i = 0; i < 32; i++) bad += g1[i] != g2[i];
  n_all++; if (r1 == 1) n_built++;
  if (bad && n_bad++ < 10) { puts_("IDT-DIFF "); hex(h, 16); hex(sel, 4); hex(ist, 2); hex(attr, 2); hex(r1, 2); hex(r2, 2); putc_('\n'); }
}
void test_main(void) {
  puts_("IDTGATEDIFF\n");
  static const uint64_t H[] = {0, 1, 0x100000, 0xffffffffull, 0x100000000ull, 0x7fffffffffffull, 0x800000000000ull,
    0xffff800000000000ull, 0xffff7fffffffffffull, 0xffffffffffffffffull, 0x8000000000000000ull};
  static const uint64_t SEL[] = {0, 8, 0x10, 0x28, 0x108}, IST[] = {0, 1, 7}, AT[] = {0x8e, 0x8f, 0xee, 0x0e, 0x18e};
  for (unsigned a = 0; a < 11; a++) for (unsigned b = 0; b < 5; b++) for (unsigned c = 0; c < 3; c++) for (unsigned d = 0; d < 5; d++) one(H[a], SEL[b], IST[c], AT[d]);
  for (unsigned k = 0; k < 20000; k++) {
    uint64_t h = rnd() >> 17; if (k & 1) h = (uint64_t)-(int64_t)h; if (k % 97 == 0) h = rnd();
    one(h, k % 13 ? 8 : SEL[rnd() % 5], k % 11 ? 0 : IST[rnd() % 3], k % 7 ? 0x8e : AT[rnd() % 5]);
  }
  static const uint64_t L[] = {0, 8, 15, 17, 32, 0xffffffffffffffffull};
  for (unsigned i = 0; i < 6; i++) {
    for (int j = 0; j < 32; j++) g2[j] = 0x5a;
    uint64_t r = kotoba_aiueos_idt_gate_build_native(0x100000, 8, 0, 0x8e, (uint64_t)(uintptr_t)(g2 + 8), L[i]);
    unsigned w = 0; for (int j = 0; j < 32; j++) w += g2[j] != 0x5a;
    if (r == 0 && w == 0) n_len++;
  }
  puts_("CASES "); hex(n_all, 8); puts_("BUILT "); hex(n_built, 8); puts_("LENGTH-REFUSED "); hex(n_len, 2); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
