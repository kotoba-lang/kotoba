#include <stdint.h>
uint32_t old_cid_body(const uint8_t *, uint32_t); int64_t kotoba_aiueos_http_cid_body(uint64_t, uint64_t);
int old_http_success(const uint8_t *, uint32_t); int new_http_success(const uint8_t *, uint32_t);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 200;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 21; }
static uint8_t a[4096];
static unsigned n_cases, n_body, n_ok, n_bad;
static void compare(uint32_t n, unsigned tag) {
  uint32_t b1 = old_cid_body(a, n), b2 = (uint32_t)kotoba_aiueos_http_cid_body((uint64_t)(uintptr_t)a, n);
  int s1 = old_http_success(a, n), s2 = new_http_success(a, n);
  n_cases++; if (b1) n_body++; if (s1) n_ok++;
  if (b1 != b2 || s1 != s2) { if (n_bad++ < 8) { puts_("HTTP-DIFF "); hex(tag, 5); hex(n, 3); hex(b1, 3); hex(b2, 3); hex(s1, 1); hex(s2, 1); putc_('\n'); } }
}
static uint32_t put(uint32_t at, const char *s) { while (*s && at < 4096) a[at++] = (uint8_t)*s++; return at; }
void test_main(void) {
  puts_("HTTPHEADDIFF\n");
  const char *status[] = {"HTTP/1.1 200 OK", "HTTP/1.0 200 OK", "HTTP/1.1 204 No Content", "HTTP/1.1 299 X", "HTTP/1.1 2a0 X",
                          "HTTP/1.1 301 Moved", "HTTP/1.1 404 Not Found", "HTTP/2 200", "HTTPS1.1 200 OK", "http/1.1 200 OK",
                          "HTTP/1.1 20", "HTTP/1.1 200"};
  for (unsigned k = 0; k < 3000; k++) {
    for (int i = 0; i < 4096; i++) a[i] = (uint8_t)rnd();
    uint32_t at = put(0, status[k % 12]);
    unsigned headers = (unsigned)(rnd() % 4);
    for (unsigned h = 0; h < headers; h++) { at = put(at, "\r\nX-H: "); at = put(at, k % 2 ? "v" : "\r"); }
    if (k % 7 != 3) at = put(at, "\r\n\r\n"); else at = put(at, "\r\n\n");
    uint32_t body = (uint32_t)(rnd() % (k % 5 ? 64 : 3000));
    uint32_t n = at + body > 4096 ? 4096 : at + body;
    compare(n, k * 8);
    compare(at, k * 8 + 1);                                         /* no body */
    if (at > 1) compare(at - 1 - (uint32_t)(rnd() % 3 < at - 1 ? rnd() % 3 : 0), k * 8 + 2);   /* terminator cut */
    for (uint32_t c = 0; c < 12 && c < n; c++) { uint8_t s = a[c]; a[c] ^= (uint8_t)(1 + rnd() % 255); compare(n, k * 8 + 3); a[c] = s; }
    for (uint32_t c = 0; c < 13; c++) compare(c, k * 8 + 4);         /* every length under 13 */
  }
  for (unsigned k = 0; k < 2000; k++) { uint32_t n = (uint32_t)(rnd() % 4097); for (uint32_t i = 0; i < n; i++) a[i] = (uint8_t)(rnd() % 4 == 0 ? (rnd() & 1 ? 13 : 10) : rnd()); compare(n, 900000 + k); }
  puts_("CASES "); hex(n_cases, 5); puts_("BODY "); hex(n_body, 4); puts_("SUCCESS "); hex(n_ok, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
