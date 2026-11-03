#include <stdint.h>
#include "device_result.h"
uint32_t old_segment(const struct aiueos_device_result *, const uint8_t[64], const uint8_t[16], uint8_t *);
uint32_t new_segment(const struct aiueos_device_result *, const uint8_t[64], const uint8_t[16], uint8_t *);
extern int64_t kotoba_aiueos_device_result_text(const uint8_t *, uint64_t, uint64_t, uint8_t *, uint64_t);
uint8_t device_boot_id[8];
uint8_t captured[2048]; uint32_t captured_length; uint8_t scripted_signature[64];
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 73;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 7; }
static unsigned n_cases, n_ok, n_bad;
static uint8_t c1[2048], c2[2048], b1[1100], b2[1100];
static uint64_t pick(unsigned k) {
  switch (k % 7) { case 0: return 0; case 1: return rnd() % 10; case 2: return ~0ull; case 3: return 1ull << 63;
    case 4: return 9999999999999999999ull; case 5: return 10000000000000000000ull; default: return rnd(); } }
void test_main(void) {
  puts_("RESULTTEXTDIFF\n");
  static struct aiueos_boot_info boot; static uint8_t mac[6], pub[64], nonce[16];
  for (unsigned k = 0; k < 600; k++) {
    for (int i = 0; i < 6; i++) mac[i] = (uint8_t)rnd();
    for (int i = 0; i < 64; i++) { pub[i] = (uint8_t)rnd(); scripted_signature[i] = (uint8_t)rnd(); }
    for (int i = 0; i < 16; i++) nonce[i] = (uint8_t)rnd();
    for (int i = 0; i < 8; i++) device_boot_id[i] = (uint8_t)rnd();
    for (int i = 0; i < 32; i++) boot.model_sha256[i] = (uint8_t)rnd();
    if (k % 50 == 1) { for (int i = 0; i < 6; i++) mac[i] = 0; for (int i = 0; i < 64; i++) pub[i] = 0xff; }
    boot.model_load_cycles = pick(rnd()); boot.tsc_hz = pick(rnd());
    struct aiueos_device_result r = {&boot, mac, (uint32_t)pick(rnd()), (uint32_t)pick(rnd()), (uint32_t)pick(rnd()),
      (uint32_t)pick(rnd()), pick(rnd()), pick(rnd()), pick(rnd()), (uint32_t)pick(rnd()), (uint32_t)pick(rnd())};
    if (k % 3 == 0) { r.token = (uint32_t)rnd(); r.generated_tokens = 8; r.decode_tokens = 7; r.vector_bits = 256; r.worker_threads = 2; }
    uint32_t l1, l2, n1, n2; int same;
    for (int i = 0; i < 1100; i++) b1[i] = b2[i] = 0x5a;
    captured_length = 0; l1 = old_segment(&r, pub, nonce, b1); n1 = captured_length;
    for (uint32_t i = 0; i < n1; i++) c1[i] = captured[i];
    captured_length = 0; l2 = new_segment(&r, pub, nonce, b2); n2 = captured_length;
    for (uint32_t i = 0; i < n2; i++) c2[i] = captured[i];
    same = l1 == l2 && n1 == n2;
    for (uint32_t i = 0; same && i < n1; i++) if (c1[i] != c2[i]) same = 0;
    for (int i = 0; same && i < 1100; i++) if (b1[i] != b2[i]) same = 0;
    n_cases++; if (l1) n_ok++;
    if (!same) { n_bad++; if (n_bad < 6) { puts_("RT-DIFF "); hex(k, 4); hex(l1, 4); hex(l2, 4); hex(n1, 4); hex(n2, 4); putc_('\n'); } }
  }
  /* the object at every capacity up to its text: 0 below the length (the C's bounded_buffer refused), the length from it */
  {
    static uint8_t rec[288], o[1024];
    for (int i = 0; i < 288; i++) rec[i] = (uint8_t)rnd();
    for (uint64_t mode = 0; mode < 2; mode++) {
      int64_t full = kotoba_aiueos_device_result_text(rec, 288, mode, o, 1024);
      for (uint64_t cap = 0; cap <= 700; cap++) {
        int64_t r = kotoba_aiueos_device_result_text(rec, 288, mode, o, cap);
        n_cases++;
        if (r != ((int64_t)cap >= full ? full : 0)) n_bad++;
      }
      n_cases++; if (full <= 0) n_bad++;
    }
    n_cases += 3;
    if (kotoba_aiueos_device_result_text(rec, 287, 0, o, 1024)) n_bad++;
    if (kotoba_aiueos_device_result_text(rec, 288, 2, o, 1024)) n_bad++;
    if (kotoba_aiueos_device_result_text(rec, 288, 0, o, 16385)) n_bad++;
  }
  puts_("CASES "); hex(n_cases, 4); puts_("SENT "); hex(n_ok, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
