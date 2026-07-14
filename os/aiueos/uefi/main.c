#include <stdint.h>

#if !defined(__x86_64__)
#error "The Phase 1 UEFI loader currently supports x86_64 only"
#endif

#define EFIAPI __attribute__((ms_abi))

typedef uint64_t efi_status;
typedef void *efi_handle;
typedef uint16_t char16;

struct efi_simple_text_output;
typedef efi_status(EFIAPI *efi_output_string)(struct efi_simple_text_output *,
                                              const char16 *);

struct efi_simple_text_output {
  void *reset;
  efi_output_string output_string;
  void *test_string;
  void *query_mode;
  void *set_mode;
  void *set_attribute;
  void *clear_screen;
  void *set_cursor_position;
  void *enable_cursor;
  void *mode;
};

struct efi_table_header {
  uint64_t signature;
  uint32_t revision;
  uint32_t header_size;
  uint32_t crc32;
  uint32_t reserved;
};

struct efi_system_table {
  struct efi_table_header header;
  char16 *firmware_vendor;
  uint32_t firmware_revision;
  uint32_t padding;
  efi_handle console_in_handle;
  void *console_in;
  efi_handle console_out_handle;
  struct efi_simple_text_output *console_out;
  efi_handle standard_error_handle;
  struct efi_simple_text_output *standard_error;
  void *runtime_services;
  void *boot_services;
  uint64_t number_of_table_entries;
  void *configuration_table;
};

static inline void debug_byte(uint8_t value) {
  __asm__ volatile("outb %0, $0xe9" : : "a"(value));
}

static void debug_string(const char *text) {
  while (*text != '\0') {
    debug_byte((uint8_t)*text++);
  }
}

static inline void qemu_exit(uint32_t value) {
  __asm__ volatile("outl %0, $0xf4" : : "a"(value));
}

efi_status EFIAPI efi_main(efi_handle image, struct efi_system_table *system) {
  static const char16 message[] =
      u"AIUEOS_BOOT_OK x86_64-uefi boot-contract-v1\r\n";
  (void)image;

  if (system != 0 && system->console_out != 0 &&
      system->console_out->output_string != 0) {
    system->console_out->output_string(system->console_out, message);
  }
  debug_string("AIUEOS_BOOT_OK x86_64-uefi boot-contract-v1\n");
  qemu_exit(0x10);
  return 0;
}

