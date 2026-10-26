#include <stdint.h>
#include <stddef.h>
#include "../include/boot_info.h"
#if defined(AIUEOS_QWEN38_MODEL_HANDOFF) || defined(AIUEOS_MODEL_NVME_SLOTS)
#include "aiueos-model-identity.h"
#endif
#ifdef AIUEOS_MODEL_NVME_SLOTS
#include "model_slots.h"
#endif

#define EFIAPI __attribute__((ms_abi))
#define SYSVABI __attribute__((sysv_abi))
#define EFI_SUCCESS 0
#define EFI_BUFFER_TOO_SMALL ((uint64_t)0x8000000000000005ULL)
#define EFI_INVALID_PARAMETER ((uint64_t)0x8000000000000002ULL)
#define EFI_BY_PROTOCOL 2
#define EFI_VARIABLE_NON_VOLATILE 1U
#define EFI_VARIABLE_BOOTSERVICE_ACCESS 2U
#define EFI_VARIABLE_RUNTIME_ACCESS 4U
#define PAGE_SIZE 4096ULL
#define KERNEL_BUFFER_SIZE (1024ULL * 1024ULL)
#define INITRAMFS_BUFFER_SIZE (1024ULL * 1024ULL)
#define MEMORY_MAP_BUFFER_SIZE (128ULL * 1024ULL)
#define EFI_ALLOCATE_MAX_ADDRESS 1U
#define EFI_LOADER_DATA 2U
#define ACPI_IDENTITY_LIMIT 0x40000000ULL
#define ACPI_RETAIN_RSDP_BYTES PAGE_SIZE
#define ACPI_RETAIN_ROOT_BYTES PAGE_SIZE
#define ACPI_RETAIN_TABLE_BYTES (64ULL * 1024ULL)
#define ACPI_RETAIN_BYTES (ACPI_RETAIN_RSDP_BYTES + ACPI_RETAIN_ROOT_BYTES + \
                           2ULL * ACPI_RETAIN_TABLE_BYTES)
#define ACPI_MAX_ROOT_ENTRIES 128U

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
typedef efi_status(EFIAPI *efi_free_pages)(uint64_t, uint64_t);
typedef efi_status(EFIAPI *efi_get_memory_map)(uint64_t *, void *, uint64_t *, uint64_t *, uint32_t *);
typedef efi_status(EFIAPI *efi_allocate_pool)(uint32_t, uint64_t, void **);
typedef efi_status(EFIAPI *efi_free_pool)(void *);
typedef efi_status(EFIAPI *efi_handle_protocol)(efi_handle, const struct efi_guid *, void **);
typedef efi_status(EFIAPI *efi_locate_handle)(uint32_t, const struct efi_guid *, void *,
                                              uint64_t *, efi_handle *);
typedef efi_status(EFIAPI *efi_exit_boot_services)(efi_handle, uint64_t);
typedef efi_status(EFIAPI *efi_set_watchdog_timer)(uint64_t, uint64_t, uint64_t,
                                                   const char16 *);
typedef efi_status(EFIAPI *efi_stall)(uint64_t);

struct efi_boot_services {
  struct efi_table_header header;
  void *raise_tpl, *restore_tpl;
  efi_allocate_pages allocate_pages;
  efi_free_pages free_pages;
  efi_get_memory_map get_memory_map;
  efi_allocate_pool allocate_pool;
  efi_free_pool free_pool;
  void *create_event, *set_timer, *wait_for_event, *signal_event, *close_event, *check_event;
  void *install_protocol_interface, *reinstall_protocol_interface, *uninstall_protocol_interface;
  efi_handle_protocol handle_protocol;
  void *reserved, *register_protocol_notify;
  efi_locate_handle locate_handle;
  void *locate_device_path;
  void *install_configuration_table, *load_image, *start_image, *exit, *unload_image;
  efi_exit_boot_services exit_boot_services;
  void *get_next_monotonic_count;
  efi_stall stall;
  efi_set_watchdog_timer set_watchdog_timer;
};

typedef efi_status(EFIAPI *efi_set_variable)(const char16 *, const struct efi_guid *,
                                             uint32_t, uint64_t, void *);
typedef efi_status(EFIAPI *efi_get_variable)(const char16 *, const struct efi_guid *,
                                             uint32_t *, uint64_t *, void *);
struct efi_runtime_services {
  struct efi_table_header header;
  void *get_time, *set_time, *get_wakeup_time, *set_wakeup_time;
  void *set_virtual_address_map, *convert_pointer;
  efi_get_variable get_variable;
  void *get_next_variable_name;
  efi_set_variable set_variable;
  void *get_next_high_monotonic_count, *reset_system;
};
struct efi_system_table {
  struct efi_table_header header;
  char16 *firmware_vendor; uint32_t firmware_revision, padding;
  efi_handle console_in_handle; void *console_in;
  efi_handle console_out_handle; struct efi_simple_text_output *console_out;
  efi_handle standard_error_handle; struct efi_simple_text_output *standard_error;
  struct efi_runtime_services *runtime_services; struct efi_boot_services *boot_services;
  uint64_t number_of_table_entries; void *configuration_table;
};
struct efi_configuration_table { struct efi_guid vendor_guid; void *vendor_table; };

