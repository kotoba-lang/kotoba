#include <stdint.h>
struct virtio_pci_cap { uint8_t bar; uint32_t offset, length, notify_multiplier; };
struct virtio_caps { struct virtio_pci_cap common, notify, device; int have_common, have_notify, have_device; uint8_t msix_pointer; };
int old_find_virtio_caps(uint8_t, uint8_t, uint8_t, struct virtio_caps *);
int new_find_virtio_caps(uint8_t, uint8_t, uint8_t, struct virtio_caps *);
static uint8_t cfg[256];
uint32_t config_read(uint8_t bus, uint8_t dev, uint8_t fn, uint8_t off) {
  (void)bus; (void)dev; (void)fn; off &= 252;
  return (uint32_t)cfg[off] | (uint32_t)cfg[off + 1] << 8 | (uint32_t)cfg[off + 2] << 16 | (uint32_t)cfg[off + 3] << 24;
}
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 598;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 23; }
static void w32(unsigned at, uint32_t v) { cfg[at & 255] = (uint8_t)v; cfg[(at + 1) & 255] = (uint8_t)(v >> 8); cfg[(at + 2) & 255] = (uint8_t)(v >> 16); cfg[(at + 3) & 255] = (uint8_t)(v >> 24); }
static unsigned n_cases, n_ok, n_bad;
static int same_cap(const struct virtio_pci_cap *a, const struct virtio_pci_cap *b) {
  return a->bar == b->bar && a->offset == b->offset && a->length == b->length && a->notify_multiplier == b->notify_multiplier;
}
static void compare(unsigned tag) {
  struct virtio_caps a, b;
  for (unsigned i = 0; i < sizeof a; i++) { ((uint8_t *)&a)[i] = 0x77; ((uint8_t *)&b)[i] = 0x77; }
  int ra = old_find_virtio_caps(0, 3, 0, &a), rb = new_find_virtio_caps(0, 3, 0, &b);
  int same = ra == rb;
  if (ra && rb) same = same && same_cap(&a.common, &b.common) && same_cap(&a.notify, &b.notify) && same_cap(&a.device, &b.device) &&
                a.have_common == b.have_common && a.have_notify == b.have_notify && a.have_device == b.have_device && a.msix_pointer == b.msix_pointer;
  n_cases++; if (ra) n_ok++;
  if (!same && n_bad++ < 8) { puts_("CAPS-DIFF "); hex(tag, 6); hex(ra, 1); hex(rb, 1); putc_('\n'); }
}
/* a chain of capabilities at the given pointers: kinds 1 2 4 vendor, 0x11 MSI-X, 0x05 MSI, other */
static void build(unsigned k) {
  for (int i = 0; i < 256; i++) cfg[i] = (uint8_t)rnd();
  w32(4, (uint32_t)(rnd() & 0xffef) << 16 | (uint32_t)(k % 23 == 0 ? 0 : 0x10) << 16);
  unsigned n = 1 + (unsigned)(rnd() % 9), at[12], used = 0;
  for (unsigned i = 0; i < n; i++) {                      /* distinct dword-aligned slots 0x40..0xf0 */
    unsigned p; do { p = 0x40 + 4 * (unsigned)(rnd() % 45); } while (used & (1u << ((p - 0x40) / 4 % 32)) && 0);
    at[i] = p; used |= 1u << ((p - 0x40) / 4 % 32);
  }
  cfg[0x34] = (uint8_t)(at[0] | (k % 17 == 0 ? 2 : 0));
  for (unsigned i = 0; i < n; i++) {
    unsigned p = at[i], kind = (unsigned)(rnd() % 8);
    cfg[(p + 1) & 255] = (uint8_t)(i + 1 < n ? at[i + 1] : 0);
    if (kind < 5) {
      cfg[p] = 0x09; cfg[(p + 3) & 255] = (uint8_t)(kind == 0 ? 1 : kind == 1 ? 2 : kind == 2 ? 4 : kind == 3 ? 1 + rnd() % 8 : 2);
      cfg[(p + 2) & 255] = (uint8_t)(k % 11 == 0 ? rnd() : (rnd() % 3 ? 20 : 16));
      cfg[(p + 4) & 255] = (uint8_t)(k % 13 == 0 ? rnd() % 8 : rnd() % 6);
      w32(p + 8, (uint32_t)(k % 19 == 0 ? 0xfffffff0u : rnd() % 0x4000));
      w32(p + 12, (uint32_t)(k % 7 == 0 ? rnd() : (k % 5 == 0 ? 0 : 8 + rnd() % 0x80)));
      w32(p + 16, (uint32_t)(rnd() % 3 ? 4 : 0));
    } else if (kind == 5) cfg[p] = 0x11;
    else cfg[p] = (uint8_t)(rnd() % 3 ? 0x05 : 0x10);
  }
  if (k % 29 == 0) cfg[(at[n - 1] + 1) & 255] = (uint8_t)at[0];   /* a loop */
}
void test_main(void) {
  puts_("VIRTIOCAPSDIFF\n");
  for (unsigned k = 0; k < 30000; k++) {
    build(k);
    compare(k * 4);
    unsigned c = 0x40 + (unsigned)(rnd() % 192); uint8_t s = cfg[c]; cfg[c] ^= (uint8_t)(1 + rnd() % 255); compare(k * 4 + 1); cfg[c] = s;
    if (k % 3 == 0) { cfg[0x34] = 0xfc; cfg[0xfc] = 0x09; cfg[0xfd] = 0; cfg[0xfe] = (uint8_t)(rnd() % 6); cfg[0xff] = 1; compare(k * 4 + 2); }
  }
  /* edges: an MSI-X capability at 0xf4 / 0xf8 after a valid pair, a common configuration of exactly 55 / 56 bytes */
  for (unsigned k = 0; k < 4000; k++) {
    for (int i = 0; i < 256; i++) cfg[i] = (uint8_t)rnd();
    w32(4, 0x10u << 16);
    cfg[0x34] = 0x40;
    cfg[0x40] = 0x09; cfg[0x41] = 0x60; cfg[0x42] = 16; cfg[0x43] = 1; cfg[0x44] = 0; w32(0x48, 0); w32(0x4c, k % 4 == 0 ? 55 : 56);
    cfg[0x60] = 0x09; cfg[0x61] = (uint8_t)(k % 3 ? 0xf8 : 0xf4); cfg[0x62] = 20; cfg[0x63] = 2; cfg[0x64] = 1; w32(0x68, 0x1000); w32(0x6c, 4); w32(0x70, 4);
    unsigned m = k % 3 ? 0xf8 : 0xf4; cfg[m] = 0x11; cfg[m + 1] = 0;
    compare(800000 + k);
  }
  /* a 49-step chain, a 48-step one, and pure noise */
  for (unsigned k = 0; k < 2000; k++) {
    for (int i = 0; i < 256; i++) cfg[i] = (uint8_t)rnd();
    w32(4, 0x10u << 16);
    unsigned steps = k % 2 ? 48 : 47;
    cfg[0x34] = 0x40;
    for (unsigned i = 0; i < steps && i < 48; i++) { unsigned p = 0x40 + 4 * i; cfg[p] = 0x05; cfg[p + 1] = (uint8_t)(i + 1 < steps ? p + 4 : 0); }
    compare(900000 + k);
    for (int i = 0; i < 256; i++) cfg[i] = (uint8_t)rnd();
    compare(950000 + k);
  }
  puts_("CASES "); hex(n_cases, 5); puts_("ADMITTED "); hex(n_ok, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
