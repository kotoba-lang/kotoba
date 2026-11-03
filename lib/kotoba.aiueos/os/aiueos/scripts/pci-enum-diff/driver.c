#include <stdint.h>
int old_present(uint32_t); int old_functions(uint8_t); int old_driver(uint32_t);
int old_result(int, int, int, int, uint32_t, uint32_t); int old_rtl8125(uint32_t);
int64_t kotoba_aiueos_pci_present(int64_t); int64_t kotoba_aiueos_pci_functions(int64_t);
int64_t kotoba_aiueos_virtio_driver(int64_t); int64_t kotoba_aiueos_pci_rtl8125(int64_t);
int64_t kotoba_aiueos_virtio_probe_result(int64_t, int64_t, int64_t, int64_t, int64_t, int64_t);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static unsigned n_cases, n_bad;
static void diff(const char *what, uint64_t x, int64_t a, int64_t b) {
  n_cases++; if (a != b && n_bad++ < 8) { puts_("ENUM-DIFF "); puts_(what); putc_(' '); hex(x, 8); hex((uint64_t)a, 2); hex((uint64_t)b, 2); putc_('\n'); }
}
void test_main(void) {
  puts_("PCIENUMDIFF\n");
  const uint32_t vendors[] = {0x1af4, 0x10ec, 0xffff, 0x8086, 0x1af5, 0x0000};
  for (unsigned v = 0; v < 6; v++) for (uint32_t d = 0; d < 65536; d++) {      /* every device ID under six vendors */
    uint32_t id = d << 16 | vendors[v];
    diff("present", id, old_present(id), kotoba_aiueos_pci_present(id));
    diff("driver", id, old_driver(id), kotoba_aiueos_virtio_driver(id));
    diff("rtl8125", id, old_rtl8125(id), kotoba_aiueos_pci_rtl8125(id));
  }
  for (uint32_t low = 0; low < 65536; low++) {                                   /* every vendor, device 0x1044 */
    uint32_t id = 0x1044u << 16 | low;
    diff("present", id, old_present(id), kotoba_aiueos_pci_present(id));
    diff("driver", id, old_driver(id), kotoba_aiueos_virtio_driver(id));
  }
  for (unsigned h = 0; h < 256; h++) diff("functions", h, old_functions((uint8_t)h), kotoba_aiueos_pci_functions(h));
  for (unsigned m = 0; m < 16; m++) for (unsigned p = 0; p < 3; p++) for (unsigned q = 0; q < 3; q++)
    diff("result", m << 8 | p << 4 | q, old_result(m & 1, m >> 1 & 1, m >> 2 & 1, m >> 3 & 1, p, q),
         kotoba_aiueos_virtio_probe_result(m & 1, m >> 1 & 1, m >> 2 & 1, m >> 3 & 1, p, q));
  puts_("CASES "); hex(n_cases, 6); puts_("DIFFS "); hex(n_bad, 6); putc_('\n'); puts_("DONE\n");
}
