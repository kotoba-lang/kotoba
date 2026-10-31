/* pci-config-read built on amu's native object route (JUN-552, amu ADR 0399) against the committed kotoba-compiler/1
   object. The grid of bus, device, function and offset values at and around each bound (bus 0 .. 255, device 0 .. 31,
   function 0 .. 7, offset 0 .. 255 with its low two bits dropped, and the i64 extremes), then every dword of every
   function on buses 0 and 1, then random tuples. The full answer of every call goes to debugcon, and run.sh compares
   the two runs' debugcon logs and traces of every 0xcf8 address write and 0xcfc data read. Built once per object
   (NATIVE selects the native one). PRESENT counts answers other than 0xffffffff. */
#include <stdint.h>
extern int64_t kotoba_aiueos_pci_config_read(int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_pci_config_read_native(int64_t, int64_t, int64_t, int64_t);
#ifdef NATIVE
#define CALL kotoba_aiueos_pci_config_read_native
#else
#define CALL kotoba_aiueos_pci_config_read
#endif
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 552;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static unsigned n_all, n_ok;
static void one(int64_t b, int64_t d, int64_t f, int64_t o) {
  int64_t r = CALL(b, d, f, o);
  n_all++; if (r != 4294967295) n_ok++;
  hex((uint64_t)r, 16); if (n_all % 8 == 0) putc_('\n');
}
void test_main(void) {
  puts_("PORTDIFF\n");
  static const int64_t B[] = {-1, 0, 1, 2, 127, 128, 254, 255, 256, 1ll << 32, INT64_MIN};
  static const int64_t D[] = {-1, 0, 1, 2, 3, 15, 16, 30, 31, 32, 64};
  static const int64_t F[] = {-1, 0, 1, 6, 7, 8};
  static const int64_t O[] = {-1, 0, 1, 2, 3, 4, 5, 8, 0x10, 0x2c, 0x34, 63, 64, 128, 252, 253, 254, 255, 256, 1ll << 33};
  for (unsigned i = 0; i < sizeof B / 8; i++) for (unsigned j = 0; j < sizeof D / 8; j++)
    for (unsigned k = 0; k < sizeof F / 8; k++) for (unsigned l = 0; l < sizeof O / 8; l++)
      one(B[i], D[j], F[k], O[l]);
  for (int64_t b = 0; b < 2; b++) for (int64_t d = 0; d < 32; d++) for (int64_t f = 0; f < 8; f++)
    for (int64_t o = 0; o < 256; o += 4) one(b, d, f, o);
  for (unsigned k = 0; k < 4000; k++) {
    int64_t b = (int64_t)(rnd() % 270) - 4, d = (int64_t)(rnd() % 36) - 2, f = (int64_t)(rnd() % 10) - 1, o = (int64_t)(rnd() % 262) - 3;
    one(b, d, f, o);
  }
  putc_('\n'); puts_("CASES "); hex(n_all, 8); puts_("NONZERO "); hex(n_ok, 8); putc_('\n'); puts_("DONE\n");
}
