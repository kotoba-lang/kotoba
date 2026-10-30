#include <stdint.h>
int old_parse(const uint8_t *); void old_state(uint32_t[260]);
int new_parse(const uint8_t *); void new_state(uint32_t[260]);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 83;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 9; }
static unsigned n_cases, n_ok, n_bad;
static uint8_t t[16384] __attribute__((aligned(8)));
static uint32_t at;
static void p32(uint32_t o, uint32_t v) { for (int i = 0; i < 4; i++) t[o + i] = (uint8_t)(v >> (8 * i)); }
static void lapic(uint8_t id, uint32_t flags) { t[at] = 0; t[at + 1] = 8; t[at + 2] = (uint8_t)rnd(); t[at + 3] = id; p32(at + 4, flags); at += 8; }
static void x2apic(uint32_t id, uint32_t flags) { t[at] = 9; t[at + 1] = 16; p32(at + 4, id); p32(at + 8, flags); p32(at + 12, (uint32_t)rnd()); at += 16; }
static void ioapic(uint32_t addr, uint32_t base) { t[at] = 1; t[at + 1] = 12; t[at + 2] = (uint8_t)rnd(); t[at + 3] = 0; p32(at + 4, addr); p32(at + 8, base); at += 12; }
static void iso(uint8_t bus, uint8_t src, uint32_t gsi) { t[at] = 2; t[at + 1] = 10; t[at + 2] = bus; t[at + 3] = src; p32(at + 4, gsi); t[at + 8] = 0; t[at + 9] = 0; at += 10; }
static void other(void) { uint8_t l = (uint8_t)(4 + rnd() % 12); t[at] = (uint8_t)(3 + rnd() % 13); if (t[at] == 9) t[at] = 4; t[at + 1] = l; for (int i = 2; i < l; i++) t[at + i] = (uint8_t)rnd(); at += l; }
static uint32_t flags_pick(void) { static const uint32_t f[] = {0, 1, 2, 3, 4, 5, 0x80000001u}; return f[rnd() % 7]; }
static void build(unsigned k) {
  for (int i = 0; i < 16384; i++) t[i] = 0;
  t[0] = 'A'; t[1] = 'P'; t[2] = 'I'; t[3] = 'C';
  at = 44;
  int many = k % 23 == 0;                                              /* past the 256-processor cap, every one enabled */
  unsigned cpus = (unsigned)(many ? 254 + rnd() % 17 : rnd() % 9);
  for (unsigned c = 0; c < cpus && at < 15000; c++) {
    uint32_t f = many ? 1 : flags_pick();
    if (rnd() % 3) lapic((uint8_t)rnd(), f); else x2apic((uint32_t)rnd(), f);
  }
  unsigned ios = (unsigned)(k % 29 == 0 ? 15 + rnd() % 4 : rnd() % 4);
  for (unsigned i = 0; i < ios; i++) {
    uint32_t addr = (rnd() % 3 == 0) ? 0xfec00000u : (uint32_t)(rnd() & 0xfffff000u);
    if (k % 13 == 1 && i == 0) addr = 0; if (k % 13 == 2) addr |= 8;
    uint32_t base = (uint32_t)(i * 24 + (rnd() % 4 == 0 ? 0 : rnd() % 30));
    if (k % 13 == 3 && i == 1) base = 0;                                /* duplicate of entry 0's base perhaps */
    ioapic(addr, base);
  }
  unsigned isos = (unsigned)(rnd() % 3);
  for (unsigned i = 0; i < isos; i++) iso((uint8_t)(rnd() % 3 == 0 ? 1 : 0), (uint8_t)(rnd() % 3 == 0 ? 1 : 0), (uint32_t)(rnd() % 60));
  for (unsigned i = 0; i < (unsigned)(rnd() % 3); i++) other();
  uint32_t len = at;
  if (k % 11 == 5 && len > 46) len -= (uint32_t)(1 + rnd() % 4);                 /* truncated */
  if (k % 11 == 6 && len > 50) t[44 + 1] = (uint8_t)(rnd() % 8);                  /* a length below the entry's own */
  if (k % 17 == 7 && len > 60) t[(uint32_t)(44 + rnd() % (len - 44))] ^= (uint8_t)(1 + rnd() % 255);
  p32(4, len);
}
void test_main(void) {
  puts_("MADTDIFF\n");
  for (unsigned k = 0; k < 6000; k++) {
    build(k);
    static uint32_t a[260], b[260];
    int r1 = old_parse(t); old_state(a);
    int r2 = new_parse(t); new_state(b);
    int same = r1 == r2; for (int i = 0; i < 260; i++) if (a[i] != b[i]) same = 0;
    n_cases++; if (r1) n_ok++;
    if (!same) { n_bad++; if (n_bad < 8) { puts_("MADT-DIFF "); hex(k, 4); hex(r1, 1); hex(r2, 1); for (int i = 0; i < 4; i++) { hex(a[i], 8); hex(b[i], 8); } putc_('\n'); } }
  }
  puts_("CASES "); hex(n_cases, 4); puts_("ACCEPTED "); hex(n_ok, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
