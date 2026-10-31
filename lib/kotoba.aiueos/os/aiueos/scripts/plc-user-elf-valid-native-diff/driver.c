/* plc-user-elf-valid built on amu's native object route (JUN-722, JUN-708) against the amu 53799cb object of main
   455b84fb it replaces. Each case starts from an image the validator admits (the PLC CPL3 ELF layout: two PT_LOAD
   segments at 0x1E1000 and 0x1E2000, the 88-byte context with capability bitmap 0xF0000 at 8208, a random text size
   in 1 .. 4096 and image length in 8280 .. 12288, every unchecked byte random), then leaves it valid or disturbs one
   checked byte (to a random value, or by +-1), flips random bytes in the checked regions, moves the length or text
   size across a boundary, or passes a null base; answers and traps compared. */
#include "diff.h"
static uint8_t im[16384] __attribute__((aligned(16)));
static void p8(int o, unsigned v) { im[o] = (uint8_t)v; }
static void p16(int o, unsigned v) { p8(o, v & 255); p8(o + 1, (v >> 8) & 255); }
static void p32(int o, uint32_t v) { p16(o, v & 0xffff); p16(o + 2, v >> 16); }
static void p64(int o, uint64_t v) { p32(o, (uint32_t)v); p32(o + 4, (uint32_t)(v >> 32)); }
static void seg(int b, unsigned flags, uint64_t off, uint64_t va, uint64_t sz) {
  p32(b, 1); p32(b + 4, flags); p64(b + 8, off); p64(b + 16, va); p64(b + 24, va); p64(b + 32, sz); p64(b + 40, sz); p64(b + 48, 4096);
}
/* the byte ranges the validator reads: header, both program headers, the context */
static const int lo[] = {0, 16, 24, 32, 52, 64, 120, 8192};
static const int hi[] = {7, 23, 31, 39, 57, 119, 175, 8279};
static int checked(void) { unsigned r = (unsigned)(rnd() % 8); return lo[r] + (int)(rnd() % (unsigned)(hi[r] - lo[r] + 1)); }
extern int64_t kotoba_aiueos_user_elf_valid(int64_t, int64_t);
extern int64_t kotoba_aiueos_user_elf_valid_native(int64_t, int64_t);
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)im;
  void *o = (void *)kotoba_aiueos_user_elf_valid, *n = (void *)kotoba_aiueos_user_elf_valid_native;
  for (unsigned k = 0; k < 40000; k++) {
    for (int i = 0; i < 16384; i++) im[i] = (uint8_t)rnd();
    int64_t len = 8280 + (int64_t)(rnd() % 4009);
    uint32_t text = 1 + (uint32_t)(rnd() % 4096);
    p32(0, 0x464c457f); p8(4, 2); p8(5, 1); p8(6, 1);
    p16(16, 2); p16(18, 62); p32(20, 1); p64(24, 0x1E1000); p64(32, 64);
    p16(52, 64); p16(54, 56); p16(56, 2);
    seg(64, 5, 4096, 0x1E1000, text); seg(120, 6, 8192, 0x1E2000, 88);
    for (int i = 8192; i < 8280; i++) im[i] = 0;
    p32(8200, 512); p32(8208, 983040); p32(8240, 1970208);
    unsigned m = (unsigned)(rnd() % 16);
    if (m >= 4 && m < 10) { int at = checked(); im[at] = rnd() % 2 ? (uint8_t)rnd() : (uint8_t)(im[at] + (rnd() % 2 ? 1 : 255)); }
    else if (m == 10 || m == 11) { unsigned c = 1 + (unsigned)(rnd() % 4); while (c--) im[checked()] ^= (uint8_t)(1u << (rnd() % 8)); }
    else if (m == 12) { const int64_t L[] = {8279, 8280, 12288, 12289, 0, 4096, 16384}; len = rnd() % 4 ? L[rnd() % 7] : (int64_t)rnd(); }
    else if (m == 13) { const uint32_t T[] = {0, 1, 4096, 4097}; uint32_t t = rnd() % 3 ? T[rnd() % 4] : (uint32_t)(len - 4096 + (int64_t)(rnd() % 3) - 1); p32(96, t); p32(104, t); }
    same(o, n, k % 211 == 0 ? 0 : b, len, 0, 0, 0);
  }
  report();
}
