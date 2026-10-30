/* Differential driver for kernel/tls_aes_gcm.c versus kotoba/tls-aes-gcm.o (JUN-556): every case prints the return values
   and FNV-1a digests of every output byte, so the C build and the Kotoba build can be compared line for line. */
#include <stdint.h>
int aiueos_aes128_gcm_encrypt(const uint8_t *, const uint8_t *, const uint8_t *, uint32_t, const uint8_t *, uint32_t, uint8_t *, uint8_t *);
int aiueos_aes128_gcm_decrypt(const uint8_t *, const uint8_t *, const uint8_t *, uint32_t, const uint8_t *, uint32_t, const uint8_t *, uint8_t *);
int aiueos_aes128_gcm_unwrap(const uint8_t *, const uint8_t *, const uint8_t *, uint32_t, uint8_t *);
int aiueos_aes128_gcm_selftest(void);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); }
static uint64_t fnv(const uint8_t *p, uint32_t n) { uint64_t h = 1469598103934665603ull; for (uint32_t i = 0; i < n; i++) { h ^= p[i]; h *= 1099511628211ull; } return h; }
static uint32_t seed = 12345;
static uint8_t rnd(void) { seed = seed * 1103515245u + 12345u; return (uint8_t)(seed >> 16); }
static uint8_t key[16], nonce[12], aad[80], pt[1400], ct[1400 + 16], back[1400 + 16], tag[16], tag2[16];
static void field(const char *k, uint64_t v, int n) { puts_(k); hex(v, n); putc_(' '); }
void test_main(void) {
  static const uint32_t aads[] = {0, 1, 13, 20, 64, 65};
  static const uint32_t pts[] = {0, 1, 15, 16, 17, 64, 255, 600, 1300};
  puts_("TLSGCM-DIFF\n");
  field("selftest=", (uint64_t)aiueos_aes128_gcm_selftest(), 2); putc_('\n');
  for (unsigned a = 0; a < sizeof aads / sizeof *aads; a++)
    for (unsigned p = 0; p < sizeof pts / sizeof *pts; p++) {
      uint32_t al = aads[a], pl = pts[p];
      for (int i = 0; i < 16; i++) key[i] = rnd();
      for (int i = 0; i < 12; i++) nonce[i] = rnd();
      for (uint32_t i = 0; i < sizeof aad; i++) aad[i] = rnd();
      for (uint32_t i = 0; i < pl; i++) pt[i] = rnd();
      for (uint32_t i = 0; i < sizeof ct; i++) ct[i] = 0xa5;
      for (int i = 0; i < 16; i++) tag[i] = 0x5a;
      field("aad=", al, 2); field("pt=", pl, 4);
      field("enc=", (uint64_t)aiueos_aes128_gcm_encrypt(key, nonce, aad, al, pt, pl, ct, tag), 2);
      field("ct=", fnv(ct, sizeof ct), 16); field("tag=", fnv(tag, 16), 16);
      for (uint32_t i = 0; i < sizeof back; i++) back[i] = 0x3c;
      field("dec=", (uint64_t)aiueos_aes128_gcm_decrypt(key, nonce, aad, al, ct, pl, tag, back), 2);
      field("pt2=", fnv(back, sizeof back), 16);
      for (int i = 0; i < 16; i++) tag2[i] = tag[i];
      tag2[p % 16] ^= 1;
      for (uint32_t i = 0; i < sizeof back; i++) back[i] = 0x3c;
      field("bad=", (uint64_t)aiueos_aes128_gcm_decrypt(key, nonce, aad, al, ct, pl, tag2, back), 2);
      field("pt3=", fnv(back, sizeof back), 16);
      for (uint32_t i = 0; i < sizeof back; i++) back[i] = 0x3c;
      field("unw=", (uint64_t)aiueos_aes128_gcm_unwrap(key, nonce, ct, pl, back), 2);
      field("pt4=", fnv(back, sizeof back), 16);
      /* in place: ct == pt */
      for (uint32_t i = 0; i < pl; i++) back[i] = pt[i];
      field("inpl=", (uint64_t)aiueos_aes128_gcm_encrypt(key, nonce, aad, al, back, pl, back, tag2), 2);
      field("ip=", fnv(back, pl), 16); field("iptag=", fnv(tag2, 16), 16);
      putc_('\n');
    }
  puts_("DONE\n");
}
