/* aiueos AArch64 UEFI loader spike.
 *
 * Mirrors the shape of os/aiueos/uefi/main.c (x86_64) to measure exactly what
 * the aarch64 port costs. The single most load-bearing difference is the
 * calling convention: on x86_64 UEFI is ms_abi, on AArch64 it is the platform
 * AAPCS64 default, so EFIAPI is empty here. Everything below is the same
 * table-walking, bounded-admission shape as the x86_64 loader: locate GOP,
 * read KERNEL.ELF off the ESP, admit only bounded ET_EXEC AArch64 PT_LOAD
 * segments, capture the firmware memory map, ExitBootServices, hand a
 * boot-info struct to the kernel.
 */
#include <stdint.h>
#include "bootinfo.h"

#define EFIAPI /* AArch64 UEFI uses AAPCS64 — no attribute, unlike x86_64 ms_abi */
#define EFI_SUCCESS 0
#define EFI_BUFFER_TOO_SMALL ((uint64_t)0x8000000000000005ULL)

typedef uint64_t efi_status;
typedef void *efi_handle;
typedef uint16_t char16;

struct efi_guid { uint32_t a; uint16_t b, c; uint8_t d[8]; };
struct efi_table_header { uint64_t signature; uint32_t revision, header_size, crc32, reserved; };

struct efi_simple_text_output;
typedef efi_status(EFIAPI *efi_output_string)(struct efi_simple_text_output *, const char16 *);
struct efi_simple_text_output { void *reset; efi_output_string output_string; void *rest[8]; };

/* --- EFI_FILE_PROTOCOL / EFI_SIMPLE_FILE_SYSTEM_PROTOCOL ---------------- */
struct efi_file;
typedef efi_status(EFIAPI *efi_file_open)(struct efi_file *, struct efi_file **,
                                          const char16 *, uint64_t, uint64_t);
typedef efi_status(EFIAPI *efi_file_close)(struct efi_file *);
typedef efi_status(EFIAPI *efi_file_read)(struct efi_file *, uint64_t *, void *);
typedef efi_status(EFIAPI *efi_file_get_position)(struct efi_file *, uint64_t *);
typedef efi_status(EFIAPI *efi_file_set_position)(struct efi_file *, uint64_t);
struct efi_file {
  uint64_t revision;
  efi_file_open open;
  efi_file_close close;
  void *delete_;
  efi_file_read read;
  void *write;
  efi_file_get_position get_position;
  efi_file_set_position set_position;
  void *get_info, *set_info, *flush;
};

struct efi_simple_file_system;
typedef efi_status(EFIAPI *efi_open_volume)(struct efi_simple_file_system *, struct efi_file **);
struct efi_simple_file_system { uint64_t revision; efi_open_volume open_volume; };

struct efi_loaded_image {
  uint32_t revision; efi_handle parent_handle; void *system_table;
  efi_handle device_handle;
  /* remaining fields unused */
};

static const struct efi_guid loaded_image_guid =
  {0x5b1b31a1, 0x9562, 0x11d2, {0x8e, 0x3f, 0x00, 0xa0, 0xc9, 0x69, 0x72, 0x3b}};
static const struct efi_guid simple_fs_guid =
  {0x964e5b22, 0x6459, 0x11d2, {0x8e, 0x39, 0x00, 0xa0, 0xc9, 0x69, 0x72, 0x3b}};
static const struct efi_guid gop_guid =
  {0x9042a9de, 0x23dc, 0x4a38, {0x96, 0xfb, 0x7a, 0xde, 0xd0, 0x80, 0x51, 0x6a}};

typedef efi_status(EFIAPI *efi_allocate_pages)(uint32_t, uint32_t, uint64_t, uint64_t *);
typedef efi_status(EFIAPI *efi_get_memory_map)(uint64_t *, void *, uint64_t *, uint64_t *, uint32_t *);
typedef efi_status(EFIAPI *efi_allocate_pool)(uint32_t, uint64_t, void **);
typedef efi_status(EFIAPI *efi_handle_protocol)(efi_handle, const struct efi_guid *, void **);
typedef efi_status(EFIAPI *efi_exit_boot_services)(efi_handle, uint64_t);
typedef efi_status(EFIAPI *efi_locate_protocol)(const struct efi_guid *, void *, void **);

