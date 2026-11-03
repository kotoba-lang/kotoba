#include <stdint.h>
int old_read_bar(uint8_t, uint8_t, uint8_t, uint8_t, uint64_t *); int new_read_bar(uint8_t, uint8_t, uint8_t, uint8_t, uint64_t *);
int old_bar_extent(uint8_t, uint8_t, uint8_t, uint8_t, uint64_t *, uint64_t *); int new_bar_extent(uint8_t, uint8_t, uint8_t, uint8_t, uint64_t *, uint64_t *);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 1305;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 7; }
/* An emulated function: 64 config words; each BAR word keeps its read-only low bits and a size mask, so writing all
   ones reads back the mask as hardware does. trace hashes every access. */
static uint32_t word[64], ro[64], mask[64]; static uint64_t trace;
static void mix(uint64_t v) { trace = (trace ^ v) * 1099511628211ull; }
uint32_t config_read(uint8_t bus, uint8_t dev, uint8_t fn, uint8_t off) {
  (void)bus; (void)dev; (void)fn; uint32_t v = word[(off & 252) / 4]; mix(0x100000000ull | off); mix(v); return v;
}
void config_write(uint8_t bus, uint8_t dev, uint8_t fn, uint8_t off, uint32_t value) {
  (void)bus; (void)dev; (void)fn; unsigned i = (off & 252) / 4; mix(0x200000000ull | off); mix(value);
  word[i] = (value & mask[i]) | ro[i];
}
static uint32_t sw[64], sro[64], smask[64];
static void save(void) { for (int i = 0; i < 64; i++) { sw[i] = word[i]; sro[i] = ro[i]; smask[i] = mask[i]; } }
static void restore(void) { for (int i = 0; i < 64; i++) { word[i] = sw[i]; ro[i] = sro[i]; mask[i] = smask[i]; } }
static unsigned n_cases, n_ok, n_bad;
static void device(unsigned k) {
  for (int i = 0; i < 64; i++) { word[i] = (uint32_t)rnd(); ro[i] = 0; mask[i] = 0xffffffffu; }
  for (int bar = 0; bar < 6; bar++) {
    unsigned i = 4 + (unsigned)bar, kind = (unsigned)(rnd() % 8);
    uint64_t size = 1ull << (4 + rnd() % (kind == 2 ? 44 : 27)), base = (rnd() << 12) & ~(size - 1);
    if (kind < 3) {                                   /* 32-bit memory BAR */
      ro[i] = (uint32_t)(rnd() & 8); mask[i] = (uint32_t)~(size - 1) & ~0xfu;
      word[i] = ((uint32_t)base & mask[i]) | ro[i];
      if (k % 9 == 0) word[i] = ro[i];                 /* base 0 */
      if (k % 13 == 0) word[i] = 0xfffffff0u | ro[i];
    } else if (kind < 5 && bar < 5) {                 /* 64-bit pair */
      ro[i] = 4 | (uint32_t)(rnd() & 8); mask[i] = (uint32_t)~(size - 1) & ~0xfu; mask[i + 1] = (uint32_t)(~(size - 1) >> 32);
      word[i] = ((uint32_t)base & mask[i]) | ro[i]; word[i + 1] = (uint32_t)(base >> 32) & mask[i + 1]; bar++;
    } else if (kind == 5) { ro[i] = 1; mask[i] = ~0xffu; }        /* I/O BAR */
    else if (kind == 6) { ro[i] = 2; }                              /* reserved type 1 */
    else { ro[i] = 6; }                                             /* reserved type 3 */
  }
  word[1] = (uint32_t)rnd() & 0xffff0007u;
}
void test_main(void) {
  puts_("PCIBARDIFF\n");
  for (unsigned k = 0; k < 8000; k++) {
    device(k); save();
    for (unsigned index = 0; index < 8; index++) {
      uint64_t b1 = 0x77, b2 = 0x77, l1 = 0x77, l2 = 0x77; uint64_t t1, t2;
      restore(); trace = 14695981039346656037ull; int r1 = old_read_bar(0, 2, 0, (uint8_t)index, &b1); t1 = trace;
      restore(); trace = 14695981039346656037ull; int r2 = new_read_bar(0, 2, 0, (uint8_t)index, &b2); t2 = trace;
      int same = r1 == r2 && b1 == b2 && t1 == t2;
      restore(); b1 = b2 = 0x77; trace = 14695981039346656037ull; int e1 = old_bar_extent(0, 2, 0, (uint8_t)index, &b1, &l1); t1 = trace;
      uint32_t after1[64]; for (int i = 0; i < 64; i++) after1[i] = word[i];
      restore(); trace = 14695981039346656037ull; int e2 = new_bar_extent(0, 2, 0, (uint8_t)index, &b2, &l2); t2 = trace;
      same = same && e1 == e2 && b1 == b2 && l1 == l2 && t1 == t2;
      for (int i = 0; i < 64; i++) if (after1[i] != word[i]) same = 0;
      n_cases++; if (r1 || e1) n_ok++;
      if (!same && n_bad++ < 8) { puts_("BAR-DIFF "); hex(k, 4); hex(index, 1); hex(r1, 1); hex(r2, 1); hex(e1, 1); hex(e2, 1); putc_('\n'); }
    }
  }
  puts_("CASES "); hex(n_cases, 5); puts_("ADMITTED "); hex(n_ok, 5); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
