/* device_result.c's cpuid / rdrand64 / aiueos_cpu_random_bytes and qwen35_infer.c's read_cycles before JUN-554 moved them
   to kotoba/cpu-reads.o, verbatim (aiueos_cpu_random_bytes and read_cycles renamed old_ and made external). */
#include <stdint.h>
static void cpuid(uint32_t leaf, uint32_t subleaf,
                  uint32_t *a, uint32_t *b, uint32_t *c, uint32_t *d) {
  __asm__ volatile("cpuid"
                   : "=a"(*a), "=b"(*b), "=c"(*c), "=d"(*d)
                   : "a"(leaf), "c"(subleaf));
}

static int rdrand64(uint64_t *value) {
  for (uint32_t attempt = 0; attempt < 32; attempt++) {
    uint8_t ready;
    uint64_t candidate;
    __asm__ volatile("rdrand %0; setc %1" : "=r"(candidate), "=qm"(ready));
    if (ready) { *value = candidate; return 1; }
    __asm__ volatile("pause");
  }
  return 0;
}

int old_cpu_random_bytes(uint8_t *out, uint32_t bytes) {
  uint32_t a, b, c, d;
  if (!out || !bytes) return 0;
  cpuid(1, 0, &a, &b, &c, &d);
  if (!(c & (1U << 30))) return 0;
  uint32_t offset = 0;
  while (offset < bytes) {
    uint64_t word;
    if (!rdrand64(&word)) return 0;
    for (uint32_t i = 0; i < 8 && offset < bytes; i++, offset++)
      out[offset] = (uint8_t)(word >> (i * 8));
  }
  return 1;
}
uint64_t old_read_cycles(void) {
#if defined(__x86_64__)
  uint32_t low, high;
  __asm__ volatile("lfence; rdtsc" : "=a"(low), "=d"(high) : : "memory");
  return ((uint64_t)high << 32) | low;
#else
  return 0;
#endif
}