struct efi_boot_services {
  struct efi_table_header header;
  void *raise_tpl, *restore_tpl;
  efi_allocate_pages allocate_pages;
  void *free_pages;
  efi_get_memory_map get_memory_map;
  efi_allocate_pool allocate_pool;
  void *free_pool;
  void *create_event, *set_timer, *wait_for_event, *signal_event, *close_event, *check_event;
  void *install_protocol_interface, *reinstall_protocol_interface, *uninstall_protocol_interface;
  efi_handle_protocol handle_protocol;
  void *reserved, *register_protocol_notify;
  void *locate_handle, *locate_device_path;
  void *install_configuration_table, *load_image, *start_image, *exit, *unload_image;
  efi_exit_boot_services exit_boot_services;
  void *get_next_monotonic_count, *stall, *set_watchdog_timer;
  void *connect_controller, *disconnect_controller;
  void *open_protocol, *close_protocol, *open_protocol_information;
  void *protocols_per_handle, *locate_handle_buffer;
  efi_locate_protocol locate_protocol;
};

struct efi_system_table {
  struct efi_table_header header;
  char16 *firmware_vendor; uint32_t firmware_revision;
  efi_handle console_in_handle; void *con_in;
  efi_handle console_out_handle; struct efi_simple_text_output *con_out;
  efi_handle standard_error_handle; void *std_err;
  void *runtime_services;
  struct efi_boot_services *boot_services;
};

struct efi_pixel_bitmask { uint32_t red, green, blue, reserved; };
struct efi_gop_mode_info {
  uint32_t version, horizontal_resolution, vertical_resolution;
  uint32_t pixel_format; struct efi_pixel_bitmask pixel_information;
  uint32_t pixels_per_scan_line;
};
struct efi_gop_mode {
  uint32_t max_mode, mode; struct efi_gop_mode_info *info;
  uint64_t size_of_info; uint64_t frame_buffer_base; uint64_t frame_buffer_size;
};
struct efi_gop { void *query_mode, *set_mode, *blt; struct efi_gop_mode *mode; };

/* --- ELF64 ------------------------------------------------------------- */
struct elf64_ehdr {
  unsigned char e_ident[16];
  uint16_t e_type, e_machine;
  uint32_t e_version;
  uint64_t e_entry, e_phoff, e_shoff;
  uint32_t e_flags;
  uint16_t e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx;
};
struct elf64_phdr {
  uint32_t p_type, p_flags;
  uint64_t p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align;
};
#define PT_LOAD 1
#define ET_EXEC 2
#define EM_AARCH64 0xB7

/* Bounded admission window: the kernel must fit the 2 MiB the kernel's own L3
   table covers. Anything larger is refused rather than silently truncated. */
#define KERNEL_MAX_SIZE 0x200000ULL
#define KERNEL_FILE_MAX 0x100000ULL
#define MEMORY_MAP_BUFFER_SIZE (128ULL * 1024ULL)
#define EFI_LOADER_DATA 2
#define ALLOCATE_ANY_PAGES 0
#define ALLOCATE_ADDRESS 2

/* --- PL011 serial ------------------------------------------------------ */
#define PL011_DR ((volatile uint32_t *)(PL011_BASE + 0x00))
#define PL011_FR ((volatile uint32_t *)(PL011_BASE + 0x18))
#define PL011_FR_TXFF (1u << 5)

static void serial_putc(char c) {
  while (*PL011_FR & PL011_FR_TXFF) { }
  *PL011_DR = (uint32_t)(unsigned char)c;
}
static void serial_puts(const char *s) {
  for (; *s; s++) { if (*s == '\n') serial_putc('\r'); serial_putc(*s); }
}
static void serial_puthex(uint64_t v) {
  serial_puts("0x");
  for (int shift = 60; shift >= 0; shift -= 4)
    serial_putc("0123456789abcdef"[(v >> shift) & 0xf]);
}
static void serial_putdec(uint64_t v) {
  char buf[21]; int i = 0;
  if (!v) { serial_putc('0'); return; }
  while (v) { buf[i++] = (char)('0' + v % 10); v /= 10; }
  while (i--) serial_putc(buf[i]);
}

