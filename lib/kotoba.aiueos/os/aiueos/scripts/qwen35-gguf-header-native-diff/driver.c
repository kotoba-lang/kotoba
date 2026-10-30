/* qwen35-gguf-header-valid rebuilt on amu's native root against the committed kotoba-compiler/1 object (JUN-633,
   JUN-554): the same source, two compilers. kotoba_aiueos_qwen35_gguf_header_valid (the committed object) and
   kotoba_aiueos_qwen35_gguf_header_valid_native (the source compiled by the native root under a test name) admit
   the same headers and must give the same verdict. 200000 calls: the two artifact sizes and others, accessible
   lengths around 24 and the artifact's, a null base, and headers with the magic, version, tensor count and pair
   count each right or wrong (including high words), so every refusal -1..-8 and the admission are reached. */
#include <stdint.h>
extern int64_t kotoba_aiueos_qwen35_gguf_header_valid(uint64_t base, uint64_t accessible, uint64_t artifact);
extern int64_t kotoba_aiueos_qwen35_gguf_header_valid_native(uint64_t base, uint64_t accessible, uint64_t artifact);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint8_t header[64] __attribute__((aligned(16)));
static uint64_t seed = 657;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 11; }
static void put32(int at, uint32_t v) { for (int i = 0; i < 4; i++) header[at + i] = (uint8_t)(v >> (8 * i)); }
static void put64(int at, uint64_t v) { put32(at, (uint32_t)v); put32(at + 4, (uint32_t)(v >> 32)); }
void test_main(void) {
  puts_("GGUFHEADERDIFF\n");
  unsigned n_bad = 0, seen[10] = {0};
  for (unsigned k = 0; k < 200000; k++) {
    unsigned r = (unsigned)(rnd() % 8);
    uint64_t artifact = r < 3 ? 5946648928ull : r < 6 ? 10934860704ull : r == 6 ? 5946648928ull + 1 - (rnd() % 3) : rnd();
    int big = artifact == 5946648928ull;
    put32(0, rnd() % 5 ? 1179993927u : (uint32_t)rnd());
    put32(4, rnd() % 5 ? 3u : (uint32_t)(rnd() % 6));
    uint64_t tensors = big ? 851 : 866, pairs = big ? 49 : 50;
    put64(8, rnd() % 5 ? tensors : (rnd() % 2 ? tensors + 1 : tensors | (uint64_t)(1 + rnd() % 7) << 32));
    put64(16, rnd() % 5 ? pairs : (rnd() % 2 ? pairs - 1 : pairs | (uint64_t)(1 + rnd() % 7) << 32));
    unsigned a = (unsigned)(rnd() % 6);
    uint64_t accessible = a == 0 ? rnd() % 30 : a == 1 ? 24 : a == 2 ? artifact : a == 3 ? artifact + 1 : 24 + rnd() % 4096;
    uint64_t base = k % 101 == 0 ? 0 : (uint64_t)(uintptr_t)header;
    int64_t v1 = kotoba_aiueos_qwen35_gguf_header_valid(base, accessible, artifact);
    int64_t v2 = kotoba_aiueos_qwen35_gguf_header_valid_native(base, accessible, artifact);
    if (v1 >= -8 && v1 <= 0) seen[-v1]++; else seen[9]++;
    if (v1 != v2 && n_bad++ < 8) { puts_("GGUF-DIFF "); hex(k, 5); hex((uint64_t)v1, 2); hex((uint64_t)v2, 2); putc_('\n'); }
  }
  puts_("VERDICTS"); for (int i = 0; i < 10; i++) { putc_(' '); hex(seen[i], 5); } putc_('\n');
  puts_("CASES 30d40 DIFFS "); hex(n_bad, 5); putc_('\n'); puts_("DONE\n");
}
