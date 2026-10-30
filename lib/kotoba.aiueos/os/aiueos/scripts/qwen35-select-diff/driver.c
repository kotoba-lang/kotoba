#include <stdint.h>
struct qwen35_token_choice { uint32_t token; uint32_t second_token; float logit; float second_logit;
                             uint64_t cycles; uint32_t failed_layer; uint32_t failure_stage; };
int old_select_view(const float *, uint32_t, uint32_t, struct qwen35_token_choice *);
int new_select_view(const float *, uint32_t, uint32_t, struct qwen35_token_choice *);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 554;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 11; }
static float bf(uint32_t b) { union { uint32_t u; float f; } c; c.u = b; return c.f; }
static uint32_t fb(float f) { union { uint32_t u; float f; } c; c.f = f; return c.u; }
#define CAP 17408
static float L[CAP];
static unsigned n_cases, n_fail, n_diffs;
static const uint32_t SPECIAL[] = {0, 0x80000000u, 0x7f800000u, 0xff800000u, 0x7fc00000u, 0xffc00001u, 0x7f800001u,
  0xff7fffffu, 0x7f7fffffu, 0x00000001u, 0x80000001u, 0x3f800000u, 0xbf800000u};
static uint32_t pick(unsigned mode) {
  uint64_t r = rnd();
  switch (mode) {
  case 0: return (uint32_t)r & 0xff7fffffu;                         /* finite-ish random bits, no inf/NaN exponent most */
  case 1: return fb((float)(int)(r % 9) - 4.0f);                    /* many ties */
  case 2: return fb(bf(0x3f800000u + (uint32_t)(r % 64)) * ((r & 64) ? -1.0f : 1.0f)); /* near-equal */
  default: return (r % 50 == 0) ? SPECIAL[r % 13] : fb((float)(int64_t)(r % 2001) / 7.0f - 140.0f);
  }
}
static void compare(uint32_t count, uint32_t first, struct qwen35_token_choice start, unsigned tag) {
  struct qwen35_token_choice a = start, b = start;
  int ra = old_select_view(L, first, count, &a), rb = new_select_view(L, first, count, &b);
  n_cases++; if (!ra) n_fail++;
  if (ra != rb || a.token != b.token || a.second_token != b.second_token || fb(a.logit) != fb(b.logit) ||
      fb(a.second_logit) != fb(b.second_logit)) {
    if (n_diffs++ < 6) { puts_("SEL-DIFF "); hex(tag, 5); hex(count, 5); hex(ra, 1); hex(rb, 1); hex(a.token, 8); hex(b.token, 8);
                         hex(a.second_token, 8); hex(b.second_token, 8); putc_('\n'); }
  }
}
void test_main(void) {
  puts_("QWEN35SELECTDIFF\n");
  const uint32_t counts[] = {1, 2, 3, 4095, 4096, 4097, 8192, 8193, 12289, 17408};
  for (unsigned k = 0; k < 400; k++) {
    uint32_t count = k < 40 ? counts[k % 10] : 1 + (uint32_t)(rnd() % CAP);
    unsigned mode = k % 4;
    for (uint32_t i = 0; i < count; i++) L[i] = bf(pick(mode));
    if (k % 5 == 3) L[rnd() % count] = bf(SPECIAL[2 + rnd() % 5]);     /* one inf or NaN somewhere */
    struct qwen35_token_choice init = {UINT32_MAX, UINT32_MAX, -3.402823466e+38f, -3.402823466e+38f, 0, 0, 0};
    uint32_t first = (uint32_t)(rnd() % 248320);
    compare(count, first, init, k * 4);
    struct qwen35_token_choice carried = {(uint32_t)rnd(), (uint32_t)rnd(), bf(pick(3) & 0xff7fffffu), 0, 0, 0, 0};
    carried.second_logit = carried.logit - 1.0f;
    compare(count, first, carried, k * 4 + 1);
    struct qwen35_token_choice equal = {7, 9, L[count / 2], L[count / 2], 0, 0, 0};
    compare(count, first, equal, k * 4 + 2);
  }
  puts_("CASES "); hex(n_cases, 4); puts_("NONFINITE "); hex(n_fail, 4); puts_("DIFFS "); hex(n_diffs, 4); putc_('\n'); puts_("DONE\n");
}
