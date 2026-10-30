#include <stdint.h>
int old_run(const uint8_t *, uint32_t, uint32_t, uint32_t, uint64_t[8]);
int new_run(const uint8_t *, uint32_t, uint32_t, uint32_t, uint64_t[8]);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint32_t seed = 53;
static uint32_t rnd(void) { seed = seed * 1103515245u + 12345u; return seed >> 8; }
static uint8_t st[24576], msgs[16384];
static uint32_t sl, ml;
static unsigned n_cases, n_ready, n_app, n_bad;
static void put(uint8_t v) { if (sl < sizeof st) st[sl++] = v; }
static void rec_hdr(uint8_t typ, uint32_t len) { put(typ); put(3); put(3); put((uint8_t)(len >> 8)); put((uint8_t)len); }
/* a handshake message of type t and body length n into msgs */
static void msg(uint8_t t, uint32_t n) {
  if (ml + 4 + n > sizeof msgs) return;
  msgs[ml++] = t; msgs[ml++] = (uint8_t)(n >> 16); msgs[ml++] = (uint8_t)(n >> 8); msgs[ml++] = (uint8_t)n;
  for (uint32_t i = 0; i < n; i++) msgs[ml++] = (uint8_t)rnd();
}
/* msgs[0..ml) as encrypted handshake records of random sizes: header, inner type 0x16 at [5], then the bytes */
static void flush_msgs(uint8_t inner, uint32_t maxfrag) {
  uint32_t at = 0;
  while (at < ml) {
    uint32_t n = 1 + rnd() % maxfrag; if (n > ml - at) n = ml - at;
    rec_hdr(0x17, n + 1); put(inner); for (uint32_t i = 0; i < n; i++) put(msgs[at + i]); at += n;
  }
  ml = 0;
}
static void one_case(unsigned k) {
  sl = 0; ml = 0;
  unsigned shape = k % 9;
  /* ServerHello in a plaintext handshake record (sometimes preceded by a CCS) */
  if (shape != 8) { if (rnd() & 1) { rec_hdr(0x14, 1); put(1); } uint32_t n = 40 + rnd() % 60; rec_hdr(0x16, n); for (uint32_t i = 0; i < n; i++) put((uint8_t)rnd()); }
  /* the encrypted flight: EE, Certificate, CertificateVerify, Finished -- reordered, dropped or corrupted by shape */
  msg(8, rnd() % 20);
  if (shape != 1) msg(11, 8 + rnd() % 900);
  if (shape != 2) msg(15, 70 + rnd() % 10);
  if (shape == 3) msg(20, 32);
  if (shape != 4) msg((shape == 5) ? (uint8_t)rnd() : 20, 32);
  if (shape == 6) { msgs[1] = 0x7f; }                       /* an oversize length */
  msg(4, rnd() % 50);                                     /* NST after Finished */
  flush_msgs((shape == 7) ? (uint8_t)(0x15 + (rnd() & 3)) : 0x16, (k & 1) ? 7 : 2000);
  /* application records: data, NST, alerts, close_notify, unknown inner types, plaintext alerts, unknown record types */
  for (unsigned r = 0; r < 4 + (rnd() & 3); r++) {
    unsigned what = rnd() % 10; uint32_t n = rnd() % 300;
    if (what == 0) { rec_hdr(0x17, 3); put(0x15); put(1); put(0); }
    else if (what == 1) { rec_hdr(0x17, 3); put(0x15); put(2); put((uint8_t)rnd()); }
    else if (what == 2) { rec_hdr(0x17, n + 1); put(0x16); for (uint32_t i = 0; i < n; i++) put((uint8_t)rnd()); }
    else if (what == 3) { rec_hdr(0x15, 2); put(2); put(40); }
    else if (what == 4) { rec_hdr((uint8_t)(0x18 + (rnd() & 7)), 2); put(0); put(0); }
    else if (what == 5) { rec_hdr(0x17, 1); put(0x15); }
    else { rec_hdr(0x17, n + 1); put(0x17); for (uint32_t i = 0; i < n; i++) put((uint8_t)rnd()); }
  }
  if (k % 13 == 0 && sl > 10) st[rnd() % sl] ^= (uint8_t)(1 + (rnd() & 0x7f));   /* a corrupted byte anywhere */
  static const uint32_t chunks[] = {1, 5, 7, 333, 24576};
  for (unsigned c = 0; c < 5; c++)
    for (unsigned s = 0; s < 3; s++) {
      uint64_t a[8], b[8]; uint32_t sc = s == 0 ? 0 : rnd();
      int r1 = old_run(st, sl, chunks[c], sc, a), r2 = new_run(st, sl, chunks[c], sc, b);
      int same = r1 == r2; for (int i = 0; i < 8; i++) if (a[i] != b[i]) same = 0;
      n_cases++; if (a[2] & 2) n_ready++; if ((uint32_t)a[4]) n_app++;
      if (!same) { n_bad++; if (n_bad < 8) { puts_("HS-DIFF "); hex(k, 4); hex(chunks[c], 4); hex(s, 1); for (int i = 0; i < 8; i++) if (a[i] != b[i]) { hex(i, 1); hex(a[i], 16); hex(b[i], 16); break; } putc_('\n'); } }
    }
}
void test_main(void) {
  puts_("HSDIFF\n");
  for (unsigned k = 0; k < 360; k++) one_case(k);
  puts_("CASES "); hex(n_cases, 5); puts_("READY "); hex(n_ready, 5); puts_("APP "); hex(n_app, 5); puts_("DIFFS "); hex(n_bad, 5); putc_('\n'); puts_("DONE\n");
}