struct __attribute__((packed)) acpi_rsdp_v2 {
  char signature[8]; uint8_t checksum; char oem_id[6]; uint8_t revision;
  uint32_t rsdt_address, length; uint64_t xsdt_address;
  uint8_t extended_checksum, reserved[3];
};
struct __attribute__((packed)) acpi_sdt_header {
  char signature[4]; uint32_t length; uint8_t revision, checksum;
  char oem_id[6], oem_table_id[8];
  uint32_t oem_revision, creator_id, creator_revision;
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
typedef efi_status(EFIAPI *efi_file_write)(struct efi_file *, uint64_t *, void *);
typedef efi_status(EFIAPI *efi_file_set_position)(struct efi_file *, uint64_t);
typedef efi_status(EFIAPI *efi_file_delete)(struct efi_file *);
struct efi_file {
  uint64_t revision; efi_file_open open; efi_file_close close;
  efi_file_delete delete_file; efi_file_read read; efi_file_write write;
  void *get_position; efi_file_set_position set_position;
  void *get_info, *set_info, *flush;
};
struct efi_simple_file_system {
  uint64_t revision;
  efi_status(EFIAPI *open_volume)(struct efi_simple_file_system *, struct efi_file **);
};

#ifdef AIUEOS_MODEL_NVME_SLOTS
struct efi_block_io_media {
  uint32_t media_id;
  uint8_t removable_media, media_present, logical_partition, read_only, write_caching;
  uint8_t padding[3];
  uint32_t block_size, io_align;
  uint64_t last_block, lowest_aligned_lba;
  uint32_t logical_blocks_per_physical_block;
  uint32_t optimal_transfer_length_granularity;
};
struct efi_block_io;
typedef efi_status(EFIAPI *efi_block_reset)(struct efi_block_io *, uint8_t);
typedef efi_status(EFIAPI *efi_block_read)(struct efi_block_io *, uint32_t,
                                           uint64_t, uint64_t, void *);
typedef efi_status(EFIAPI *efi_block_write)(struct efi_block_io *, uint32_t,
                                            uint64_t, uint64_t, const void *);
typedef efi_status(EFIAPI *efi_block_flush)(struct efi_block_io *);
struct efi_block_io {
  uint64_t revision;
  struct efi_block_io_media *media;
  efi_block_reset reset;
  efi_block_read read_blocks;
  efi_block_write write_blocks;
  efi_block_flush flush_blocks;
};
struct efi_device_path_node { uint8_t type, subtype, length[2]; };
#endif

struct elf64_header {
  uint8_t ident[16]; uint16_t type, machine; uint32_t version;
  uint64_t entry, phoff, shoff; uint32_t flags; uint16_t ehsize, phentsize, phnum;
  uint16_t shentsize, shnum, shstrndx;
};
struct elf64_program_header {
  uint32_t type, flags; uint64_t offset, vaddr, paddr, filesz, memsz, align;
};

struct aiueos_qualification_record {
  uint32_t magic;
  uint16_t version, state;
  uint32_t code, reserved;
};
typedef void(SYSVABI *kernel_entry)(const struct aiueos_boot_info *);
extern const uint8_t aiueos_expected_kernel_sha256[32];
extern const uint8_t aiueos_expected_initramfs_sha256[32];

static const struct efi_guid loaded_image_guid =
  {0x5b1b31a1, 0x9562, 0x11d2, {0x8e,0x3f,0x00,0xa0,0xc9,0x69,0x72,0x3b}};
static const struct efi_guid simple_fs_guid =
  {0x964e5b22, 0x6459, 0x11d2, {0x8e,0x39,0x00,0xa0,0xc9,0x69,0x72,0x3b}};
#ifdef AIUEOS_MODEL_NVME_SLOTS
static const struct efi_guid block_io_guid =
  {0x964e5b21, 0x6459, 0x11d2, {0x8e,0x39,0x00,0xa0,0xc9,0x69,0x72,0x3b}};
static const struct efi_guid device_path_guid =
  {0x09576e91, 0x6d3f, 0x11d2, {0x8e,0x39,0x00,0xa0,0xc9,0x69,0x72,0x3b}};
#endif
static const struct efi_guid acpi20_guid =
  {0x8868e871, 0xe4f1, 0x11d3, {0xbc,0x22,0x00,0x80,0xc7,0x3c,0x88,0x81}};
static const struct efi_guid graphics_output_guid =
  {0x9042a9de, 0x23dc, 0x4a38, {0x96,0xfb,0x7a,0xde,0xd0,0x80,0x51,0x6a}};
static const struct efi_guid qualification_guid =
  {0x73953a72,0x6627,0x4b62,{0x9a,0x9c,0x10,0x38,0xd9,0x20,0x9a,0x16}};
static const struct efi_guid global_variable_guid =
  {0x8be4df61,0x93ca,0x11d2,{0xaa,0x0d,0x00,0xe0,0x98,0x03,0x2b,0x8c}};
static const char16 qualification_name[] = u"AIUEOSQualificationResult";
static const char16 boot_current_name[] = u"BootCurrent";
static const char16 boot_next_name[] = u"BootNext";

#ifdef AIUEOS_EMBEDDED_RELEASE
extern const uint8_t aiueos_embedded_kernel_start[];
extern const uint8_t aiueos_embedded_kernel_end[];
extern const uint8_t aiueos_embedded_initramfs_start[];
extern const uint8_t aiueos_embedded_initramfs_end[];
#endif

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

static struct efi_graphics_output_protocol *find_graphics_output(
    struct efi_system_table *system, struct efi_boot_services *bs,
    uint8_t *used_protocol_scan) {
  struct efi_graphics_output_protocol *gop=0;
#ifndef AIUEOS_GOP_FORCE_PROTOCOL_SCAN
  if (system->console_out_handle &&
      bs->handle_protocol(system->console_out_handle,&graphics_output_guid,
                          (void **)&gop)==EFI_SUCCESS && gop)
    return gop;
#endif
  efi_handle handles[32];uint64_t bytes=sizeof(handles);
  if (bs->locate_handle(EFI_BY_PROTOCOL,&graphics_output_guid,0,&bytes,handles)!=EFI_SUCCESS)
    return 0;
  uint64_t count=bytes/sizeof(efi_handle);
  for (uint64_t i=0;i<count;i++) {
    gop=0;
    if (bs->handle_protocol(handles[i],&graphics_output_guid,(void **)&gop)==EFI_SUCCESS && gop) {
      *used_protocol_scan=1;
      return gop;
    }
  }
  return 0;
}

static int guid_equal(const struct efi_guid *a, const struct efi_guid *b) {
  const uint8_t *x = (const uint8_t *)a, *y = (const uint8_t *)b;
  for (uint64_t i = 0; i < sizeof(*a); i++) if (x[i] != y[i]) return 0;
  return 1;
}

static uint64_t read_cr3(void) {
  uint64_t value;
  __asm__ volatile("mov %%cr3, %0" : "=r"(value));
  return value;
}

static uint64_t read_tsc(void) {
  uint32_t low, high;
  __asm__ volatile("rdtsc" : "=a"(low), "=d"(high));
  return ((uint64_t)high << 32) | low;
}

static void copy_bytes(void *to, const void *from, uint64_t size) {
  uint8_t *d = to; const uint8_t *s = from; while (size--) *d++ = *s++;
}
static void zero_bytes(void *to, uint64_t size) { uint8_t *d = to; while (size--) *d++ = 0; }

static int acpi_bytes_equal(const char *left, const char *right,
                            uint64_t bytes) {
  while (bytes--) if (*left++ != *right++) return 0;
  return 1;
}

static int acpi_checksum_ok(const void *table, uint64_t bytes) {
  if (!table || !bytes || bytes > ACPI_RETAIN_TABLE_BYTES) return 0;
  const uint8_t *input=table;
  uint8_t sum=0;
  while (bytes--) sum=(uint8_t)(sum+*input++);
  return sum==0;
}

static uint8_t acpi_checksum_value(const void *table, uint64_t bytes) {
  const uint8_t *input=table;
  uint8_t sum=0;
  while (bytes--) sum=(uint8_t)(sum+*input++);
  return (uint8_t)(0U-sum);
}

static int acpi_source_address_sane(uint64_t address, uint64_t bytes) {
  return address && bytes && address < (1ULL << 52) &&
         address <= (1ULL << 52) - bytes;
}

/* Firmware can place ACPI reclaim memory well above the kernel's intentionally
   small bootstrap identity map (the physical K16 places it around 0x92f00000).
   Before ExitBootServices, validate the source graph and relocate only the two
   tables this kernel consumes into LoaderData below 1 GiB.  The synthetic XSDT
   is checksummed again and contains only APIC plus optional DMAR, so the kernel
   still runs its Kotoba admission over every table it is asked to trust. */
static void *retain_acpi_graph(struct efi_boot_services *bs,
                               const void *rsdp_pointer) {
  if (!bs || !bs->allocate_pages || !rsdp_pointer) return 0;
  const struct acpi_rsdp_v2 *source_rsdp=rsdp_pointer;
  if (!acpi_bytes_equal(source_rsdp->signature,"RSD PTR ",8) ||
      source_rsdp->revision<2 || source_rsdp->length<sizeof(*source_rsdp) ||
      source_rsdp->length>ACPI_RETAIN_RSDP_BYTES ||
      !acpi_checksum_ok(source_rsdp,20) ||
      !acpi_checksum_ok(source_rsdp,source_rsdp->length) ||
      !acpi_source_address_sane(source_rsdp->xsdt_address,
                                sizeof(struct acpi_sdt_header))) return 0;

  const struct acpi_sdt_header *source_root=
    (const void *)(uintptr_t)source_rsdp->xsdt_address;
  if (!acpi_bytes_equal(source_root->signature,"XSDT",4) ||
      source_root->length<sizeof(*source_root) ||
      source_root->length>ACPI_RETAIN_ROOT_BYTES ||
      (source_root->length-sizeof(*source_root))%8 ||
      !acpi_checksum_ok(source_root,source_root->length)) return 0;
  uint32_t entries=(source_root->length-sizeof(*source_root))/8;
  if (!entries || entries>ACPI_MAX_ROOT_ENTRIES) return 0;

  const struct acpi_sdt_header *source_madt=0,*source_dmar=0;
  const uint8_t *entry_bytes=(const uint8_t *)source_root+sizeof(*source_root);
  for (uint32_t index=0;index<entries;index++) {
    uint64_t address=*(const uint64_t *)(const void *)(entry_bytes+(uint64_t)index*8);
    if (!acpi_source_address_sane(address,sizeof(struct acpi_sdt_header))) return 0;
    const struct acpi_sdt_header *candidate=(const void *)(uintptr_t)address;
    if (!acpi_bytes_equal(candidate->signature,"APIC",4) &&
        !acpi_bytes_equal(candidate->signature,"DMAR",4)) continue;
    if (candidate->length<sizeof(*candidate) ||
        candidate->length>ACPI_RETAIN_TABLE_BYTES ||
        !acpi_source_address_sane(address,candidate->length) ||
        !acpi_checksum_ok(candidate,candidate->length)) return 0;
    if (acpi_bytes_equal(candidate->signature,"APIC",4)) {
      if (source_madt) return 0;
      source_madt=candidate;
    } else {
      if (source_dmar) return 0;
      source_dmar=candidate;
    }
  }
  if (!source_madt) return 0;

  uint64_t pages=(ACPI_RETAIN_BYTES+PAGE_SIZE-1)/PAGE_SIZE;
  uint64_t base=ACPI_IDENTITY_LIMIT-1;
  if (bs->allocate_pages(EFI_ALLOCATE_MAX_ADDRESS,EFI_LOADER_DATA,pages,&base)
        != EFI_SUCCESS || !base || base>=ACPI_IDENTITY_LIMIT ||
      base>ACPI_IDENTITY_LIMIT-pages*PAGE_SIZE) return 0;
  zero_bytes((void *)(uintptr_t)base,pages*PAGE_SIZE);

  struct acpi_rsdp_v2 *retained_rsdp=(void *)(uintptr_t)base;
  struct acpi_sdt_header *retained_root=
    (void *)(uintptr_t)(base+ACPI_RETAIN_RSDP_BYTES);
  struct acpi_sdt_header *retained_madt=
    (void *)(uintptr_t)(base+ACPI_RETAIN_RSDP_BYTES+ACPI_RETAIN_ROOT_BYTES);
  struct acpi_sdt_header *retained_dmar=
    (void *)(uintptr_t)(base+ACPI_RETAIN_RSDP_BYTES+ACPI_RETAIN_ROOT_BYTES+
                        ACPI_RETAIN_TABLE_BYTES);
  copy_bytes(retained_rsdp,source_rsdp,source_rsdp->length);
  copy_bytes(retained_root,source_root,sizeof(*retained_root));
  copy_bytes(retained_madt,source_madt,source_madt->length);
  if (source_dmar) copy_bytes(retained_dmar,source_dmar,source_dmar->length);

  uint64_t *retained_entries=(void *)((uint8_t *)retained_root+
                                      sizeof(*retained_root));
  retained_entries[0]=(uint64_t)(uintptr_t)retained_madt;
  uint32_t retained_entry_count=1;
  if (source_dmar)
    retained_entries[retained_entry_count++]=(uint64_t)(uintptr_t)retained_dmar;
  retained_root->length=sizeof(*retained_root)+retained_entry_count*8U;
  retained_root->checksum=0;
  retained_root->checksum=acpi_checksum_value(retained_root,retained_root->length);

  retained_rsdp->rsdt_address=0;
  retained_rsdp->xsdt_address=(uint64_t)(uintptr_t)retained_root;
  retained_rsdp->checksum=0;
  retained_rsdp->extended_checksum=0;
  retained_rsdp->checksum=acpi_checksum_value(retained_rsdp,20);
  retained_rsdp->extended_checksum=
    acpi_checksum_value(retained_rsdp,retained_rsdp->length);
  return retained_rsdp;
}

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
static void debug_hex32(uint32_t value) {
  static const char digits[] = "0123456789ABCDEF";
  for (int shift = 28; shift >= 0; shift -= 4) debug_byte((uint8_t)digits[(value >> shift) & 0xf]);
}
static inline void fail_exit(void) { __asm__ volatile("outl %0, $0xf4" : : "a"(0x7f)); }
static struct efi_simple_text_output *loader_console;
static struct efi_runtime_services *loader_runtime;

#ifndef AIUEOS_QUALIFICATION_LOADER_WATCHDOG_SECONDS
#define AIUEOS_QUALIFICATION_LOADER_WATCHDOG_SECONDS 90ULL
#endif

static void console_ascii(const char *text) {
  if (!loader_console || !loader_console->output_string) return;
  char16 wide[192];
  uint64_t i=0;
  while (text[i] && i+1<sizeof(wide)/sizeof(wide[0])) {
    wide[i]=(uint8_t)text[i];i++;
  }
  wide[i]=0;
  loader_console->output_string(loader_console,wide);
}

static void console_decimal(uint32_t value) {
  char text[16];uint32_t digits=0;
  do { text[digits++]=(char)('0'+value%10);value/=10; } while (value && digits<15);
  for (uint32_t i=0;i<digits/2;i++) {
    char tmp=text[i];text[i]=text[digits-1-i];text[digits-1-i]=tmp;
  }
  text[digits]=0;console_ascii(text);
}

static int persist_loader_record(uint16_t state, uint32_t code) {
  if (!loader_runtime || !loader_runtime->set_variable) return 0;
  struct aiueos_qualification_record record={0x514b3241U,2,state,code,0};
  return loader_runtime->set_variable(
      qualification_name,&qualification_guid,
      EFI_VARIABLE_NON_VOLATILE|EFI_VARIABLE_BOOTSERVICE_ACCESS|
        EFI_VARIABLE_RUNTIME_ACCESS,
      sizeof(record),&record)==EFI_SUCCESS;
}

static int persist_loader_failure(uint32_t code) {
  return persist_loader_record(2,code);
}

static int prepare_netboot_qualification_return(void) {
#ifdef AIUEOS_NETBOOT_QUALIFICATION
  if (!loader_runtime || !loader_runtime->get_variable ||
      !loader_runtime->set_variable) return 0;
  uint16_t boot_current=0;
  uint32_t attributes=0;
  uint64_t bytes=sizeof(boot_current);
  if (loader_runtime->get_variable(
          boot_current_name,&global_variable_guid,&attributes,&bytes,
          &boot_current)!=EFI_SUCCESS || bytes!=sizeof(boot_current)) return 0;
  attributes=EFI_VARIABLE_NON_VOLATILE|EFI_VARIABLE_BOOTSERVICE_ACCESS|
             EFI_VARIABLE_RUNTIME_ACCESS;
  if (loader_runtime->set_variable(
          boot_next_name,&global_variable_guid,attributes,sizeof(boot_current),
          &boot_current)!=EFI_SUCCESS) return 0;
  struct aiueos_qualification_record pending={0x514b3241U,2,0,0,0};
  if (loader_runtime->set_variable(
          qualification_name,&qualification_guid,attributes,sizeof(pending),
          &pending)!=EFI_SUCCESS) {
    loader_runtime->set_variable(
        boot_next_name,&global_variable_guid,0,0,0);
    return 0;
  }
  debug_string("AIUEOS_NETBOOT_RETURN_ARMED bootnext=current result=pending\n");
#endif
  return 1;
}

static void progress(uint32_t code, const char *message) {
  debug_string(message);debug_string(" code=");
  char digits[16];uint32_t count=0,value=code;
  do { digits[count++]=(char)('0'+value%10);value/=10; } while (value && count<15);
  while (count) debug_byte((uint8_t)digits[--count]);
  debug_byte('\n');
  console_ascii(message);console_ascii(" code=");console_decimal(code);console_ascii("\r\n");
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
  if (!persist_loader_record(0,code)) {
    debug_string("AIUEOS_LOADER_PROGRESS_PERSIST_FAIL\n");
    console_ascii("Progress could not be persisted.\r\n");
  }
#endif
}

static efi_status fail(uint32_t code, const char *message) {
  debug_string(message);debug_string(" code=");
  char digits[16];uint32_t count=0,value=code;
  do { digits[count++]=(char)('0'+value%10);value/=10; } while (value && count<15);
  while (count) debug_byte((uint8_t)digits[--count]);
  debug_byte('\n');
  console_ascii("\r\n");console_ascii(message);console_ascii(" code=");
  console_decimal(code);console_ascii("\r\n");
  if (persist_loader_failure(code)) {
    debug_string("AIUEOS_LOADER_FAILURE_RESULT_PERSISTED\n");
    console_ascii("Failure result persisted; returning to USB collector.\r\n");
  } else {
    debug_string("AIUEOS_LOADER_FAILURE_RESULT_PERSIST_FAIL\n");
    console_ascii("Failure result could not be persisted.\r\n");
  }
#ifndef AIUEOS_PHYSICAL_QUALIFICATION
  fail_exit();
#else
#ifdef AIUEOS_MODEL_SLOT_IMPORT_EXIT
  fail_exit();
#endif
#endif
  return EFI_INVALID_PARAMETER;
}

/* ---- H3 recovery reinstall (JUN-140) -------------------------------------
   Booting the recovery volume (RECOVERY.ID present on the loaded volume) or
   falling back to an alternate volume for the kernel means the system
   volume's boot chain is gone or suspect. The recovery volume carries the
   three boot-chain files; restore them file-by-file to the system ESP so
   the system boots on its own again. The data partition is not touched.
   The copy is bounded: one file at a time through a staging buffer, each
   write followed by a read-back comparison. */
#define REINSTALL_MAX_FILE (8U * 1024U * 1024U)
static uint8_t *reinstall_stage;

static int recovery_marker_present(struct efi_file *root) {
  struct efi_file *file = 0;
  if (root->open(root, &file, u"\\RECOVERY.ID", 1, 0) != EFI_SUCCESS || !file) return 0;
  file->close(file);
  return 1;
}

static int reinstall_copy(struct efi_file *src_root, struct efi_file *dst_root,
                          const char16 *path, struct efi_boot_services *bs,
                          const char *step) {
  struct efi_file *src = 0, *dst = 0;
  uint64_t size = 0;
  if (src_root->open(src_root, &src, path, 1, 0) != EFI_SUCCESS || !src) {
    debug_string("AIUEOS_RECOVERY_COPY_FAIL src "); debug_string(step); debug_string("\n");
    return 0;
  }
  size = REINSTALL_MAX_FILE;
  if (src->read(src, &size, reinstall_stage) != EFI_SUCCESS || size == 0 ||
      size > REINSTALL_MAX_FILE) { src->close(src); return 0; }
  src->close(src);
  /* Replace semantics: an existing dest file keeps its old size on write
     (no truncate through Open), so delete it first — measured 2026-10-25
     when a smaller update file failed the read-back compare against the
     larger file it replaced. */
  {
    struct efi_file *old = 0;
    if (dst_root->open(dst_root, &old, path, 3, 0) == EFI_SUCCESS && old) {
      old->delete_file(old);
    }
  }
  /* Measured 2026-10-25: FatPkg returns EFI_INVALID_PARAMETER for
     WRITE|CREATE (status 2) and accepts READ|WRITE|CREATE with ARCHIVE
     attributes — the form used here and proven by the reinstall run. */
  efi_status create_status = dst_root->open(dst_root, &dst, path,
      3 | 0x8000000000000000ULL, 0x20);
  if (create_status != EFI_SUCCESS || !dst) {
    debug_string("AIUEOS_RECOVERY_COPY_FAIL create "); debug_string(step);
    debug_string(" status="); debug_hex32((uint32_t)create_status); debug_string("\n");
    return 0;
  }
  uint64_t written = size;
  if (dst->write(dst, &written, reinstall_stage) != EFI_SUCCESS || written != size) {
    debug_string("AIUEOS_RECOVERY_COPY_FAIL write "); debug_string(step); debug_string("\n");
    dst->close(dst); return 0;
  }
  dst->close(dst);
  /* read back and compare */
  struct efi_file *chk = 0;
  uint64_t back = 0;
  if (dst_root->open(dst_root, &chk, path, 1, 0) != EFI_SUCCESS || !chk) {
    debug_string("AIUEOS_RECOVERY_COPY_FAIL reopen "); debug_string(step); debug_string("\n");
    return 0;
  }
  back = REINSTALL_MAX_FILE;
  int same = (chk->read(chk, &back, reinstall_stage + REINSTALL_MAX_FILE) == EFI_SUCCESS &&
              back == size);
  chk->close(chk);
  if (same) {
    for (uint64_t k = 0; k < size; k++) {
      if (reinstall_stage[k] != reinstall_stage[REINSTALL_MAX_FILE + k]) { same = 0; break; }
    }
  }
  return same;
}

/* Restore the boot chain to the system ESP (the first non-own FAT volume
   that has an EFI\AIUEOS directory). Returns 1 when a restore ran. */
/* ---- H1 signed update (JUN-140) -----------------------------------------
   An update volume carries UPDATE.ID, UPDATE.MANIFEST (ascii lines
   "<64-hex-sha256> <KERNEL.ELF|INITRD.IMG|BOOTX64.EFI>"), the three files at
   their normal paths, and UPDATE.MANIFEST.SIG (RSASSA-PKCS1-v1_5-SHA256
   over the manifest under the release key; the matching private key is held
   by the signing pipeline in qualification/release-key/). The loader
   verifies the manifest signature against the baked release public key and
   each file against the manifest, then applies the files to its own volume
   (the system ESP) with the H3 copy path. A missing or bad signature is
   AIUEOS_UPDATE_REFUSED_unsigned with no writes. */
static const uint8_t update_modulus[256] = {
  0xb2, 0xf3, 0x95, 0x6b, 0xa4, 0x1f, 0x54, 0xce, 0xc4, 0x8b, 0x46, 0x45,
  0x59, 0x07, 0xf7, 0xaa, 0x37, 0xc0, 0x5c, 0xa1, 0xed, 0x3a, 0xf9, 0x97,
  0x67, 0x06, 0x63, 0xfc, 0x9d, 0xea, 0x41, 0xa4, 0xd3, 0x0c, 0x34, 0xc8,
  0x21, 0xa0, 0x72, 0x6b, 0x7b, 0xee, 0x80, 0x58, 0xdd, 0x32, 0xe5, 0x79,
  0x58, 0x8f, 0xc7, 0x14, 0x35, 0xd0, 0xa5, 0xf6, 0xc9, 0x32, 0x48, 0x76,
  0x48, 0x72, 0x4a, 0x45, 0x2b, 0xf5, 0x0e, 0x4f, 0xcc, 0xb2, 0xd0, 0x45,
  0x00, 0xde, 0x27, 0x74, 0xd0, 0x93, 0x0b, 0x25, 0x96, 0x3b, 0xaa, 0xb1,
  0xe7, 0x4f, 0x7e, 0x46, 0x04, 0xb1, 0x06, 0x76, 0x14, 0xa7, 0x21, 0x75,
  0xcc, 0x8c, 0x78, 0xc7, 0xb7, 0x0e, 0x8f, 0xe3, 0x4f, 0x4f, 0xa2, 0x05,
  0x94, 0xf9, 0xfa, 0xd0, 0x54, 0x56, 0xa9, 0x3a, 0xcf, 0xcb, 0xa3, 0xa2,
  0xcd, 0x10, 0x31, 0xe8, 0x7e, 0xbd, 0x6f, 0xdc, 0xa2, 0xe0, 0xe1, 0x3b,
  0x34, 0x08, 0x43, 0x11, 0x1e, 0x36, 0x4e, 0xdc, 0xa7, 0xbc, 0xad, 0xf0,
  0x0e, 0x54, 0xba, 0x3b, 0x31, 0xdc, 0x2d, 0xfa, 0x64, 0x09, 0x66, 0xa0,
  0x86, 0xbd, 0x52, 0x85, 0x26, 0x68, 0x12, 0x7e, 0x1b, 0x45, 0xbe, 0x45,
  0x13, 0xc1, 0x2f, 0x68, 0x2d, 0x0e, 0x90, 0xa5, 0x7e, 0xb6, 0x44, 0x03,
  0x2b, 0x3e, 0xf8, 0xb1, 0x13, 0x5e, 0xd8, 0xf7, 0x0d, 0xa5, 0xb2, 0xd6,
  0xc4, 0x4f, 0x13, 0x56, 0x56, 0xaa, 0xd3, 0x27, 0x83, 0xa8, 0xbf, 0x41,
  0xa3, 0xdb, 0xfd, 0xae, 0xe2, 0x15, 0x70, 0x5c, 0xac, 0xbb, 0x4b, 0x86,
  0xd9, 0x3c, 0x06, 0x48, 0x5a, 0x4d, 0x7b, 0xb9, 0x16, 0xfd, 0xbb, 0xcf,
  0xaf, 0x6a, 0x8e, 0x73, 0xad, 0xd5, 0x70, 0x33, 0xf5, 0x5f, 0x8b, 0xa1,
  0xcc, 0x0f, 0x95, 0x51, 0x40, 0xe5, 0xf1, 0x0f, 0xce, 0x43, 0x9d, 0xa4,
  0x1b, 0xa7, 0x2c, 0x3f,
};
/* 32-bit limbs, little-endian order, 64 limbs to a 2048-bit number. */
static void update_to_limbs(const uint8_t be[256], uint32_t out[64]) {
  for (int i = 0; i < 64; i++) {
    int o = 255 - (i * 4) - 3;
    out[i] = ((uint32_t)be[o] << 24) | ((uint32_t)be[o + 1] << 16) |
             ((uint32_t)be[o + 2] << 8) | (uint32_t)be[o + 3];
  }
}
static void update_from_limbs(const uint32_t in[64], uint8_t be[256]) {
  for (int i = 0; i < 64; i++) {
    int o = 255 - (i * 4) - 3;
    be[o] = (uint8_t)(in[i] >> 24); be[o + 1] = (uint8_t)(in[i] >> 16);
    be[o + 2] = (uint8_t)(in[i] >> 8); be[o + 3] = (uint8_t)in[i];
  }
}
/* out = (a * b) mod n, all 2048-bit. Schoolbook product, then the proven
   shift-subtract reduction (the same algorithm cross-checked against
   openssl's pow in the H1 design work): for bit 2048..0 subtract n << bit
   whenever the running value is at least it. */
static uint32_t update_slimb(const uint32_t n[64], int word, int shift, int i) {
  uint64_t v = 0;
  int j = i - word;
  if (j >= 0 && j < 64) v = (uint64_t)n[j] << shift;
  if (shift && j - 1 >= 0 && j - 1 < 64) v |= (uint64_t)n[j - 1] >> (32 - shift);
  return (uint32_t)v;
}
static void update_modmul(const uint32_t a[64], const uint32_t b[64],
                          const uint32_t n[64], uint32_t out[64]) {
  uint32_t prod[128];
  for (int i = 0; i < 128; i++) prod[i] = 0;
  for (int i = 0; i < 64; i++) {
    uint64_t carry = 0;
    for (int j = 0; j < 64; j++) {
      uint64_t v = (uint64_t)prod[i + j] + (uint64_t)a[i] * b[j] + carry;
      prod[i + j] = (uint32_t)v; carry = v >> 32;
    }
    uint64_t v = (uint64_t)prod[i + 64] + carry;
    prod[i + 64] = (uint32_t)v;
    uint64_t c2 = v >> 32;
    for (int k = i + 65; k < 128 && c2; k++) {
      uint64_t w = (uint64_t)prod[k] + c2;
      prod[k] = (uint32_t)w;
      c2 = w >> 32;
    }
  }
  uint32_t r[129];
  for (int i = 0; i < 128; i++) r[i] = prod[i];
  r[128] = 0;
  for (int bit = 2048; bit >= 0; bit--) {
    int word = bit / 32, shift = bit % 32;
    int ge = 0;
    for (int i = 128; i >= 0; i--) {
      uint32_t nl = update_slimb(n, word, shift, i);
      if (r[i] > nl) { ge = 1; break; }
      if (r[i] < nl) { ge = 0; break; }
    }
    if (ge) {
      long long borrow = 0;
      for (int i = 0; i <= 128; i++) {
        uint32_t nl = update_slimb(n, word, shift, i);
        long long diff = (long long)r[i] - nl - borrow;
        r[i] = (uint32_t)diff;
        borrow = diff < 0 ? 1 : 0;
      }
    }
  }
  for (int i = 0; i < 64; i++) out[i] = r[i];
}

static int update_sig_verify(const uint8_t sig[256], const uint8_t digest[32]) {
  uint32_t n[64], base[64], acc[64];
  update_to_limbs(update_modulus, n);
  update_to_limbs(sig, base);
  for (int i = 0; i < 64; i++) acc[i] = base[i];
  for (int i = 0; i < 16; i++) update_modmul(acc, acc, n, acc); /* in^(2^16) */
  update_modmul(acc, base, n, acc);                              /* * in   */
  uint8_t em[256];
  update_from_limbs(acc, em);
  /* EM = 00 01 FF x 202 00 || DigestInfo(SHA-256) || H */
  static const uint8_t digestinfo[19] = {
    0x30, 0x31, 0x30, 0x0d, 0x06, 0x09, 0x60, 0x86, 0x48, 0x01,
    0x65, 0x03, 0x04, 0x02, 0x01, 0x05, 0x00, 0x04, 0x20};
  if (em[0] != 0x00 || em[1] != 0x01) return 0;
  int i = 2;
  while (i < 256 && em[i] == 0xff) i++;
  if (i != 204 || em[i] != 0x00) return 0;
  i++;
  for (int k = 0; k < 19; k++) if (em[i + k] != digestinfo[k]) return 0;
  i += 19;
  for (int k = 0; k < 32; k++) if (em[i + k] != digest[k]) return 0;
  return 1;
}

static int update_apply(struct efi_boot_services *bs, efi_handle own_device) {
  static const char16 update_id[] = u"\\UPDATE.ID";
  static const char16 manifest_path[] = u"\\UPDATE.MNF";
  static const char16 signature_path[] = u"\\UPDATE.SIG";
  static const char16 kernel_path[] = u"\\EFI\\AIUEOS\\KERNEL.ELF";
  static const char16 initramfs_path[] = u"\\EFI\\AIUEOS\\INITRD.IMG";
  static const char16 boot_path[] = u"\\EFI\\BOOT\\BOOTX64.EFI";
  efi_handle handles[16];
  uint64_t handle_bytes = sizeof(handles);
  struct efi_file *src_root = 0, *dst_root = 0;
  struct efi_simple_file_system *fs = 0;
  struct efi_file *probe = 0;
  uint8_t *pool = 0;
  if (bs->locate_handle(2, &simple_fs_guid, 0, &handle_bytes, handles) != EFI_SUCCESS) return 0;
  uint64_t count = handle_bytes / sizeof(efi_handle);
  for (uint64_t i = 0; i < count && !src_root; i++) {
    if (bs->handle_protocol(handles[i], &simple_fs_guid, (void **)&fs) != EFI_SUCCESS || !fs) continue;
    if (fs->open_volume(fs, &probe) != EFI_SUCCESS || !probe) continue;
    struct efi_file *id = 0;
    if (probe->open(probe, &id, update_id, 1, 0) == EFI_SUCCESS && id) {
      id->close(id);
      src_root = probe;
    } else {
      probe->close(probe);
    }
  }
  if (!src_root) return 0;
  if (bs->handle_protocol(own_device, &simple_fs_guid, (void **)&fs) != EFI_SUCCESS || !fs ||
      fs->open_volume(fs, &dst_root) != EFI_SUCCESS || !dst_root) {
    src_root->close(src_root); return 0;
  }
  if (bs->allocate_pool(2, 2 * 1024 * 1024, (void **)&pool) != EFI_SUCCESS) {
    src_root->close(src_root); dst_root->close(dst_root); return 0;
  }
  struct efi_file *mf = 0, *sg = 0;
  uint64_t msize = 0, ssize = 0;
  int ok = 0;
  if (src_root->open(src_root, &mf, manifest_path, 1, 0) == EFI_SUCCESS && mf) {
    msize = 4096;
    if (mf->read(mf, &msize, pool) == EFI_SUCCESS && msize > 0 && msize <= 4096) ok = 1;
    mf->close(mf);
  }
  if (ok) ok = (src_root->open(src_root, &sg, signature_path, 1, 0) == EFI_SUCCESS && sg);
  if (ok) {
    ssize = 256;
    ok = (sg->read(sg, &ssize, pool + 8192) == EFI_SUCCESS && ssize == 256);
    sg->close(sg);
  }
  if (!ok) {
    debug_string("AIUEOS_UPDATE_REFUSED_unsigned\n");
    goto done;
  }
  {
    uint8_t digest[32];
    sha256(pool, msize, digest);
    if (!update_sig_verify(pool + 8192, digest)) {
      debug_string("AIUEOS_UPDATE_REFUSED_unsigned\n");
      goto done;
    }
    /* manifest lines: "<64-hex> <NAME>"; each file verified then copied */
    static const char16 *paths[3] = { kernel_path, initramfs_path, boot_path };
    const char *names[3] = { "KERNEL.ELF", "INITRD.IMG", "BOOTX64.EFI" };
    int seen = 0;
    uint64_t pos = 0;
    while (pos < msize && seen < 3) {
      uint64_t line_start = pos;
      while (pos < msize && pool[pos] != '\n') pos++;
      uint64_t line_len = pos - line_start;
      pos++;
      if (line_len < 66) continue;
      const char *name = (const char *)(pool + line_start + 65);
      uint64_t name_len = line_len - 65;
      for (int f = 0; f < 3; f++) {
        int match = 1;
        if (name_len != 0) {
          uint64_t k = 0;
          while (k < name_len && names[f][k] && names[f][k] == name[k]) k++;
          match = (k == name_len && names[f][k] == 0);
        }
        if (!match) continue;
        struct efi_file *in = 0;
        if (src_root->open(src_root, &in, paths[f], 1, 0) != EFI_SUCCESS || !in) { ok = 0; break; }
        uint64_t fsz = 1024 * 1024;
        if (in->read(in, &fsz, pool + 16384) != EFI_SUCCESS || fsz == 0 || fsz > 1024 * 1024) {
          in->close(in); ok = 0; break;
        }
        in->close(in);
        uint8_t got[32];
        sha256(pool + 16384, fsz, got);
        for (int b = 0; b < 32; b++) {
          int hi = pool[line_start + b * 2], lo = pool[line_start + b * 2 + 1];
          int hv = (hi >= 'a') ? hi - 'a' + 10 : hi - '0';
          int lv = (lo >= 'a') ? lo - 'a' + 10 : lo - '0';
          if (got[b] != (uint8_t)((hv << 4) | lv)) { ok = 0; }
        }
        if (!ok) break;
        seen++;
        break;
      }
      if (!ok) break;
    }
    if (!ok || seen != 3) {
      debug_string("AIUEOS_UPDATE_REFUSED_digest\n");
      goto done;
    }
    if (!reinstall_copy(src_root, dst_root, kernel_path, bs, "update-kernel") ||
        !reinstall_copy(src_root, dst_root, initramfs_path, bs, "update-initrd") ||
        !reinstall_copy(src_root, dst_root, boot_path, bs, "update-bootx")) {
      debug_string("AIUEOS_UPDATE_FAIL copy\n");
      goto done;
    }
    debug_string("AIUEOS_UPDATE_APPLIED manifest-signed copies-verified\n");
  }
done:
  bs->free_pool(pool);
  src_root->close(src_root);
  dst_root->close(dst_root);
  return 1;
}

/* ---- A5 first-run setup (JUN-140) ---------------------------------------
   On a clean install the loader looks for a setup volume (SETUP.ID +
   SETUP.INI: three lines "name=", "device=", "account="), stores SETUP.INI
   on the system ESP and prints the applied marker; on every later boot the
   stored choices are read back and printed. The QEMU test delivers the
   choices on the setup volume (the physical-machine story is a first-run UI
   writing the same file); the readback marker is the row's evidence. */
static int setup_flow(struct efi_boot_services *bs, efi_handle own_device) {
  static const char16 setup_id[] = u"\\SETUP.ID";
  static const char16 setup_ini[] = u"\\SETUP.INI";
  efi_handle handles[16];
  uint64_t handle_bytes = sizeof(handles);
  struct efi_simple_file_system *fs = 0;
  struct efi_file *own = 0, *src = 0, *f = 0;
  uint8_t *buf = 0;
  uint64_t size = 0;
  if (bs->allocate_pool(2, 4096, (void **)&buf) != EFI_SUCCESS) return 0;
  /* 1. the stored choices read back first: they are the evidence on every
     boot after the setup completed. */
  if (bs->handle_protocol(own_device, &simple_fs_guid, (void **)&fs) == EFI_SUCCESS &&
      fs && fs->open_volume(fs, &own) == EFI_SUCCESS && own) {
    if (own->open(own, &f, setup_ini, 1, 0) == EFI_SUCCESS && f) {
      size = 4095;
      if (f->read(f, &size, buf) == EFI_SUCCESS && size > 0) {
        buf[size] = 0;
        debug_string("AIUEOS_SETUP_LOADED ");
        debug_string((const char *)buf);
        if (((const char *)buf)[size - 1] != '\n') debug_string("\n");
      }
      f->close(f);
      bs->free_pool(buf);
      own->close(own);
      return 1;
    }
    own->close(own);
    own = 0;
  }
  /* 2. first run: take the choices from a setup volume */
  if (bs->locate_handle(2, &simple_fs_guid, 0, &handle_bytes, handles) != EFI_SUCCESS) {
    bs->free_pool(buf); return 0;
  }
  uint64_t count = handle_bytes / sizeof(efi_handle);
  for (uint64_t i = 0; i < count; i++) {
    struct efi_file *probe = 0, *id = 0;
    if (handles[i] == own_device) continue;
    if (bs->handle_protocol(handles[i], &simple_fs_guid, (void **)&fs) != EFI_SUCCESS || !fs) continue;
    if (fs->open_volume(fs, &probe) != EFI_SUCCESS || !probe) continue;
    if (probe->open(probe, &id, setup_id, 1, 0) == EFI_SUCCESS && id) {
      id->close(id);
      src = probe;
      break;
    }
    probe->close(probe);
  }
  if (!src) { bs->free_pool(buf); return 0; }
  int applied = 0;
  if (src->open(src, &f, setup_ini, 1, 0) == EFI_SUCCESS && f) {
    size = 4095;
    if (f->read(f, &size, buf) == EFI_SUCCESS && size > 0 && size < 2048) {
      buf[size] = 0;
      if (bs->handle_protocol(own_device, &simple_fs_guid, (void **)&fs) == EFI_SUCCESS &&
          fs && fs->open_volume(fs, &own) == EFI_SUCCESS && own) {
        struct efi_file *out = 0;
        if (own->open(own, &out, setup_ini, 3 | 0x8000000000000000ULL, 0x20) == EFI_SUCCESS && out) {
          uint64_t written = size;
          if (out->write(out, &written, buf) == EFI_SUCCESS && written == size) applied = 1;
          out->close(out);
        }
        own->close(own);
      }
      if (applied) {
        debug_string("AIUEOS_SETUP_APPLIED ");
        debug_string((const char *)buf);
        if (((const char *)buf)[size - 1] != '\n') debug_string("\n");
      }
    }
    f->close(f);
  }
  src->close(src);
  bs->free_pool(buf);
  return applied;
}

static int recovery_reinstall(struct efi_boot_services *bs, efi_handle own_device) {
  debug_string("ZZQQ_UNIQUE_PROBE_12345\n");
  static const char16 kernel_path[] = u"\\EFI\\AIUEOS\\KERNEL.ELF";
  static const char16 initramfs_path[] = u"\\EFI\\AIUEOS\\INITRD.IMG";
  static const char16 boot_path[] = u"\\EFI\\BOOT\\BOOTX64.EFI";
  static const char16 marker_dir[] = u"\\EFI\\AIUEOS";
  efi_handle handles[16];
  uint64_t handle_bytes = sizeof(handles);
  int ran = 0;
  struct efi_simple_file_system *own_fs = 0;
  struct efi_file *own_root = 0;
  if (bs->handle_protocol(own_device, &simple_fs_guid, (void **)&own_fs) != EFI_SUCCESS ||
      !own_fs || own_fs->open_volume(own_fs, &own_root) != EFI_SUCCESS || !own_root)
    return 0;
  if (!recovery_marker_present(own_root)) {
    debug_string("AIUEOS_RECOVERY_ID_ABSENT\n");
    own_root->close(own_root); return 0;
  }
  debug_string("AIUEOS_RECOVERY_ID_OK\n");
  if (bs->allocate_pool(2, 2 * REINSTALL_MAX_FILE, (void **)&reinstall_stage) != EFI_SUCCESS)
    return 0;
  if (bs->locate_handle(2, &simple_fs_guid, 0, &handle_bytes, handles) != EFI_SUCCESS) {
    own_root->close(own_root); return 0;
  }
  uint64_t count = handle_bytes / sizeof(efi_handle);
  for (uint64_t i = 0; i < count; i++) {
    struct efi_simple_file_system *fs = 0;
    struct efi_file *root = 0;
    struct efi_file *probe = 0;
    if (handles[i] == own_device) continue;
    if (bs->handle_protocol(handles[i], &simple_fs_guid, (void **)&fs) != EFI_SUCCESS || !fs)
      continue;
    if (fs->open_volume(fs, &root) != EFI_SUCCESS || !root) continue;
    if (root->open(root, &probe, marker_dir, 1, 0) != EFI_SUCCESS || !probe) {
      root->close(root); continue;
    }
    probe->close(probe);
    debug_string("AIUEOS_RECOVERY_TARGET_FOUND\n");
    int ok = reinstall_copy(own_root, root, kernel_path, bs, "kernel") &&
             reinstall_copy(own_root, root, initramfs_path, bs, "initrd") &&
             reinstall_copy(own_root, root, boot_path, bs, "bootx");
    root->close(root);
    if (ok) {
      debug_string("AIUEOS_RECOVERY_REINSTALL_OK boot-chain-restored\n");
      ran = 1;
    } else {
      debug_string("AIUEOS_RECOVERY_REINSTALL_FAIL copy\n");
    }
    break;
  }
  if (!ran) debug_string("AIUEOS_RECOVERY_NOTARGET\n");
  own_root->close(own_root);
  return ran;
}

static efi_status read_verified_file(struct efi_file *root, const char16 *path,
                                     const char *kind_open, const char *kind_read,
                                     const char *kind_sha,
                                     const uint8_t expected_sha256[32],
                                     uint8_t *buffer, uint64_t buffer_size,
                                     uint64_t *size) {
  struct efi_file *file = 0;
  if (root->open(root, &file, path, 1, 0) != EFI_SUCCESS || !file) {
    debug_string(kind_open); return EFI_INVALID_PARAMETER;
  }
  *size = buffer_size;
  if (file->read(file, size, buffer) != EFI_SUCCESS) {
    file->close(file);
    debug_string(kind_read); return EFI_INVALID_PARAMETER;
  }
  file->close(file);
  uint8_t digest[32];
  sha256(buffer, *size, digest);
  for (uint32_t i = 0; i < 32; i++) {
    if (digest[i] != expected_sha256[i]) {
      debug_string(kind_sha); return EFI_INVALID_PARAMETER;
    }
  }
  return EFI_SUCCESS;
}

/* One admission candidate: open the volume on this device and require both
   the kernel and the initramfs to match their compiled-in SHA-256 digests.
   Emits the failure marker but does not terminate, so the caller can fall
   back to another volume. */
static efi_status read_verified_kernel(struct efi_boot_services *bs, efi_handle device,
                                       const char16 *kernel_path,
                                       const char16 *initramfs_path,
                                       uint8_t *kernel_file, uint64_t *kernel_size,
                                       uint8_t *initramfs_file, uint64_t *initramfs_size) {
  struct efi_simple_file_system *fs = 0;
  struct efi_file *root = 0;
  if (bs->handle_protocol(device, &simple_fs_guid, (void **)&fs) != EFI_SUCCESS || !fs) {
    debug_string("AIUEOS_LOADER_FAIL filesystem\n"); return EFI_INVALID_PARAMETER;
  }
  if (fs->open_volume(fs, &root) != EFI_SUCCESS || !root) {
    debug_string("AIUEOS_LOADER_FAIL volume\n"); return EFI_INVALID_PARAMETER;
  }
  efi_status status = read_verified_file(root, kernel_path,
      "AIUEOS_LOADER_FAIL kernel-open\n", "AIUEOS_LOADER_FAIL kernel-read\n",
      "AIUEOS_LOADER_FAIL kernel-sha256\n",
      aiueos_expected_kernel_sha256, kernel_file, KERNEL_BUFFER_SIZE, kernel_size);
  if (status == EFI_SUCCESS)
    status = read_verified_file(root, initramfs_path,
        "AIUEOS_LOADER_FAIL initramfs-open\n", "AIUEOS_LOADER_FAIL initramfs-read\n",
        "AIUEOS_LOADER_FAIL initramfs-sha256\n",
        aiueos_expected_initramfs_sha256, initramfs_file, INITRAMFS_BUFFER_SIZE,
        initramfs_size);
  root->close(root);
  return status;
}

#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
#define MODEL_READ_CHUNK (16ULL * 1024ULL * 1024ULL)
#define MODEL_HUGE_PAGE_SIZE (2ULL * 1024ULL * 1024ULL)
_Static_assert(AIUEOS_MODEL_PART_COUNT == 2U || AIUEOS_MODEL_PART_COUNT == 3U,
               "model bundle is two (bonsai2) or three (qwen38) parts");
_Static_assert(AIUEOS_MODEL_PART0_BYTES + AIUEOS_MODEL_PART1_BYTES +
               AIUEOS_MODEL_PART2_BYTES == AIUEOS_MODEL_TOTAL_BYTES,
               "model bundle lengths do not sum to the artifact length");
_Static_assert(AIUEOS_MODEL_PART_COUNT == 3U || AIUEOS_MODEL_PART2_BYTES == 0ULL,
               "a two-part bundle has no third part");

struct model_part { const char16 *path; uint64_t bytes; };
static const struct model_part model_parts[AIUEOS_MODEL_PART_COUNT] = {
  { AIUEOS_MODEL_PART0_PATH, AIUEOS_MODEL_PART0_BYTES },
  { AIUEOS_MODEL_PART1_PATH, AIUEOS_MODEL_PART1_BYTES },
#if AIUEOS_MODEL_PART_COUNT == 3
  { AIUEOS_MODEL_PART2_PATH, AIUEOS_MODEL_PART2_BYTES },
#endif
};

static efi_status read_exact_model_part(struct efi_file *root,
                                        const char16 *path,
                                        uint8_t *destination,
                                        uint64_t expected_bytes) {
  struct efi_file *file = 0;
  if (!root || root->open(root, &file, path, 1, 0) != EFI_SUCCESS || !file)
    return EFI_INVALID_PARAMETER;
  uint64_t offset = 0;
  while (offset < expected_bytes) {
    uint64_t remaining = expected_bytes - offset;
    uint64_t bytes = remaining > MODEL_READ_CHUNK ? MODEL_READ_CHUNK : remaining;
    efi_status status = file->read(file, &bytes, destination + offset);
    if (status != EFI_SUCCESS || !bytes || bytes > remaining) {
      file->close(file);
      return EFI_INVALID_PARAMETER;
    }
    offset += bytes;
  }
  uint8_t extra = 0;
  uint64_t extra_bytes = 1;
  efi_status status = file->read(file, &extra_bytes, &extra);
  file->close(file);
  return status == EFI_SUCCESS && extra_bytes == 0 ?
    EFI_SUCCESS : EFI_INVALID_PARAMETER;
}

static efi_status read_model_on_device(struct efi_boot_services *bs,
                                       efi_handle device, uint8_t *model) {
  struct efi_simple_file_system *fs = 0;
  struct efi_file *root = 0;
  if (bs->handle_protocol(device, &simple_fs_guid, (void **)&fs) != EFI_SUCCESS ||
      !fs || fs->open_volume(fs, &root) != EFI_SUCCESS || !root)
    return EFI_INVALID_PARAMETER;
  efi_status status = EFI_SUCCESS;
  uint64_t offset = 0;
  for (uint32_t i = 0; i < AIUEOS_MODEL_PART_COUNT && status == EFI_SUCCESS; i++) {
    status = read_exact_model_part(root, model_parts[i].path, model + offset,
                                   model_parts[i].bytes);
    offset += model_parts[i].bytes;
  }
  root->close(root);
  if (status != EFI_SUCCESS) return status;
  uint8_t digest[32];
  sha256(model, AIUEOS_MODEL_TOTAL_BYTES, digest);
  for (uint32_t i = 0; i < 32; i++)
    if (digest[i] != aiueos_expected_model_sha256[i])
      return EFI_INVALID_PARAMETER;
  return EFI_SUCCESS;
}

static efi_status load_verified_model(struct efi_boot_services *bs,
                                      efi_handle boot_device,
                                      struct aiueos_boot_info *info) {
  if (!bs || !bs->allocate_pages || !bs->free_pages || !info ||
      !AIUEOS_MODEL_TOTAL_BYTES ||
      AIUEOS_MODEL_TOTAL_BYTES > AIUEOS_MODEL_MAX_ADDRESS + 1ULL)
    return EFI_INVALID_PARAMETER;
  uint64_t mapped_bytes =
    (AIUEOS_MODEL_TOTAL_BYTES + MODEL_HUGE_PAGE_SIZE - 1) &
    ~(MODEL_HUGE_PAGE_SIZE - 1);
  uint64_t pages = mapped_bytes / PAGE_SIZE;
  uint64_t raw_pages = pages + MODEL_HUGE_PAGE_SIZE / PAGE_SIZE - 1;
  uint64_t raw_base = AIUEOS_MODEL_MAX_ADDRESS;
  if (!pages || raw_pages < pages ||
      raw_pages > (AIUEOS_MODEL_MAX_ADDRESS + 1ULL) / PAGE_SIZE)
    return EFI_INVALID_PARAMETER;
  if (bs->allocate_pages(EFI_ALLOCATE_MAX_ADDRESS, EFI_LOADER_DATA,
                         raw_pages, &raw_base) != EFI_SUCCESS)
    return EFI_INVALID_PARAMETER;
  uint64_t base = (raw_base + MODEL_HUGE_PAGE_SIZE - 1) &
                  ~(MODEL_HUGE_PAGE_SIZE - 1);
  if (base < AIUEOS_MODEL_MIN_ADDRESS ||
      base < raw_base || base > AIUEOS_MODEL_MAX_ADDRESS + 1ULL - mapped_bytes ||
      base + mapped_bytes > raw_base + raw_pages * PAGE_SIZE) {
    bs->free_pages(raw_base, raw_pages);
    return EFI_INVALID_PARAMETER;
  }
  uint64_t paging_pages = AIUEOS_MODEL_PAGING_PAGES;
  uint64_t paging_base = 0x40000000ULL - 1ULL;
  if (bs->allocate_pages(EFI_ALLOCATE_MAX_ADDRESS, EFI_LOADER_DATA,
                         paging_pages, &paging_base) != EFI_SUCCESS) {
    bs->free_pages(raw_base, raw_pages);
    return EFI_INVALID_PARAMETER;
  }
  if (!paging_base || paging_base >= 0x40000000ULL ||
      paging_base > 0x40000000ULL - paging_pages * PAGE_SIZE) {
    bs->free_pages(paging_base, paging_pages);
    bs->free_pages(raw_base, raw_pages);
    return EFI_INVALID_PARAMETER;
  }
  zero_bytes((void *)(uintptr_t)paging_base, paging_pages * PAGE_SIZE);
  uint8_t *model = (uint8_t *)(uintptr_t)base;
  uint64_t started = read_tsc();
  efi_status admitted = read_model_on_device(bs, boot_device, model);
  if (admitted != EFI_SUCCESS) {
    efi_handle handles[32];
    uint64_t handle_bytes = sizeof(handles);
    if (bs->locate_handle(EFI_BY_PROTOCOL, &simple_fs_guid, 0,
                          &handle_bytes, handles) == EFI_SUCCESS) {
      uint64_t count = handle_bytes / sizeof(efi_handle);
      for (uint64_t i = 0; i < count && admitted != EFI_SUCCESS; i++) {
        if (handles[i] == boot_device) continue;
        admitted = read_model_on_device(bs, handles[i], model);
      }
    }
  }
  if (admitted != EFI_SUCCESS) {
    zero_bytes(model, mapped_bytes);
    zero_bytes((void *)(uintptr_t)paging_base, paging_pages * PAGE_SIZE);
    bs->free_pages(paging_base, paging_pages);
    bs->free_pages(raw_base, raw_pages);
    return admitted;
  }
  zero_bytes(model + AIUEOS_MODEL_TOTAL_BYTES,
             mapped_bytes - AIUEOS_MODEL_TOTAL_BYTES);
  info->model_base = base;
  info->model_size = AIUEOS_MODEL_TOTAL_BYTES;
  for (uint32_t i = 0; i < 32; i++)
    info->model_sha256[i] = aiueos_expected_model_sha256[i];
  info->model_part_count = AIUEOS_MODEL_PART_COUNT;
  info->model_format = AIUEOS_MODEL_FORMAT_GGUF;
  info->model_flags = AIUEOS_MODEL_HANDOFF_SHA256_VERIFIED |
                      AIUEOS_MODEL_HANDOFF_SPLIT_EXACT;
  info->model_load_cycles = read_tsc() - started;
  info->model_paging_base = paging_base;
  info->model_paging_pages = paging_pages;
  debug_string("AIUEOS_LOADER_MODEL_OK " AIUEOS_MODEL_NAME " gguf-v3 parts="
               AIUEOS_MODEL_PARTS_TEXT " sha256=verified\n");
  console_ascii(AIUEOS_MODEL_NAME " model admitted. Entering native kernel.\r\n");
  return EFI_SUCCESS;
}
#endif

#ifdef AIUEOS_MODEL_NVME_SLOTS
#define MODEL_SLOT_IO_BYTES (16ULL * 1024ULL * 1024ULL)
#define MODEL_SLOT_IO_PAGES (MODEL_SLOT_IO_BYTES / PAGE_SIZE)

struct uefi_model_slot_context { struct efi_block_io *block; };

static int uefi_model_slot_read(void *opaque, uint64_t lba, uint64_t blocks,
                                void *buffer) {
  struct uefi_model_slot_context *context = opaque;
  struct efi_block_io *block = context ? context->block : 0;
  return block && block->media && blocks &&
         blocks <= UINT64_MAX / block->media->block_size &&
         block->read_blocks(block, block->media->media_id, lba,
                            blocks * block->media->block_size, buffer) == EFI_SUCCESS;
}

static int uefi_model_slot_write(void *opaque, uint64_t lba, uint64_t blocks,
                                 const void *buffer) {
  struct uefi_model_slot_context *context = opaque;
  struct efi_block_io *block = context ? context->block : 0;
  return block && block->media && blocks &&
         blocks <= UINT64_MAX / block->media->block_size &&
         block->write_blocks(block, block->media->media_id, lba,
                             blocks * block->media->block_size, buffer) == EFI_SUCCESS;
}

static int uefi_model_slot_flush(void *opaque) {
  struct uefi_model_slot_context *context = opaque;
  return context && context->block && context->block->flush_blocks &&
         context->block->flush_blocks(context->block) == EFI_SUCCESS;
}

static int device_path_contains_nvme(const struct efi_device_path_node *node) {
  uint32_t walked = 0;
  while (node && walked < 4096U) {
    uint16_t length = (uint16_t)node->length[0] | ((uint16_t)node->length[1] << 8);
    if (length < sizeof(*node) || length > 4096U - walked) return 0;
    if (node->type == 3U && node->subtype == 23U) return 1;
    if (node->type == 0x7fU) return 0;
    walked += length;
    node = (const void *)((const uint8_t *)node + length);
  }
  return 0;
}

static int find_model_slot_nvme(struct efi_boot_services *bs,
                                struct uefi_model_slot_context *context,
                                struct aiueos_model_slot_io *io,
                                struct aiueos_model_slot_state *state) {
  efi_handle handles[64];
  uint64_t handle_bytes = sizeof(handles);
  if (!bs || bs->locate_handle(EFI_BY_PROTOCOL, &block_io_guid, 0,
                               &handle_bytes, handles) != EFI_SUCCESS) return 0;
  uint64_t count = handle_bytes / sizeof(efi_handle);
  for (uint64_t i = 0; i < count; i++) {
    struct efi_block_io *block = 0;
    struct efi_device_path_node *path = 0;
    if (bs->handle_protocol(handles[i], &block_io_guid, (void **)&block) != EFI_SUCCESS ||
        !block || !block->media || !block->media->media_present ||
        !block->media->logical_partition || block->media->removable_media ||
        block->media->read_only || block->media->block_size != AIUEOS_MODEL_SLOT_BLOCK_BYTES ||
        !block->read_blocks || !block->write_blocks || !block->flush_blocks ||
        block->media->last_block == UINT64_MAX ||
        bs->handle_protocol(handles[i], &device_path_guid, (void **)&path) != EFI_SUCCESS ||
        !device_path_contains_nvme(path)) continue;
    context->block = block;
    io->context = context;
    io->block_bytes = block->media->block_size;
    io->io_alignment = block->media->io_align;
    io->block_count = block->media->last_block + 1ULL;
    io->read_blocks = uefi_model_slot_read;
    io->write_blocks = uefi_model_slot_write;
    io->flush = uefi_model_slot_flush;
    if (aiueos_model_slot_inspect(io, state)) return 1;
  }
  return 0;
}

static int stream_model_part_to_slot(struct efi_file *root, const char16 *path,
                                     uint64_t expected_bytes,
                                     struct aiueos_model_slot_session *session,
                                     uint8_t *buffer) {
  struct efi_file *file = 0;
  if (!root || root->open(root, &file, path, 1, 0) != EFI_SUCCESS || !file) return 0;
  uint64_t offset = 0;
  while (offset < expected_bytes) {
    uint64_t remaining = expected_bytes - offset;
    uint64_t bytes = remaining > MODEL_SLOT_IO_BYTES ? MODEL_SLOT_IO_BYTES : remaining;
    if (file->read(file, &bytes, buffer) != EFI_SUCCESS || !bytes || bytes > remaining ||
        !aiueos_model_slot_append(session, buffer, bytes)) {
      file->close(file);
      return 0;
    }
    offset += bytes;
  }
  uint8_t extra = 0;
  uint64_t extra_bytes = 1;
  efi_status status = file->read(file, &extra_bytes, &extra);
  file->close(file);
  return status == EFI_SUCCESS && extra_bytes == 0;
}

static int stream_model_volume_to_slot(struct efi_boot_services *bs,
                                       efi_handle source,
                                       struct aiueos_model_slot_session *session,
                                       uint8_t *buffer) {
  static const char16 part0[] = u"\\EFI\\AIUEOS\\Q38P0.BIN";
  static const char16 part1[] = u"\\EFI\\AIUEOS\\Q38P1.BIN";
  static const char16 part2[] = u"\\EFI\\AIUEOS\\Q38P2.BIN";
  struct efi_simple_file_system *fs = 0;
  struct efi_file *root = 0;
  if (bs->handle_protocol(source, &simple_fs_guid, (void **)&fs) != EFI_SUCCESS ||
      !fs || fs->open_volume(fs, &root) != EFI_SUCCESS || !root) return 0;
  int ok = stream_model_part_to_slot(root, part0, AIUEOS_MODEL_PART0_BYTES,
                                     session, buffer) &&
           stream_model_part_to_slot(root, part1, AIUEOS_MODEL_PART1_BYTES,
                                     session, buffer) &&
           stream_model_part_to_slot(root, part2, AIUEOS_MODEL_PART2_BYTES,
                                     session, buffer);
  root->close(root);
  return ok;
}

static efi_status stage_model_to_nvme(struct efi_boot_services *bs,
                                      efi_handle boot_device) {
  struct uefi_model_slot_context context;
  struct aiueos_model_slot_io io;
  struct aiueos_model_slot_state before, after;
  zero_bytes(&context, sizeof(context));
  zero_bytes(&io, sizeof(io));
  zero_bytes(&before, sizeof(before));
  if (!find_model_slot_nvme(bs, &context, &io, &before)) {
#ifdef AIUEOS_MODEL_NVME_TARGET_OPTIONAL
    debug_string("AIUEOS_MODEL_SLOT_DEFERRED target=dedicated-nvme-partition reason=absent internal-disk-write=none\n");
    console_ascii("AIUEOS dedicated model partition absent; continuing HTTPS qualification without an internal-disk write.\r\n");
    return EFI_SUCCESS;
#else
    debug_string("AIUEOS_MODEL_SLOT_FAIL target=dedicated-nvme-partition reason=absent\n");
    return EFI_INVALID_PARAMETER;
#endif
  }
  struct aiueos_model_identity identity;
  identity.bytes = AIUEOS_MODEL_TOTAL_BYTES;
  copy_bytes(identity.sha256, aiueos_expected_model_sha256, 32);
  struct aiueos_model_slot_session session;
  int begin = aiueos_model_slot_begin(&io, &identity, &session, &before);
  if (begin == AIUEOS_MODEL_SLOT_BEGIN_ALREADY_ACTIVE) {
    uint64_t verify_base = 0xffffffffULL;
    if (bs->allocate_pages(EFI_ALLOCATE_MAX_ADDRESS, EFI_LOADER_DATA,
                           MODEL_SLOT_IO_PAGES, &verify_base) != EFI_SUCCESS)
      return EFI_INVALID_PARAMETER;
    uint8_t *verify_buffer = (void *)(uintptr_t)verify_base;
    int verified = aiueos_model_slot_verify_active(
      &io, &before, verify_buffer, MODEL_SLOT_IO_BYTES);
    zero_bytes(verify_buffer, MODEL_SLOT_IO_BYTES);
    bs->free_pages(verify_base, MODEL_SLOT_IO_PAGES);
    if (!verified) {
      debug_string("AIUEOS_MODEL_SLOT_FAIL source=nvme action=reuse-active reason=sha256\n");
      return EFI_INVALID_PARAMETER;
    }
    debug_string("AIUEOS_MODEL_SLOT_OK source=nvme action=reuse-active sha256=verified\n");
    console_ascii("AIUEOS model slot already active and verified.\r\n");
    return EFI_SUCCESS;
  }
  if (begin != AIUEOS_MODEL_SLOT_BEGIN_WRITE) return EFI_INVALID_PARAMETER;

  uint64_t buffer_base = 0xffffffffULL;
  if (bs->allocate_pages(EFI_ALLOCATE_MAX_ADDRESS, EFI_LOADER_DATA,
                         MODEL_SLOT_IO_PAGES, &buffer_base) != EFI_SUCCESS)
    return EFI_INVALID_PARAMETER;
  uint8_t *buffer = (void *)(uintptr_t)buffer_base;
  int streamed = stream_model_volume_to_slot(bs, boot_device, &session, buffer);
  if (!streamed) {
    efi_handle handles[32];
    uint64_t handle_bytes = sizeof(handles);
    if (bs->locate_handle(EFI_BY_PROTOCOL, &simple_fs_guid, 0,
                          &handle_bytes, handles) == EFI_SUCCESS) {
      uint64_t count = handle_bytes / sizeof(efi_handle);
      for (uint64_t i = 0; i < count && !streamed; i++) {
        if (handles[i] == boot_device) continue;
        begin = aiueos_model_slot_begin(&io, &identity, &session, &before);
        if (begin != AIUEOS_MODEL_SLOT_BEGIN_WRITE) break;
        streamed = stream_model_volume_to_slot(bs, handles[i], &session, buffer);
      }
    }
  }
  int committed = streamed &&
    aiueos_model_slot_commit(&session, buffer, MODEL_SLOT_IO_BYTES, &after);
  zero_bytes(buffer, MODEL_SLOT_IO_BYTES);
  bs->free_pages(buffer_base, MODEL_SLOT_IO_PAGES);
  if (!committed) {
    debug_string("AIUEOS_MODEL_SLOT_FAIL source=usb target=nvme action=keep-last-known-good\n");
    return EFI_INVALID_PARAMETER;
  }
  debug_string("AIUEOS_MODEL_SLOT_OK source=usb target=nvme layout=ab readback=sha256 activation=atomic\n");
  console_ascii("AIUEOS model imported to inactive NVMe slot and activated.\r\n");
  return EFI_SUCCESS;
}
#endif

#ifdef AIUEOS_EMBEDDED_RELEASE
static efi_status read_verified_embedded(uint8_t *kernel_file,
                                         uint64_t *kernel_size,
                                         uint8_t *initramfs_file,
                                         uint64_t *initramfs_size) {
  uint64_t embedded_kernel_size=
    (uint64_t)(aiueos_embedded_kernel_end-aiueos_embedded_kernel_start);
  uint64_t embedded_initramfs_size=
    (uint64_t)(aiueos_embedded_initramfs_end-aiueos_embedded_initramfs_start);
  if (!embedded_kernel_size || embedded_kernel_size>KERNEL_BUFFER_SIZE ||
      !embedded_initramfs_size || embedded_initramfs_size>INITRAMFS_BUFFER_SIZE)
    return EFI_INVALID_PARAMETER;
  copy_bytes(kernel_file,aiueos_embedded_kernel_start,embedded_kernel_size);
  copy_bytes(initramfs_file,aiueos_embedded_initramfs_start,
             embedded_initramfs_size);
  uint8_t digest[32];
  sha256(kernel_file,embedded_kernel_size,digest);
  for (uint32_t i=0;i<32;i++)
    if (digest[i]!=aiueos_expected_kernel_sha256[i]) return EFI_INVALID_PARAMETER;
  sha256(initramfs_file,embedded_initramfs_size,digest);
  for (uint32_t i=0;i<32;i++)
    if (digest[i]!=aiueos_expected_initramfs_sha256[i]) return EFI_INVALID_PARAMETER;
  *kernel_size=embedded_kernel_size;
  *initramfs_size=embedded_initramfs_size;
  debug_string("AIUEOS_NETBOOT_EMBEDDED_OK kernel+initramfs sha256-v1\n");
  console_ascii("AIUEOS PXE payload admitted.\r\n");
  return EFI_SUCCESS;
}
#endif

efi_status EFIAPI efi_main(efi_handle image, struct efi_system_table *system) {
  static const char16 console_message[] = u"AIUEOS_LOADER_OK loading kernel.elf\r\n";
  static const char16 kernel_path[] = u"\\EFI\\AIUEOS\\KERNEL.ELF";
  static const char16 initramfs_path[] = u"\\EFI\\AIUEOS\\INITRD.IMG";
  struct efi_boot_services *bs;
  struct efi_loaded_image *loaded = 0;
  uint8_t *kernel_file = 0, *initramfs_file = 0;
  void *memory_map = 0;
  uint64_t kernel_size = KERNEL_BUFFER_SIZE;
  uint64_t initramfs_size = INITRAMFS_BUFFER_SIZE;
  uint64_t memory_map_size, map_key, descriptor_size;
  uint32_t descriptor_version;
  struct aiueos_boot_info info;
  struct efi_graphics_output_protocol *gop = 0;

  loader_console=system?system->console_out:0;
  loader_runtime=system?system->runtime_services:0;
  if (!system || !(bs = system->boot_services)) return fail(101,"AIUEOS_LOADER_FAIL system-table");
  zero_bytes(&info, sizeof(info));
  if (!prepare_netboot_qualification_return())
    return fail(119,"AIUEOS_LOADER_FAIL netboot-return-arm");
  if (system->console_out && system->console_out->output_string)
    system->console_out->output_string(system->console_out, console_message);
  debug_string("AIUEOS_LOADER_OK\n");
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
#ifdef AIUEOS_PERSISTENT_BOOT
  if (!bs->set_watchdog_timer ||
      bs->set_watchdog_timer(0,0,0,0)!=EFI_SUCCESS)
    return fail(120,"AIUEOS_LOADER_FAIL watchdog-disable");
  debug_string("AIUEOS_LOADER_WATCHDOG_DISABLED persistent-native\n");
  console_ascii("AIUEOS loader watchdog disabled for persistent native boot.\r\n");
#else
  if (bs->set_watchdog_timer &&
      bs->set_watchdog_timer(AIUEOS_QUALIFICATION_LOADER_WATCHDOG_SECONDS,
                             0xA106,0,0)==EFI_SUCCESS) {
    debug_string("AIUEOS_LOADER_WATCHDOG_ARMED\n");
    console_ascii("AIUEOS loader watchdog armed.\r\n");
  }
#endif
#endif
#ifdef AIUEOS_QUALIFICATION_FORCE_LOADER_HANG_CODE
  progress(AIUEOS_QUALIFICATION_FORCE_LOADER_HANG_CODE,
           "AIUEOS_LOADER_PROGRESS forced-hang");
  for (;;) __asm__ volatile("pause");
#endif
#ifdef AIUEOS_QUALIFICATION_FORCE_LOADER_FAILURE_CODE
  return fail(AIUEOS_QUALIFICATION_FORCE_LOADER_FAILURE_CODE,
              "AIUEOS_LOADER_FAIL forced-test");
#endif

  progress(201,"AIUEOS_LOADER_PROGRESS loaded-image-protocol");
  if (bs->handle_protocol(image, &loaded_image_guid, (void **)&loaded) != EFI_SUCCESS || !loaded)
    return fail(102,"AIUEOS_LOADER_FAIL loaded-image");
  progress(202,"AIUEOS_LOADER_PROGRESS kernel-buffer");
  if (bs->allocate_pool(2, KERNEL_BUFFER_SIZE, (void **)&kernel_file) != EFI_SUCCESS)
    return fail(103,"AIUEOS_LOADER_FAIL kernel-buffer");
  progress(203,"AIUEOS_LOADER_PROGRESS initramfs-buffer");
  if (bs->allocate_pool(2, INITRAMFS_BUFFER_SIZE, (void **)&initramfs_file) != EFI_SUCCESS)
    return fail(104,"AIUEOS_LOADER_FAIL initramfs-buffer");
  progress(204,"AIUEOS_LOADER_PROGRESS kernel-admission");
#ifdef AIUEOS_EMBEDDED_RELEASE
  efi_status admitted=read_verified_embedded(
      kernel_file,&kernel_size,initramfs_file,&initramfs_size);
  if (admitted!=EFI_SUCCESS)
    return fail(105,"AIUEOS_LOADER_FAIL embedded-admission");
#else
  efi_status admitted = read_verified_kernel(bs, loaded->device_handle, kernel_path,
                                             initramfs_path, kernel_file, &kernel_size,
                                             initramfs_file, &initramfs_size);
  if (admitted != EFI_SUCCESS) {
    /* Bounded recovery: every other filesystem volume may carry the same
       kernel path; admission still requires the identical compiled-in
       SHA-256, so a fallback can only load the expected kernel bytes. */
    efi_handle handles[16];
    uint64_t handle_bytes = sizeof(handles);
    if (bs->locate_handle(2, &simple_fs_guid, 0, &handle_bytes, handles) == EFI_SUCCESS) {
      uint64_t count = handle_bytes / sizeof(efi_handle);
      for (uint64_t i = 0; i < count && admitted != EFI_SUCCESS; i++) {
        if (handles[i] == loaded->device_handle) continue;
        admitted = read_verified_kernel(bs, handles[i], kernel_path,
                                        initramfs_path, kernel_file, &kernel_size,
                                        initramfs_file, &initramfs_size);
      }
    }
    if (admitted != EFI_SUCCESS)
      return fail(105,"AIUEOS_LOADER_FAIL kernel-admission-exhausted");
    debug_string("AIUEOS_LOADER_RECOVERY_OK kernel-from-alternate-volume sha256-v1\n");
    /* H2 rollback (JUN-140): the system chain failed admission — the boot
       that just failed was an applied update. The alternate volume that
       admitted the kernel carries the previous boot chain; restore it over
       the system ESP (the H3 copy path, read-back compared) so the machine
       returns to the previous version by itself. */
    {
      static const char16 rb_boot_path[] = u"\\EFI\\BOOT\\BOOTX64.EFI";
      efi_handle rollback_src = 0;
      efi_handle rb_handles[16];
      uint64_t rb_bytes = sizeof(rb_handles);
      if (bs->locate_handle(2, &simple_fs_guid, 0, &rb_bytes, rb_handles) == EFI_SUCCESS) {
        /* the admitting volume is the first non-own one whose kernel passed;
           re-find it by admission order: try each non-own volume again */
        uint64_t rb_count = rb_bytes / sizeof(efi_handle);
        struct efi_simple_file_system *rfs = 0;
        struct efi_file *rsrc = 0, *rdst = 0;
        for (uint64_t r = 0; r < rb_count && !rollback_src; r++) {
          if (rb_handles[r] == loaded->device_handle) continue;
          if (bs->handle_protocol(rb_handles[r], &simple_fs_guid, (void **)&rfs) != EFI_SUCCESS || !rfs)
            continue;
          if (rfs->open_volume(rfs, &rsrc) != EFI_SUCCESS || !rsrc) continue;
          struct efi_file *rp = 0;
          if (rsrc->open(rsrc, &rp, kernel_path, 1, 0) == EFI_SUCCESS && rp) {
            rp->close(rp);
            rollback_src = rb_handles[r];
          } else {
            rsrc->close(rsrc);
            rsrc = 0;
          }
        }
        if (rollback_src &&
            bs->handle_protocol(loaded->device_handle, &simple_fs_guid, (void **)&rfs) == EFI_SUCCESS &&
            rfs && rfs->open_volume(rfs, &rdst) == EFI_SUCCESS && rdst) {
          int restored = reinstall_copy(rsrc, rdst, kernel_path, bs, "rb-kernel") &&
                         reinstall_copy(rsrc, rdst, initramfs_path, bs, "rb-initrd") &&
                         reinstall_copy(rsrc, rdst, rb_boot_path, bs, "rb-bootx");
          rdst->close(rdst);
          if (restored) debug_string("AIUEOS_UPDATE_ROLLED_BACK previous-version-restored\n");
          else debug_string("AIUEOS_UPDATE_ROLLBACK_FAIL copy\n");
        }
        if (rsrc) rsrc->close(rsrc);
      }
    }
  }
#endif
  debug_string("AIUEOS_LOADER_INTEGRITY_OK sha256-v1\n");
  progress(212, "AIUEOS_LOADER_PROGRESS recovery-reinstall");
  recovery_reinstall(bs, loaded->device_handle);
  progress(213, "AIUEOS_LOADER_PROGRESS update-apply");
  update_apply(bs, loaded->device_handle);
  progress(214, "AIUEOS_LOADER_PROGRESS first-run-setup");
  setup_flow(bs, loaded->device_handle);
#ifdef AIUEOS_MODEL_NVME_SLOTS
  progress(211,"AIUEOS_LOADER_PROGRESS model-usb-to-nvme-ab");
  if (stage_model_to_nvme(bs, loaded->device_handle) != EFI_SUCCESS)
    return fail(122,"AIUEOS_LOADER_FAIL model-nvme-slot-import");
#ifdef AIUEOS_MODEL_SLOT_IMPORT_EXIT
  debug_string("AIUEOS_MODEL_SLOT_IMPORT_TEST_EXIT\n");
  fail_exit();
#endif
#endif
#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
  progress(210,"AIUEOS_LOADER_PROGRESS model-allocation-and-admission");
  if (load_verified_model(bs, loaded->device_handle, &info) != EFI_SUCCESS)
    return fail(121,"AIUEOS_LOADER_FAIL qwen38-model-admission");
#endif

  progress(205,"AIUEOS_LOADER_PROGRESS elf-validation");
  if (kernel_size < sizeof(struct elf64_header)) return fail(106,"AIUEOS_LOADER_FAIL elf-size");
  struct elf64_header *elf = (struct elf64_header *)kernel_file;
  if (elf->ident[0] != 0x7f || elf->ident[1] != 'E' || elf->ident[2] != 'L' ||
      elf->ident[3] != 'F' || elf->ident[4] != 2 || elf->machine != 62 ||
      elf->phentsize != sizeof(struct elf64_program_header))
    return fail(107,"AIUEOS_LOADER_FAIL elf-header");
  if (elf->phoff > kernel_size || elf->phnum > 32 ||
      elf->phoff + (uint64_t)elf->phnum * elf->phentsize > kernel_size)
    return fail(108,"AIUEOS_LOADER_FAIL elf-program-table");

  struct elf64_program_header *ph = (void *)(kernel_file + elf->phoff);
  uint8_t entry_is_executable = 0;
  for (uint16_t i = 0; i < elf->phnum; i++) {
    if (ph[i].type != 1) continue;
    if (ph[i].filesz > ph[i].memsz || ph[i].offset > kernel_size ||
        ph[i].filesz > kernel_size - ph[i].offset ||
        ph[i].paddr < 0x100000 || ph[i].paddr > UINT64_MAX - ph[i].memsz ||
        (ph[i].paddr & (PAGE_SIZE - 1)) != 0)
      return fail(109,"AIUEOS_LOADER_FAIL elf-segment");
    if ((ph[i].flags & 1) && elf->entry >= ph[i].paddr &&
        elf->entry - ph[i].paddr < ph[i].memsz) entry_is_executable = 1;
    progress(206,"AIUEOS_LOADER_PROGRESS segment-allocation");
    uint64_t address = ph[i].paddr;
    uint64_t pages = (ph[i].memsz + PAGE_SIZE - 1) / PAGE_SIZE;
    if (!pages || bs->allocate_pages(2, 2, pages, &address) != EFI_SUCCESS || address != ph[i].paddr)
      return fail(110,"AIUEOS_LOADER_FAIL segment-allocation");
    copy_bytes((void *)(uintptr_t)address, kernel_file + ph[i].offset, ph[i].filesz);
    zero_bytes((void *)(uintptr_t)(address + ph[i].filesz), ph[i].memsz - ph[i].filesz);
  }
  if (!entry_is_executable) return fail(111,"AIUEOS_LOADER_FAIL elf-entry");

  progress(207,"AIUEOS_LOADER_PROGRESS memory-map-buffer");
  if (bs->allocate_pool(2, MEMORY_MAP_BUFFER_SIZE, &memory_map) != EFI_SUCCESS)
    return fail(112,"AIUEOS_LOADER_FAIL map-buffer");
  info.magic = AIUEOS_BOOT_INFO_MAGIC;
#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
  info.version = AIUEOS_BOOT_INFO_VERSION_TSC_CALIBRATED;
#else
  info.version = AIUEOS_BOOT_INFO_VERSION_BASE;
#endif
  info.initramfs_base = (uint64_t)(uintptr_t)initramfs_file;
  info.initramfs_size = initramfs_size;
  /* G3: the data-disk at-rest key. Read \EFI\AIUEOS\DATA.KEY from this
     volume (the system ESP); when absent, generate one from the TSC (the
     qualification entropy source, documented as weak) and write it back so
     the key survives reboots. The data disk it protects is a different
     disk, so reading the data disk alone shows ciphertext. */
  {
    static const char16 data_key_path[] = u"\\EFI\\AIUEOS\\DATA.KEY";
    struct efi_simple_file_system *kfs = 0;
    struct efi_file *kroot = 0, *kfile = 0;
    uint64_t ksize = 0;
    int have_key = 0;
    if (bs->handle_protocol(loaded->device_handle, &simple_fs_guid, (void **)&kfs) == EFI_SUCCESS &&
        kfs && kfs->open_volume(kfs, &kroot) == EFI_SUCCESS && kroot) {
      if (kroot->open(kroot, &kfile, data_key_path, 1, 0) == EFI_SUCCESS && kfile) {
        ksize = 16;
        if (kfile->read(kfile, &ksize, info.data_key) == EFI_SUCCESS && ksize == 16) have_key = 1;
        kfile->close(kfile);
      }
      if (!have_key) {
        uint64_t tsc_a, tsc_b;
        __asm__ volatile("rdtsc" : "=a"(tsc_a), "=d"(tsc_b));
        for (int i = 0; i < 16; i++) {
          tsc_a = tsc_a * 6364136223846793005ULL + 1442695040888963407ULL;
          __asm__ volatile("rdtsc" : "=a"(tsc_a), "=d"(tsc_b));
          info.data_key[i] = (uint8_t)((tsc_a >> ((i % 8) * 8)) & 0xff);
        }
        if (kroot->open(kroot, &kfile, data_key_path,
                        3 | 0x8000000000000000ULL, 0x20) == EFI_SUCCESS && kfile) {
          uint64_t w = 16;
          kfile->write(kfile, &w, info.data_key);
          kfile->close(kfile);
        }
        have_key = 1;
        debug_string("AIUEOS_DATA_KEY_CREATED tsc-entropy weak\n");
      } else {
        debug_string("AIUEOS_DATA_KEY_LOADED\n");
      }
      kroot->close(kroot);
      if (have_key) info.data_key_tag = 0x9a7461b0d2746b31ULL;
    }
  }
  if (!initramfs_size) return fail(114,"AIUEOS_LOADER_FAIL initramfs-empty");
  info.acpi_rsdp = 0;
  const void *firmware_acpi_rsdp=0;
  struct efi_configuration_table *tables = system->configuration_table;
  for (uint64_t i = 0; i < system->number_of_table_entries; i++) {
    if (guid_equal(&tables[i].vendor_guid, &acpi20_guid)) {
      firmware_acpi_rsdp = tables[i].vendor_table;
      break;
    }
  }
  if (!firmware_acpi_rsdp) return fail(115,"AIUEOS_LOADER_FAIL acpi-rsdp");
  info.acpi_rsdp=retain_acpi_graph(bs,firmware_acpi_rsdp);
  if (!info.acpi_rsdp) return fail(115,"AIUEOS_LOADER_FAIL acpi-retain");
  debug_string("AIUEOS_ACPI_RETAIN_OK source=firmware copy=low-identity tables=APIC+DMAR\n");

  progress(208,"AIUEOS_LOADER_PROGRESS gop-discovery");
  uint8_t gop_used_protocol_scan=0;
  gop=find_graphics_output(system,bs,&gop_used_protocol_scan);
  if (!gop || !gop->mode ||
      !gop->mode->info || !gop->mode->framebuffer_base ||
      !gop->mode->framebuffer_size)
    return fail(116,"AIUEOS_LOADER_FAIL gop");
  struct efi_graphics_output_mode_info *gop_info = gop->mode->info;
  if (!gop_info->horizontal_resolution || !gop_info->vertical_resolution ||
      gop_info->pixels_per_scan_line < gop_info->horizontal_resolution ||
      (gop_info->pixel_format != 0 && gop_info->pixel_format != 1) ||
      (uint64_t)gop_info->pixels_per_scan_line * gop_info->vertical_resolution >
        gop->mode->framebuffer_size / 4)
    return fail(117,"AIUEOS_LOADER_FAIL gop-mode");
  info.framebuffer_base = gop->mode->framebuffer_base;
  info.framebuffer_size = gop->mode->framebuffer_size;
  info.framebuffer_width = gop_info->horizontal_resolution;
  info.framebuffer_height = gop_info->vertical_resolution;
  info.framebuffer_stride = gop_info->pixels_per_scan_line;
  info.framebuffer_format = gop_info->pixel_format;
  info.runtime_services = system->runtime_services;
  info.firmware_cr3 = read_cr3();
  if (gop_used_protocol_scan)
    debug_string("AIUEOS_GOP_DISCOVERY_OK source=protocol-scan\n");
  debug_string("AIUEOS_GOP_HANDOFF_OK framebuffer-v1\n");

  /* Calibrate the Qwen qualification image's invariant TSC against UEFI's
     microsecond service while Boot Services still exist. This measurement is
     handed to the kernel; no nominal CPU clock is used to turn inference
     cycles into elapsed time. Other profiles retain the v3 handoff unchanged. */
#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
  if (!bs->stall) return fail(123,"AIUEOS_LOADER_FAIL tsc-calibration-service");
  {
    uint64_t started = read_tsc();
    if (bs->stall(100000) != EFI_SUCCESS)
      return fail(123,"AIUEOS_LOADER_FAIL tsc-calibration-stall");
    uint64_t elapsed = read_tsc() - started;
    if (elapsed < 100000 || elapsed > 1000000000ULL)
      return fail(123,"AIUEOS_LOADER_FAIL tsc-calibration-bounds");
    info.tsc_hz = elapsed * 10ULL;
  }
#endif

  progress(209,"AIUEOS_LOADER_PROGRESS exit-boot-services");
  memory_map_size = MEMORY_MAP_BUFFER_SIZE;
  efi_status status = bs->get_memory_map(&memory_map_size, memory_map, &map_key,
                                         &descriptor_size, &descriptor_version);
  if (status != EFI_SUCCESS) return fail(113,"AIUEOS_LOADER_FAIL memory-map");
  info.memory_map = memory_map; info.memory_map_size = memory_map_size;
  info.descriptor_size = descriptor_size; info.descriptor_version = descriptor_version;
  status = bs->exit_boot_services(image, map_key);
  if (status != EFI_SUCCESS) return fail(118,"AIUEOS_LOADER_FAIL exit-boot-services");
  debug_string("AIUEOS_LOADER_PROGRESS kernel-entry-call code=211\n");
  persist_loader_record(0,211);
  ((kernel_entry)(uintptr_t)elf->entry)(&info);
  for (;;) __asm__ volatile("hlt");
}
