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
struct efi_configuration_table { struct efi_guid vendor_guid; void *vendor_table; };

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
  void *acpi_rsdp;
  uint64_t framebuffer_base, framebuffer_size;
  uint32_t framebuffer_width, framebuffer_height, framebuffer_stride, framebuffer_format;
};
typedef void(SYSVABI *kernel_entry)(const struct aiueos_boot_info *);
extern const uint8_t aiueos_expected_kernel_sha256[32];

static const struct efi_guid loaded_image_guid =
  {0x5b1b31a1, 0x9562, 0x11d2, {0x8e,0x3f,0x00,0xa0,0xc9,0x69,0x72,0x3b}};
static const struct efi_guid simple_fs_guid =
  {0x964e5b22, 0x6459, 0x11d2, {0x8e,0x39,0x00,0xa0,0xc9,0x69,0x72,0x3b}};
static const struct efi_guid acpi20_guid =
  {0x8868e871, 0xe4f1, 0x11d3, {0xbc,0x22,0x00,0x80,0xc7,0x3c,0x88,0x81}};
static const struct efi_guid graphics_output_guid =
  {0x9042a9de, 0x23dc, 0x4a38, {0x96,0xfb,0x7a,0xde,0xd0,0x80,0x51,0x6a}};

struct efi_graphics_output_mode_info {
  uint32_t version, horizontal_resolution, vertical_resolution, pixel_format;
  uint32_t pixel_information[4], pixels_per_scan_line;
};
struct efi_graphics_output_mode {
  uint32_t max_mode, mode; struct efi_graphics_output_mode_info *info;
  uint64_t size_of_info, framebuffer_base, framebuffer_size;
};
struct efi_graphics_output_protocol {
  void *query_mode, *set_mode, *blt; struct efi_graphics_output_mode *mode;
};

static int guid_equal(const struct efi_guid *a, const struct efi_guid *b) {
  const uint8_t *x = (const uint8_t *)a, *y = (const uint8_t *)b;
  for (uint64_t i = 0; i < sizeof(*a); i++) if (x[i] != y[i]) return 0;
  return 1;
}

