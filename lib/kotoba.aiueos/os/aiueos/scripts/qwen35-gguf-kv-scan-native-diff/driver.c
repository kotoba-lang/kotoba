/* qwen35-gguf-kv-scan ported to amu's native object route against the committed kotoba-compiler/1 object (JUN-633,
   JUN-554). Both scan the Qwen3.8 GGUF metadata prefix tests/make_qwen35_header_fixture.py builds (linked in as
   header.gguf) into a plan workspace, and must answer the same and leave the same plan bytes (and the guard after
   them untouched). 210 scans: the header as built; the early refusals (base, plan, plan length, accessible, magic,
   version, the profile's metadata count); and for each of the 50 entries, its key's first byte changed, its value type
   changed, its first value byte changed, and the accessible length ending two bytes into its value. Each mutation is
   undone before the next. */
#include <stdint.h>
#include "offsets.h"
extern int64_t kotoba_aiueos_qwen35_gguf_kv_scan(uint64_t base, uint64_t accessible, uint64_t plan, uint64_t plan_length);
extern int64_t kotoba_aiueos_qwen35_gguf_kv_scan_native(uint64_t base, uint64_t accessible, uint64_t plan, uint64_t plan_length);
extern uint8_t _binary_header_gguf_start[], _binary_header_gguf_end[];
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint8_t p1[160] __attribute__((aligned(16))), p2[160] __attribute__((aligned(16)));
static unsigned n_cases, n_ok, n_bad;
static void run(unsigned id, uint64_t base, uint64_t accessible, int null_plan, uint64_t plen) {
  for (int i = 0; i < 160; i++) { p1[i] = 0xa5; p2[i] = 0xa5; }
  int64_t v1 = kotoba_aiueos_qwen35_gguf_kv_scan(base, accessible, null_plan ? 0 : (uint64_t)(uintptr_t)p1, plen);
  int64_t v2 = kotoba_aiueos_qwen35_gguf_kv_scan_native(base, accessible, null_plan ? 0 : (uint64_t)(uintptr_t)p2, plen);
  unsigned bad = v1 != v2; for (int i = 0; i < 160; i++) if (p1[i] != p2[i]) bad++;
  n_cases++; if (v1 == 0) n_ok++;
  if (bad && n_bad++ < 12) { puts_("KV-DIFF "); hex(id, 4); hex((uint64_t)v1, 16); hex((uint64_t)v2, 16); hex(bad, 3); putc_('\n'); }
}
void test_main(void) {
  puts_("KVSCANDIFF\n");
  uint8_t *h = _binary_header_gguf_start; uint64_t hb = (uint64_t)(uintptr_t)h, len = (uint64_t)(_binary_header_gguf_end - h);
  run(0, hb, len, 0, 128);
  run(1, hb, len, 0, 144); run(2, hb, len, 1, 128); run(3, 0, len, 0, 128); run(4, hb, 23, 0, 128);
  h[0] ^= 1; run(5, hb, len, 0, 128); h[0] ^= 1;
  h[4] = 2; run(6, hb, len, 0, 128); h[4] = 3;
  uint8_t t = h[8]; h[8] = 0x53; run(7, hb, len, 0, 144); run(8, hb, len, 0, 128); h[8] = t;
  t = h[16]; h[16] = 49; run(9, hb, len, 0, 128); h[16] = t;
  for (unsigned e = 0; e < ENTRIES; e++) {
    uint64_t key = entry_off[e][1], type = entry_off[e][3], value = entry_off[e][4];
    h[key] ^= 0x20; run(100 + e, hb, len, 0, 128); h[key] ^= 0x20;
    h[type] ^= 3; run(200 + e, hb, len, 0, 128); h[type] ^= 3;
    h[value] ^= 1; run(300 + e, hb, len, 0, 128); h[value] ^= 1;
    run(400 + e, hb, value + 2, 0, 128);
    puts_("E "); hex(e, 2); putc_('\n');
  }
  puts_("CASES "); hex(n_cases, 3); puts_("ADMITTED "); hex(n_ok, 3); puts_("DIFFS "); hex(n_bad, 3); putc_('\n'); puts_("DONE\n");
}
