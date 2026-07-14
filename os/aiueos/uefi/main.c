#include <stdint.h>
#include <stddef.h>

#define EFIAPI __attribute__((ms_abi))
#define SYSVABI __attribute__((sysv_abi))
#define EFI_SUCCESS 0
#define EFI_BUFFER_TOO_SMALL ((uint64_t)0x8000000000000005ULL)
#define EFI_INVALID_PARAMETER ((uint64_t)0x8000000000000002ULL)
#define PAGE_SIZE 4096ULL
#define KERNEL_BUFFER_SIZE (1024ULL * 1024ULL)
#define MEMORY_MAP_BUFFER_SIZE (128ULL * 1024ULL)

typedef uint64_t efi_status;
typedef void *efi_handle;
typedef uint16_t char16;

struct efi_guid { uint32_t a; uint16_t b, c; uint8_t d[8]; };
struct efi_table_header { uint64_t signature; uint32_t revision, header_size, crc32, reserved; };
struct efi_simple_text_output;
typedef efi_status(EFIAPI *efi_output_string)(struct efi_simple_text_output *, const char16 *);
struct efi_simple_text_output {
  void *reset; efi_output_string output_string; void *rest[8];
};

typedef efi_status(EFIAPI *efi_allocate_pages)(uint32_t, uint32_t, uint64_t, uint64_t *);
typedef efi_status(EFIAPI *efi_get_memory_map)(uint64_t *, void *, uint64_t *, uint64_t *, uint32_t *);
typedef efi_status(EFIAPI *efi_allocate_pool)(uint32_t, uint64_t, void **);
typedef efi_status(EFIAPI *efi_free_pool)(void *);
typedef efi_status(EFIAPI *efi_handle_protocol)(efi_handle, const struct efi_guid *, void **);
typedef efi_status(EFIAPI *efi_exit_boot_services)(efi_handle, uint64_t);

struct efi_boot_services {
  struct efi_table_header header;
  void *raise_tpl, *restore_tpl;
  efi_allocate_pages allocate_pages;
  void *free_pages;
  efi_get_memory_map get_memory_map;
  efi_allocate_pool allocate_pool;
  efi_free_pool free_pool;
  void *create_event, *set_timer, *wait_for_event, *signal_event, *close_event, *check_event;
  void *install_protocol_interface, *reinstall_protocol_interface, *uninstall_protocol_interface;
  efi_handle_protocol handle_protocol;
  void *reserved, *register_protocol_notify, *locate_handle, *locate_device_path;
  void *install_configuration_table, *load_image, *start_image, *exit, *unload_image;
  efi_exit_boot_services exit_boot_services;
};

struct efi_system_table {
  struct efi_table_header header;
  char16 *firmware_vendor; uint32_t firmware_revision, padding;
  efi_handle console_in_handle; void *console_in;
  efi_handle console_out_handle; struct efi_simple_text_output *console_out;
  efi_handle standard_error_handle; struct efi_simple_text_output *standard_error;
  void *runtime_services; struct efi_boot_services *boot_services;
  uint64_t number_of_table_entries; void *configuration_table;
};

struct efi_loaded_image {
  uint32_t revision, padding; efi_handle parent_handle;
  struct efi_system_table *system_table; efi_handle device_handle;
  void *file_path, *reserved; uint32_t load_options_size, padding2;
  void *load_options, *image_base; uint64_t image_size;
  uint32_t image_code_type, image_data_type; void *unload;
};

struct efi_file;
typedef efi_status(EFIAPI *efi_file_open)(struct efi_file *, struct efi_file **, const char16 *, uint64_t, uint64_t);
typedef efi_status(EFIAPI *efi_file_close)(struct efi_file *);
typedef efi_status(EFIAPI *efi_file_read)(struct efi_file *, uint64_t *, void *);
struct efi_file {
  uint64_t revision; efi_file_open open; efi_file_close close;
  void *delete_file; efi_file_read read; void *write, *get_position, *set_position;
  void *get_info, *set_info, *flush;
};
struct efi_simple_file_system {
  uint64_t revision;
  efi_status(EFIAPI *open_volume)(struct efi_simple_file_system *, struct efi_file **);
};

struct elf64_header {
  uint8_t ident[16]; uint16_t type, machine; uint32_t version;
  uint64_t entry, phoff, shoff; uint32_t flags; uint16_t ehsize, phentsize, phnum;
  uint16_t shentsize, shnum, shstrndx;
};
struct elf64_program_header {
  uint32_t type, flags; uint64_t offset, vaddr, paddr, filesz, memsz, align;
};

struct aiueos_boot_info {
  uint64_t magic, version;
  void *memory_map; uint64_t memory_map_size, descriptor_size, descriptor_version;
};
typedef void(SYSVABI *kernel_entry)(const struct aiueos_boot_info *);

static const struct efi_guid loaded_image_guid =
  {0x5b1b31a1, 0x9562, 0x11d2, {0x8e,0x3f,0x00,0xa0,0xc9,0x69,0x72,0x3b}};
static const struct efi_guid simple_fs_guid =
  {0x964e5b22, 0x6459, 0x11d2, {0x8e,0x39,0x00,0xa0,0xc9,0x69,0x72,0x3b}};

static void copy_bytes(void *to, const void *from, uint64_t size) {
  uint8_t *d = to; const uint8_t *s = from; while (size--) *d++ = *s++;
}
static void zero_bytes(void *to, uint64_t size) { uint8_t *d = to; while (size--) *d++ = 0; }
static inline void debug_byte(uint8_t value) { __asm__ volatile("outb %0, $0xe9" : : "a"(value)); }
static void debug_string(const char *text) { while (*text) debug_byte((uint8_t)*text++); }
static inline void fail_exit(void) { __asm__ volatile("outl %0, $0xf4" : : "a"(0x7f)); }
static efi_status fail(const char *message) { debug_string(message); debug_byte('\n'); fail_exit(); return EFI_INVALID_PARAMETER; }