static void copy_bytes(void *to, const void *from, uint64_t size) {
  uint8_t *d = to; const uint8_t *s = from; while (size--) *d++ = *s++;
}
static void zero_bytes(void *to, uint64_t size) { uint8_t *d = to; while (size--) *d++ = 0; }
static uint32_t rotate_right(uint32_t value, uint32_t bits) {
  return (value >> bits) | (value << (32 - bits));
}
static void sha256(const uint8_t *input, uint64_t size, uint8_t output[32]) {
  static const uint32_t constants[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
  };
  uint32_t state[8] = {0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
                       0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
  uint8_t block[64]; uint64_t offset = 0, total_bits = size * 8;
  for (;;) {
    uint64_t remaining = size - offset;
    uint64_t take = remaining > 64 ? 64 : remaining;
    for (uint64_t i = 0; i < take; i++) block[i] = input[offset + i];
    offset += take;
    if (take < 64) {
      block[take++] = 0x80;
      if (take > 56) {
        while (take < 64) block[take++] = 0;
      } else {
        while (take < 56) block[take++] = 0;
        for (int i = 7; i >= 0; i--) block[take++] = (uint8_t)(total_bits >> (i * 8));
      }
    }
    uint32_t words[64];
    for (uint32_t i = 0; i < 16; i++) words[i] = ((uint32_t)block[i*4] << 24) |
      ((uint32_t)block[i*4+1] << 16) | ((uint32_t)block[i*4+2] << 8) | block[i*4+3];
    for (uint32_t i = 16; i < 64; i++) {
      uint32_t s0 = rotate_right(words[i-15],7) ^ rotate_right(words[i-15],18) ^ (words[i-15] >> 3);
      uint32_t s1 = rotate_right(words[i-2],17) ^ rotate_right(words[i-2],19) ^ (words[i-2] >> 10);
      words[i] = words[i-16] + s0 + words[i-7] + s1;
    }
    uint32_t a=state[0],b=state[1],c=state[2],d=state[3],e=state[4],f=state[5],g=state[6],h=state[7];
    for (uint32_t i = 0; i < 64; i++) {
      uint32_t s1=rotate_right(e,6)^rotate_right(e,11)^rotate_right(e,25);
      uint32_t choice=(e&f)^((~e)&g), t1=h+s1+choice+constants[i]+words[i];
      uint32_t s0=rotate_right(a,2)^rotate_right(a,13)^rotate_right(a,22);
      uint32_t majority=(a&b)^(a&c)^(b&c), t2=s0+majority;
      h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    state[0]+=a;state[1]+=b;state[2]+=c;state[3]+=d;state[4]+=e;state[5]+=f;state[6]+=g;state[7]+=h;
    if (remaining < 64) {
      if (take == 64 && block[56] != (uint8_t)(total_bits >> 56) && remaining >= 56) {
        for (uint32_t i=0;i<56;i++) block[i]=0;
        for (int i=7;i>=0;i--) block[56+(7-i)]=(uint8_t)(total_bits>>(i*8));
        uint32_t w2[64];
        for(uint32_t i=0;i<16;i++) w2[i]=((uint32_t)block[i*4]<<24)|((uint32_t)block[i*4+1]<<16)|((uint32_t)block[i*4+2]<<8)|block[i*4+3];
        for(uint32_t i=16;i<64;i++){uint32_t x=rotate_right(w2[i-15],7)^rotate_right(w2[i-15],18)^(w2[i-15]>>3);uint32_t y=rotate_right(w2[i-2],17)^rotate_right(w2[i-2],19)^(w2[i-2]>>10);w2[i]=w2[i-16]+x+w2[i-7]+y;}
        a=state[0];b=state[1];c=state[2];d=state[3];e=state[4];f=state[5];g=state[6];h=state[7];
        for(uint32_t i=0;i<64;i++){uint32_t x=rotate_right(e,6)^rotate_right(e,11)^rotate_right(e,25);uint32_t t1=h+x+((e&f)^((~e)&g))+constants[i]+w2[i];uint32_t t2=(rotate_right(a,2)^rotate_right(a,13)^rotate_right(a,22))+((a&b)^(a&c)^(b&c));h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;}
        state[0]+=a;state[1]+=b;state[2]+=c;state[3]+=d;state[4]+=e;state[5]+=f;state[6]+=g;state[7]+=h;
      }
      break;
    }
  }
  for(uint32_t i=0;i<8;i++){output[i*4]=(uint8_t)(state[i]>>24);output[i*4+1]=(uint8_t)(state[i]>>16);output[i*4+2]=(uint8_t)(state[i]>>8);output[i*4+3]=(uint8_t)state[i];}
}
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
  struct efi_graphics_output_protocol *gop = 0;

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
  uint8_t kernel_digest[32]; sha256(kernel_file, kernel_size, kernel_digest);
  for (uint32_t i = 0; i < 32; i++) if (kernel_digest[i] != aiueos_expected_kernel_sha256[i])
    return fail("AIUEOS_LOADER_FAIL kernel-sha256");
  debug_string("AIUEOS_LOADER_INTEGRITY_OK sha256-v1\n");

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
  info.acpi_rsdp = 0;
  struct efi_configuration_table *tables = system->configuration_table;
  for (uint64_t i = 0; i < system->number_of_table_entries; i++) {
    if (guid_equal(&tables[i].vendor_guid, &acpi20_guid)) {
      info.acpi_rsdp = tables[i].vendor_table;
      break;
    }
  }
  if (!info.acpi_rsdp) return fail("AIUEOS_LOADER_FAIL acpi-rsdp");

  if (bs->handle_protocol(system->console_out_handle, &graphics_output_guid,
                          (void **)&gop) != EFI_SUCCESS || !gop || !gop->mode ||
      !gop->mode->info || !gop->mode->framebuffer_base ||
      !gop->mode->framebuffer_size)
    return fail("AIUEOS_LOADER_FAIL gop");
  struct efi_graphics_output_mode_info *gop_info = gop->mode->info;
  if (!gop_info->horizontal_resolution || !gop_info->vertical_resolution ||
      gop_info->pixels_per_scan_line < gop_info->horizontal_resolution ||
      (gop_info->pixel_format != 0 && gop_info->pixel_format != 1) ||
      (uint64_t)gop_info->pixels_per_scan_line * gop_info->vertical_resolution >
        gop->mode->framebuffer_size / 4)
    return fail("AIUEOS_LOADER_FAIL gop-mode");
  info.framebuffer_base = gop->mode->framebuffer_base;
  info.framebuffer_size = gop->mode->framebuffer_size;
  info.framebuffer_width = gop_info->horizontal_resolution;
  info.framebuffer_height = gop_info->vertical_resolution;
  info.framebuffer_stride = gop_info->pixels_per_scan_line;
  info.framebuffer_format = gop_info->pixel_format;
  debug_string("AIUEOS_GOP_HANDOFF_OK framebuffer-v1\n");

  status = bs->exit_boot_services(image, map_key);
  if (status != EFI_SUCCESS) return fail("AIUEOS_LOADER_FAIL exit-boot-services");
  ((kernel_entry)(uintptr_t)elf->entry)(&info);
  for (;;) __asm__ volatile("hlt");
}