static void *mem_set(void *d, int c, uint64_t n) {
  unsigned char *p = d; while (n--) *p++ = (unsigned char)c; return d;
}
static void *mem_copy(void *d, const void *s, uint64_t n) {
  unsigned char *a = d; const unsigned char *b = s; while (n--) *a++ = *b++; return d;
}

/* Read \EFI\AIUEOS\KERNEL.ELF off the volume this image was loaded from. */
static efi_status read_kernel_file(efi_handle image, struct efi_boot_services *bs,
                                   void **out_buf, uint64_t *out_size) {
  struct efi_loaded_image *li = 0;
  struct efi_simple_file_system *fs = 0;
  struct efi_file *root = 0, *file = 0;
  efi_status st;

  if ((st = bs->handle_protocol(image, &loaded_image_guid, (void **)&li)) != EFI_SUCCESS) return st;
  if ((st = bs->handle_protocol(li->device_handle, &simple_fs_guid, (void **)&fs)) != EFI_SUCCESS) return st;
  if ((st = fs->open_volume(fs, &root)) != EFI_SUCCESS) return st;

  static const char16 path[] = {'\\','E','F','I','\\','A','I','U','E','O','S','\\',
                                'K','E','R','N','E','L','.','E','L','F',0};
  if ((st = root->open(root, &file, path, 1 /* read */, 0)) != EFI_SUCCESS) return st;

  uint64_t size = 0;
  file->set_position(file, 0xFFFFFFFFFFFFFFFFULL);
  file->get_position(file, &size);
  file->set_position(file, 0);
  if (size == 0 || size > KERNEL_FILE_MAX) { file->close(file); return 1; }

  void *buf = 0;
  if ((st = bs->allocate_pool(EFI_LOADER_DATA, size, &buf)) != EFI_SUCCESS) {
    file->close(file); return st;
  }
  uint64_t read = size;
  st = file->read(file, &read, buf);
  file->close(file);
  if (st != EFI_SUCCESS || read != size) return st ? st : 1;

  *out_buf = buf; *out_size = size;
  return EFI_SUCCESS;
}

