/* acpi-table-valid built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object. SDT
   headers whose declared length (offset 4) matches the length argument and whose signature (offsets 0 .. 3, read most
   significant byte first) matches the expected one, with one input then mutated in turn: the declared length, a
   signature byte, the expected signature, the max-length argument, the length at and around 36, 16384 and max-length,
   and the table address (null, negative, at and around the 1 GiB identity limit, which only bounds the address and is
   not read past the header). The object reads only the first 8 bytes, so the length argument is free of the buffer;
   answers and traps compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_acpi_table_valid(int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_acpi_table_valid_native(int64_t, int64_t, int64_t, int64_t);
static uint8_t buf[64] __attribute__((aligned(16)));
static const char *SIG[] = {"APIC", "XSDT", "RSDT", "DMAR", "FACP", "MCFG"};
static const int64_t LEN[] = {0, 1, 35, 36, 37, 44, 100, 4096, 16383, 16384, 16385, 1048576, -1, INT64_MIN};
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)buf;
  void *o = (void *)kotoba_aiueos_acpi_table_valid, *n = (void *)kotoba_aiueos_acpi_table_valid_native;
  for (unsigned k = 0; k < 20000; k++) {
    for (int i = 0; i < 64; i++) buf[i] = (uint8_t)rnd();
    const char *s = SIG[rnd() % 6];
    for (int i = 0; i < 4; i++) buf[i] = (uint8_t)s[i];
    int64_t sig = ((int64_t)buf[0] << 24) | (buf[1] << 16) | (buf[2] << 8) | buf[3];
    int64_t len = 36 + (int64_t)(rnd() % (16384 - 35)), max = 1048576, tab = b;
    unsigned m = (unsigned)(rnd() % 9);
    if (m == 1) len = LEN[rnd() % 14];
    if (m == 2) max = rnd() % 2 ? len - (int64_t)(rnd() % 2) : (int64_t)(rnd() % 20000);
    if (m == 3) { tab = rnd() % 4 ? (1ll << 30) - len + (int64_t)(rnd() % 3) - 1 : (int64_t)(rnd() % 3) - 1; }
    if (m == 4) tab = rnd() % 2 ? (1ll << 30) + (int64_t)(rnd() % 3) - 1 : INT64_MIN + (int64_t)(rnd() % 2) * 4096;
    for (int i = 0; i < 4; i++) buf[4 + i] = (uint8_t)((uint64_t)len >> (8 * i));
    if (m == 5) buf[4 + rnd() % 4] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 6) buf[rnd() % 4] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 7) sig = rnd() % 2 ? sig ^ (1ll << (rnd() % 32)) : sig | (1ll << 32);
    if (m == 8) { len = 16000 + (int64_t)(rnd() % 400); max = len + (int64_t)(rnd() % 3); for (int i = 0; i < 4; i++) buf[4 + i] = (uint8_t)((uint64_t)len >> (8 * i)); }
    if (tab != b && tab > 0 && tab < (1ll << 30) && tab != 0) {   /* an address in the identity map: give it the same header */
      uint8_t *p = (uint8_t *)(uintptr_t)tab; for (int i = 0; i < 8; i++) p[i] = buf[i];
    }
    same(o, n, tab, len, sig, max, 0);
  }
  report();
}
