/* app-catalog-valid built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object.
   Valid aiuefs-v3 catalogs of 1 .. 4 entries (printable NUL-padded ids, disjoint extents of 1 .. 12288 bytes, each
   signature sector past its extent, signer 1) with a routing pair outside every extent, then one thing mutated in turn:
   the magic, the version, the count against the length, an id byte (empty, out of range, a byte after the NUL, a
   duplicate id), an extent or signature sector moved onto a neighbour's or onto a routing sector, a length at 0 or
   12289, the capacity at the last extent's end or signature, the signer, the routing sectors, the routing length; plus
   random catalogs, lengths outside 80 .. 272, and null catalog or routing pointers; answers and traps compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_app_catalog_valid(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_app_catalog_valid_native(int64_t, int64_t, int64_t, int64_t, int64_t);
static uint8_t cat[512] __attribute__((aligned(16))), rt[16] __attribute__((aligned(16)));
static void put32(uint8_t *p, uint32_t v) { for (int i = 0; i < 4; i++) p[i] = (uint8_t)(v >> (8 * i)); }
static uint32_t get32(const uint8_t *p) { return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  void *o = (void *)kotoba_aiueos_app_catalog_valid, *n = (void *)kotoba_aiueos_app_catalog_valid_native;
  static const char M[8] = {'A', 'I', 'U', 'C', 'A', 'T', '1', 0};
  for (unsigned k = 0; k < 30000; k++) {
    for (int i = 0; i < 512; i++) cat[i] = (uint8_t)rnd();
    for (int i = 0; i < 16; i++) rt[i] = (uint8_t)rnd();
    uint32_t count = 1 + (uint32_t)(rnd() % 4);
    for (int i = 0; i < 8; i++) cat[i] = (uint8_t)M[i];
    put32(cat + 8, 1); put32(cat + 12, count);
    uint32_t sector = 4 + (uint32_t)(rnd() % 40), last_end = 0, last_sig = 0;
    for (uint32_t a = 0; a < count; a++) {
      uint8_t *e = cat + 16 + 64 * a;
      int idn = 1 + (int)(rnd() % 16);
      for (int i = 0; i < 16; i++) e[i] = i < idn ? (uint8_t)(33 + rnd() % 94) : 0;
      e[0] = (uint8_t)('a' + a);
      uint32_t len = 1 + (uint32_t)(rnd() % 12288), end = sector + (len + 511) / 512, sig = end + (uint32_t)(rnd() % 4);
      put32(e + 16, sector); put32(e + 20, len); put32(e + 56, sig); put32(e + 60, 1);
      last_end = end; last_sig = sig; sector = sig + 1 + (uint32_t)(rnd() % 8);
    }
    int64_t length = 16 + 64 * (int64_t)count, capacity = (int64_t)last_sig + 1 + (int64_t)(rnd() % 100), rlen = 8;
    put32(rt, (uint32_t)(sector + (uint32_t)(rnd() % 50))); put32(rt + 4, (uint32_t)(rnd() % 4));
    uint32_t a = (uint32_t)(rnd() % count), b = (uint32_t)(rnd() % count); uint8_t *ea = cat + 16 + 64 * a, *eb = cat + 16 + 64 * b;
    switch (rnd() % 24) {
      case 1: cat[rnd() % 8] ^= (uint8_t)(1 + rnd() % 255); break;
      case 2: put32(cat + 8, (uint32_t)(rnd() % 3)); break;
      case 3: put32(cat + 12, rnd() % 2 ? (uint32_t)(rnd() % 6) : (uint32_t)rnd()); break;
      case 4: ea[0] = 0; break;
      case 5: ea[rnd() % 16] = (uint8_t)(rnd() % 2 ? rnd() % 33 : 127 + rnd() % 129); break;
      case 6: { int z = (int)(rnd() % 15); ea[z] = 0; ea[z + 1 + rnd() % (15 - z)] = 'x'; } break;
      case 7: for (int i = 0; i < 16; i++) ea[i] = eb[i]; break;
      case 8: put32(ea + 16, get32(eb + 16) + (uint32_t)(rnd() % 3)); break;
      case 9: put32(ea + 56, get32(eb + 56)); break;
      case 10: put32(ea + 56, get32(eb + 16) + (uint32_t)(rnd() % 2)); break;
      case 11: put32(ea + 20, rnd() % 2 ? 0 : 12289); break;
      case 12: put32(ea + 16, (uint32_t)(rnd() % 5)); break;
      case 13: capacity = rnd() % 2 ? (int64_t)last_end - (int64_t)(rnd() % 2) : (int64_t)last_sig + (int64_t)(rnd() % 2); break;
      case 14: put32(ea + 60, (uint32_t)(rnd() % 3)); break;
      case 15: put32(rt, get32(ea + 16) + (uint32_t)(rnd() % 2)); break;
      case 16: put32(rt + 4, rnd() % 2 ? get32(ea + 16) : get32(ea + 56)); break;
      case 17: put32(rt, get32(ea + 56)); break;
      case 18: rlen = (int64_t)(rnd() % 16); break;
      case 19: length = rnd() % 2 ? (int64_t)(rnd() % 300) : length + (int64_t)(rnd() % 3) - 1; break;
      case 20: for (int i = 16; i < 272; i++) cat[i] = (uint8_t)rnd(); break;
      case 21: put32(ea + 56, get32(ea + 16) + (uint32_t)(rnd() % 2)); break;
      default: break;
    }
    int64_t pc = k % 97 == 0 ? 0 : (int64_t)(uintptr_t)cat, pr = k % 89 == 0 ? 0 : (int64_t)(uintptr_t)rt;
    same(o, n, pc, length, capacity, pr, rlen);
  }
  report();
}
