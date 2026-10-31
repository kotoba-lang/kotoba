/* qwen35-tensor-table-bind ported to amu's native object route against the committed kotoba-compiler/1 object
   (JUN-633, JUN-554). Both bind the 866-record tensor table of the Qwen3.8 prefix tests/make_qwen35_header_fixture.py
   builds (linked in as header.gguf), called as the C calls it -- the table at the metadata's end, the rest of the
   prefix as its limit, a 28160-byte plan -- and must answer the same and leave the same plan (and the guard after it
   untouched). Scans: the table as built; the early refusals (table, plan, plan length, metadata end, a limit under the
   table's floor); a limit ending inside a record; and for every seventh record, its name's first byte, its
   dimension count, its first dimension, its type and its data offset each changed (undone before the next). */
#include <stdint.h>
#include "records.h"
extern int64_t kotoba_aiueos_qwen35_tensor_table_bind(uint64_t t, uint64_t l, uint64_t m, uint64_t p, uint64_t pl);
extern int64_t kotoba_aiueos_qwen35_tensor_table_bind_native(uint64_t t, uint64_t l, uint64_t m, uint64_t p, uint64_t pl);
extern uint8_t _binary_header_gguf_start[], _binary_header_gguf_end[];
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
#define PLAN 28160
static uint8_t p1[PLAN + 64] __attribute__((aligned(64))), p2[PLAN + 64] __attribute__((aligned(64)));
static unsigned n_cases, n_ok, n_bad;
static void run(unsigned id, uint64_t t, uint64_t limit, uint64_t meta, int null_plan, uint64_t plen) {
  for (int i = 0; i < PLAN + 64; i++) { p1[i] = 0xa5; p2[i] = 0xa5; }
  int64_t v1 = kotoba_aiueos_qwen35_tensor_table_bind(t, limit, meta, null_plan ? 0 : (uint64_t)(uintptr_t)p1, plen);
  int64_t v2 = kotoba_aiueos_qwen35_tensor_table_bind_native(t, limit, meta, null_plan ? 0 : (uint64_t)(uintptr_t)p2, plen);
  unsigned bad = v1 != v2; for (int i = 0; i < PLAN + 64; i++) if (p1[i] != p2[i]) bad++;
  n_cases++; if (v1 == 0) n_ok++;
  if (bad && n_bad++ < 12) { puts_("TT-DIFF "); hex(id, 4); hex((uint64_t)v1, 16); hex((uint64_t)v2, 16); hex(bad, 5); putc_('\n'); }
}
void test_main(void) {
  puts_("TENSORTABLEDIFF\n");
  uint8_t *h = _binary_header_gguf_start; uint64_t len = (uint64_t)(_binary_header_gguf_end - h);
  uint8_t *tb = h + METADATA_END; uint64_t t = (uint64_t)(uintptr_t)tb, lim = len - METADATA_END;
  run(0, t, lim, METADATA_END, 0, PLAN);
  run(1, 0, lim, METADATA_END, 0, PLAN); run(2, t, lim, METADATA_END, 1, PLAN); run(3, t, lim, METADATA_END, 0, PLAN - 4);
  run(4, t, lim, METADATA_END + 1, 0, PLAN); run(5, t, 1000, METADATA_END, 0, PLAN); run(6, t, lim, 11070652, 0, PLAN);
  run(7, t, rec_off[RECORDS / 2][3] + 3, METADATA_END, 0, PLAN);
  for (unsigned r = 0; r < RECORDS; r += 7) {
    uint8_t s;
    s = tb[rec_off[r][1]]; tb[rec_off[r][1]] ^= 0x01; run(1000 + r, t, lim, METADATA_END, 0, PLAN); tb[rec_off[r][1]] = s;
    s = tb[rec_off[r][2]]; tb[rec_off[r][2]] += 1; run(2000 + r, t, lim, METADATA_END, 0, PLAN); tb[rec_off[r][2]] = s;
    s = tb[rec_off[r][3]]; tb[rec_off[r][3]] ^= 0x01; run(3000 + r, t, lim, METADATA_END, 0, PLAN); tb[rec_off[r][3]] = s;
    s = tb[rec_off[r][4]]; tb[rec_off[r][4]] ^= 0x01; run(4000 + r, t, lim, METADATA_END, 0, PLAN); tb[rec_off[r][4]] = s;
    s = tb[rec_off[r][5]]; tb[rec_off[r][5]] ^= 0x20; run(5000 + r, t, lim, METADATA_END, 0, PLAN); tb[rec_off[r][5]] = s;
  }
  puts_("CASES "); hex(n_cases, 3); puts_("BOUND "); hex(n_ok, 3); puts_("DIFFS "); hex(n_bad, 3); putc_('\n'); puts_("DONE\n");
}