/* Bounded ET_EXEC AArch64 PT_LOAD placement. Every rejection is loud. */
static int load_kernel_image(const void *buf, uint64_t size, uint64_t *out_entry) {
  if (size < sizeof(struct elf64_ehdr)) { serial_puts("AIUEOS_KERNEL_ELF_TOO_SMALL\n"); return 0; }
  const struct elf64_ehdr *eh = buf;

  if (!(eh->e_ident[0] == 0x7f && eh->e_ident[1] == 'E' &&
        eh->e_ident[2] == 'L' && eh->e_ident[3] == 'F')) {
    serial_puts("AIUEOS_KERNEL_ELF_BAD_MAGIC\n"); return 0;
  }
  if (eh->e_ident[4] != 2 || eh->e_ident[5] != 1) {
    serial_puts("AIUEOS_KERNEL_ELF_NOT_LE64\n"); return 0;
  }
  if (eh->e_type != ET_EXEC) { serial_puts("AIUEOS_KERNEL_ELF_NOT_ET_EXEC\n"); return 0; }
  if (eh->e_machine != EM_AARCH64) { serial_puts("AIUEOS_KERNEL_ELF_NOT_AARCH64\n"); return 0; }
  if (eh->e_phnum == 0 || eh->e_phnum > 16) { serial_puts("AIUEOS_KERNEL_ELF_PHNUM\n"); return 0; }
  if (eh->e_phoff + (uint64_t)eh->e_phnum * eh->e_phentsize > size) {
    serial_puts("AIUEOS_KERNEL_ELF_PHOFF\n"); return 0;
  }

  int loaded = 0;
  for (uint16_t i = 0; i < eh->e_phnum; i++) {
    const struct elf64_phdr *ph =
      (const struct elf64_phdr *)((const unsigned char *)buf + eh->e_phoff + (uint64_t)i * eh->e_phentsize);
    if (ph->p_type != PT_LOAD) continue;
    if (ph->p_filesz > ph->p_memsz) { serial_puts("AIUEOS_KERNEL_ELF_FILESZ\n"); return 0; }
    if (ph->p_offset + ph->p_filesz > size) { serial_puts("AIUEOS_KERNEL_ELF_OFFSET\n"); return 0; }
    if (ph->p_paddr < AIUEOS_KERNEL_LOAD_BASE ||
        ph->p_paddr + ph->p_memsz > AIUEOS_KERNEL_LOAD_BASE + KERNEL_MAX_SIZE) {
      serial_puts("AIUEOS_KERNEL_ELF_OUT_OF_WINDOW paddr=");
      serial_puthex(ph->p_paddr); serial_puts("\n");
      return 0;
    }
    mem_copy((void *)ph->p_paddr, (const unsigned char *)buf + ph->p_offset, ph->p_filesz);
    if (ph->p_memsz > ph->p_filesz)
      mem_set((void *)(ph->p_paddr + ph->p_filesz), 0, ph->p_memsz - ph->p_filesz);
    loaded++;
  }
  if (!loaded) { serial_puts("AIUEOS_KERNEL_ELF_NO_PT_LOAD\n"); return 0; }
  if (eh->e_entry < AIUEOS_KERNEL_LOAD_BASE ||
      eh->e_entry >= AIUEOS_KERNEL_LOAD_BASE + KERNEL_MAX_SIZE) {
    serial_puts("AIUEOS_KERNEL_ELF_ENTRY_OUT_OF_WINDOW\n"); return 0;
  }
  *out_entry = eh->e_entry;
  serial_puts("AIUEOS_KERNEL_ELF_OK segments=");
  serial_putdec((uint64_t)loaded);
  serial_puts(" entry=");
  serial_puthex(eh->e_entry);
  serial_puts("\n");
  return 1;
}

