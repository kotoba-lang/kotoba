#include <stdint.h>

struct aiueos_boot_info {
  uint64_t magic, version;
  void *memory_map; uint64_t memory_map_size, descriptor_size, descriptor_version;
};

static inline void debug_byte(uint8_t value) {
  __asm__ volatile("outb %0, $0xe9" : : "a"(value));
}
static void debug_string(const char *text) {
  while (*text) debug_byte((uint8_t)*text++);
}
static inline void qemu_exit(uint32_t value) {
  __asm__ volatile("outl %0, $0xf4" : : "a"(value));
}

__attribute__((noreturn))
void aiueos_kernel_entry(const struct aiueos_boot_info *boot) {
  if (!boot || boot->magic != 0x414955454f53424fULL || boot->version != 1 ||
      !boot->memory_map || !boot->memory_map_size || !boot->descriptor_size) {
    debug_string("AIUEOS_KERNEL_FAIL boot-info\n");
    qemu_exit(0x7e);
  } else {
    debug_string("AIUEOS_KERNEL_OK memory-map-v1\n");
    qemu_exit(0x20);
  }
  for (;;) __asm__ volatile("cli; hlt");
}