efi_status EFIAPI efi_main(efi_handle image, struct efi_system_table *system) {
  static const char16 console_message[] = u"AIUEOS_LOADER_OK loading kernel.elf\r\n";
  static const char16 kernel_path[] = u"\\EFI\\AIUEOS\\KERNEL.ELF";
  struct efi_boot_services *bs;
  struct efi_loaded_image *loaded = 0;
  struct efi_simple_file_system *fs = 0;
  struct efi_file *root = 0, *file = 0;
  uint8_t *kernel_file = 0;
  void *memory_map = 0;
  uint64_t kernel_size = KERNEL_BUFFER_SIZE;
  uint64_t memory_map_size, map_key, descriptor_size;
  uint32_t descriptor_version;
  struct aiueos_boot_info info;

  if (!system || !(bs = system->boot_services)) return fail("AIUEOS_LOADER_FAIL system-table");
  if (system->console_out && system->console_out->output_string)
    system->console_out->output_string(system->console_out, console_message);
  debug_string("AIUEOS_LOADER_OK\n");

  if (bs->handle_protocol(image, &loaded_image_guid, (void **)&loaded) != EFI_SUCCESS || !loaded)
    return fail("AIUEOS_LOADER_FAIL loaded-image");
  if (bs->handle_protocol(loaded->device_handle, &simple_fs_guid, (void **)&fs) != EFI_SUCCESS || !fs)
    return fail("AIUEOS_LOADER_FAIL filesystem");
  if (fs->open_volume(fs, &root) != EFI_SUCCESS || !root)
    return fail("AIUEOS_LOADER_FAIL volume");
  if (root->open(root, &file, kernel_path, 1, 0) != EFI_SUCCESS || !file)
    return fail("AIUEOS_LOADER_FAIL kernel-open");
  if (bs->allocate_pool(2, KERNEL_BUFFER_SIZE, (void **)&kernel_file) != EFI_SUCCESS)
    return fail("AIUEOS_LOADER_FAIL kernel-buffer");
  if (file->read(file, &kernel_size, kernel_file) != EFI_SUCCESS)
    return fail("AIUEOS_LOADER_FAIL kernel-read");
  file->close(file); root->close(root);

  if (kernel_size < sizeof(struct elf64_header)) return fail("AIUEOS_LOADER_FAIL elf-size");
  struct elf64_header *elf = (struct elf64_header *)kernel_file;
  if (elf->ident[0] != 0x7f || elf->ident[1] != 'E' || elf->ident[2] != 'L' ||
      elf->ident[3] != 'F' || elf->ident[4] != 2 || elf->machine != 62 ||
      elf->phentsize != sizeof(struct elf64_program_header))
    return fail("AIUEOS_LOADER_FAIL elf-header");
  if (elf->phoff > kernel_size || elf->phnum > 32 ||
      elf->phoff + (uint64_t)elf->phnum * elf->phentsize > kernel_size)
    return fail("AIUEOS_LOADER_FAIL elf-program-table");

  struct elf64_program_header *ph = (void *)(kernel_file + elf->phoff);
  uint8_t entry_is_executable = 0;
  for (uint16_t i = 0; i < elf->phnum; i++) {
    if (ph[i].type != 1) continue;
    if (ph[i].filesz > ph[i].memsz || ph[i].offset > kernel_size ||
        ph[i].filesz > kernel_size - ph[i].offset ||
        ph[i].paddr < 0x100000 || ph[i].paddr > UINT64_MAX - ph[i].memsz ||
        (ph[i].paddr & (PAGE_SIZE - 1)) != 0)
      return fail("AIUEOS_LOADER_FAIL elf-segment");
    if ((ph[i].flags & 1) && elf->entry >= ph[i].paddr &&
        elf->entry - ph[i].paddr < ph[i].memsz) entry_is_executable = 1;
    uint64_t address = ph[i].paddr;
    uint64_t pages = (ph[i].memsz + PAGE_SIZE - 1) / PAGE_SIZE;
    if (!pages || bs->allocate_pages(2, 2, pages, &address) != EFI_SUCCESS || address != ph[i].paddr)
      return fail("AIUEOS_LOADER_FAIL segment-allocation");
    copy_bytes((void *)(uintptr_t)address, kernel_file + ph[i].offset, ph[i].filesz);
    zero_bytes((void *)(uintptr_t)(address + ph[i].filesz), ph[i].memsz - ph[i].filesz);
  }
  if (!entry_is_executable) return fail("AIUEOS_LOADER_FAIL elf-entry");

  if (bs->allocate_pool(2, MEMORY_MAP_BUFFER_SIZE, &memory_map) != EFI_SUCCESS)
    return fail("AIUEOS_LOADER_FAIL map-buffer");
  memory_map_size = MEMORY_MAP_BUFFER_SIZE;
  efi_status status = bs->get_memory_map(&memory_map_size, memory_map, &map_key,
                                         &descriptor_size, &descriptor_version);
  if (status != EFI_SUCCESS) return fail("AIUEOS_LOADER_FAIL memory-map");
  info.magic = 0x414955454f53424fULL; info.version = 1;
  info.memory_map = memory_map; info.memory_map_size = memory_map_size;
  info.descriptor_size = descriptor_size; info.descriptor_version = descriptor_version;

  status = bs->exit_boot_services(image, map_key);
  if (status != EFI_SUCCESS) return fail("AIUEOS_LOADER_FAIL exit-boot-services");
  ((kernel_entry)(uintptr_t)elf->entry)(&info);
  for (;;) __asm__ volatile("hlt");
}