efi_status EFIAPI efi_main(efi_handle image, struct efi_system_table *systab) {
  struct efi_boot_services *bs = systab->boot_services;

  serial_puts("AIUEOS_AARCH64_UEFI_ENTRY\n");
  serial_puts("AIUEOS_UEFI_REVISION ");
  serial_puthex(systab->header.revision);
  serial_puts("\n");

  /* GOP. Kept as a capability probe: on AArch64 `virt` the idiomatic
     virtio-gpu-pci reports PixelBltOnly with no linear aperture, so this is
     where the desktop-surface bootstrap diverges from x86_64. */
  uint64_t fb_base = 0, fb_size = 0;
  uint32_t fb_w = 0, fb_h = 0, fb_stride = 0, fb_format = 0;
  struct efi_gop *gop = 0;
  if (bs->locate_protocol(&gop_guid, 0, (void **)&gop) == EFI_SUCCESS && gop && gop->mode) {
    struct efi_gop_mode_info *info = gop->mode->info;
    fb_base = gop->mode->frame_buffer_base;
    fb_size = gop->mode->frame_buffer_size;
    fb_w = info->horizontal_resolution;
    fb_h = info->vertical_resolution;
    fb_stride = info->pixels_per_scan_line;
    fb_format = info->pixel_format;
    serial_puts("AIUEOS_GOP_OK base=");
    serial_puthex(fb_base);
    serial_puts(" size="); serial_putdec(fb_size);
    serial_puts(" w="); serial_putdec(fb_w);
    serial_puts(" h="); serial_putdec(fb_h);
    serial_puts(" stride="); serial_putdec(fb_stride);
    serial_puts(" format="); serial_putdec(fb_format);
    serial_puts("\n");
  } else {
    serial_puts("AIUEOS_GOP_ABSENT\n");
  }

  /* Reserve the kernel window by address so a collision is loud. */
  uint64_t kernel_pages = KERNEL_MAX_SIZE / 4096ULL;
  uint64_t kernel_base = AIUEOS_KERNEL_LOAD_BASE;
  if (bs->allocate_pages(ALLOCATE_ADDRESS, EFI_LOADER_DATA, kernel_pages, &kernel_base) != EFI_SUCCESS) {
    serial_puts("AIUEOS_KERNEL_WINDOW_ALLOC_FAIL\n"); goto hang;
  }
  mem_set((void *)AIUEOS_KERNEL_LOAD_BASE, 0, KERNEL_MAX_SIZE);

  void *kbuf = 0; uint64_t ksize = 0, kentry = 0;
  if (read_kernel_file(image, bs, &kbuf, &ksize) != EFI_SUCCESS) {
    serial_puts("AIUEOS_KERNEL_FILE_MISSING\n"); goto hang;
  }
  serial_puts("AIUEOS_KERNEL_FILE_OK bytes="); serial_putdec(ksize); serial_puts("\n");
  if (!load_kernel_image(kbuf, ksize, &kentry)) goto hang;

  /* Allocate boot-info and the memory-map buffer BEFORE GetMemoryMap: any
     allocation afterwards invalidates the map key ExitBootServices needs. */
  uint64_t info_addr = 0;
  if (bs->allocate_pages(ALLOCATE_ANY_PAGES, EFI_LOADER_DATA, 1, &info_addr) != EFI_SUCCESS) {
    serial_puts("AIUEOS_BOOTINFO_ALLOC_FAIL\n"); goto hang;
  }
  uint64_t map_addr = 0;
  if (bs->allocate_pages(ALLOCATE_ANY_PAGES, EFI_LOADER_DATA,
                         MEMORY_MAP_BUFFER_SIZE / 4096ULL, &map_addr) != EFI_SUCCESS) {
    serial_puts("AIUEOS_MEMMAP_ALLOC_FAIL\n"); goto hang;
  }

  uint64_t map_size = MEMORY_MAP_BUFFER_SIZE, map_key = 0, descriptor_size = 0;
  uint32_t descriptor_version = 0;
  if (bs->get_memory_map(&map_size, (void *)map_addr, &map_key,
                         &descriptor_size, &descriptor_version) != EFI_SUCCESS) {
    serial_puts("AIUEOS_MEMMAP_FAIL\n"); goto hang;
  }
  serial_puts("AIUEOS_MEMMAP_OK entries=");
  serial_putdec(map_size / descriptor_size);
  serial_puts(" descsize="); serial_putdec(descriptor_size);
  serial_puts("\n");

  if (bs->exit_boot_services(image, map_key) != EFI_SUCCESS) {
    serial_puts("AIUEOS_EXIT_BOOT_SERVICES_FAIL\n"); goto hang;
  }
  serial_puts("AIUEOS_EXIT_BOOT_SERVICES_OK\n");

  {
    uint64_t current_el;
    __asm__ volatile("mrs %0, CurrentEL" : "=r"(current_el));
    serial_puts("AIUEOS_CURRENT_EL ");
    serial_putdec((current_el >> 2) & 3);
    serial_puts("\n");
  }
  serial_puts("AIUEOS_AARCH64_UEFI_OK\n");

  /* Fill boot-info without allocating, then hand off. */
  {
    struct aiueos_boot_info *info = (struct aiueos_boot_info *)info_addr;
    mem_set(info, 0, sizeof *info);
    info->magic = AIUEOS_BOOT_INFO_MAGIC;
    info->version = AIUEOS_BOOT_INFO_VERSION;
    info->memory_map = (void *)map_addr;
    info->memory_map_size = map_size;
    info->descriptor_size = descriptor_size;
    info->descriptor_version = descriptor_version;
    info->framebuffer_base = fb_base;
    info->framebuffer_size = fb_size;
    info->framebuffer_width = fb_w;
    info->framebuffer_height = fb_h;
    info->framebuffer_stride = fb_stride;
    info->framebuffer_format = fb_format;

    serial_puts("AIUEOS_KERNEL_HANDOFF entry=");
    serial_puthex(kentry);
    serial_puts("\n");

    void (*kernel_entry)(struct aiueos_boot_info *) =
      (void (*)(struct aiueos_boot_info *))kentry;
    kernel_entry(info);
  }

hang:
  for (;;) __asm__ volatile("wfi");
  return EFI_SUCCESS;
}
