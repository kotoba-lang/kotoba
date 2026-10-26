#include <stddef.h>
#include <stdint.h>

#define EFIAPI __attribute__((ms_abi))
#define EFI_SUCCESS 0
#define EFI_BUFFER_TOO_SMALL ((uint64_t)0x8000000000000005ULL)
#define EFI_TIMEOUT ((uint64_t)0x8000000000000012ULL)
#define EFI_NOT_FOUND ((uint64_t)0x8000000000000014ULL)
#define EFI_INVALID_PARAMETER ((uint64_t)0x8000000000000002ULL)
#define EFI_BY_PROTOCOL 2
#define EFI_BOOT_SERVICES_DATA 4
#define EFI_ALLOCATE_ANY_PAGES 0
#define EFI_PCI_IO_WIDTH_UINT8 0
#define EFI_PCI_IO_WIDTH_UINT32 2
#define EFI_PCI_IO_WIDTH_UINT64 3
#define EFI_PCI_IO_OPERATION_COMMON_BUFFER 2
#define EFI_PCI_IO_OPERATION_COMMON_BUFFER_64 5
#define EFI_PCI_IO_ATTRIBUTE_ENABLE 2
#define EFI_PCI_IO_ATTRIBUTE_MEMORY 0x0200ULL
#define EFI_PCI_IO_ATTRIBUTE_BUS_MASTER 0x0400ULL
#define EFI_PCI_IO_ATTRIBUTE_DUAL_ADDRESS_CYCLE 0x8000ULL
#define MAX_PCI_HANDLES 256
#define MAX_DBC_CONTROLLERS 5
#define MAX_PXE_HANDLES 8
#define MAX_XHCI_EXT_CAPS 50
#define MAX_XHCI_EXT_CAP_OFFSET 0x40000U
#define DBC_DMA_BYTES 4096ULL
#define DBC_RING_TRBS 16U
#define DBC_USABLE_TRBS 15U
#define DBC_DCE (1U << 31)
#define DBC_DCR (1U << 0)
#define DBC_DRC (1U << 4)
#define DBC_PORT_CCS (1U << 0)
#define DBC_PORT_PED (1U << 1)
#define DBC_PORT_CHANGE_MASK ((1U << 17) | (1U << 21) | (1U << 22) | (1U << 23))
#define DBC_TRB_NORMAL 1U
#define DBC_TRB_LINK 6U
#define DBC_TRB_TRANSFER_EVENT 32U
#define DBC_TRB_PORT_STATUS_EVENT 34U
#define DBC_TRB_IOC (1U << 5)
#define DBC_TRB_ISP (1U << 2)
#define DBC_LINK_TC (1U << 1)
#define DBC_COMPLETION_SUCCESS 1U
#define DBC_COMPLETION_SHORT_PACKET 13U
#define DBC_VENDOR_ID 0xffffU
#define DBC_PRODUCT_ID 0xa11eU
#define NETLOG_PORT 7777U
#define CONTROL_PORT 7778U
#define PXE_UDP_ANY_SRC_PORT 0x0002U
#define EFI_VARIABLE_NON_VOLATILE 0x00000001U
#define EFI_VARIABLE_BOOTSERVICE_ACCESS 0x00000002U
#define EFI_VARIABLE_RUNTIME_ACCESS 0x00000004U
#define EFI_RESET_COLD 0U
#define ACPI_MAX_TABLE_SIZE (1024U * 1024U)
#define ACPI_MAX_ROOT_ENTRIES 128U
#define ACPI_BOOTSTRAP_IDENTITY_LIMIT 0x40000000ULL

typedef uint64_t efi_status;
typedef void *efi_handle;
typedef uint16_t char16;

struct efi_guid { uint32_t a; uint16_t b, c; uint8_t d[8]; };
struct efi_table_header {
  uint64_t signature;
  uint32_t revision, header_size, crc32, reserved;
};

struct efi_simple_text_output;
typedef efi_status(EFIAPI *efi_output_string)(struct efi_simple_text_output *,
                                               const char16 *);
struct efi_simple_text_output {
  void *reset;
  efi_output_string output_string;
  void *rest[8];
};

struct efi_runtime_services;

typedef efi_status(EFIAPI *efi_handle_protocol)(efi_handle,
                                                const struct efi_guid *, void **);
typedef efi_status(EFIAPI *efi_locate_handle)(uint32_t, const struct efi_guid *,
                                              void *, uint64_t *, efi_handle *);
typedef efi_status(EFIAPI *efi_stall)(uint64_t);
struct efi_boot_services {
  struct efi_table_header header;
  void *raise_tpl, *restore_tpl, *allocate_pages, *free_pages, *get_memory_map;
  void *allocate_pool, *free_pool;
  void *create_event, *set_timer, *wait_for_event, *signal_event, *close_event,
       *check_event;
  void *install_protocol_interface, *reinstall_protocol_interface,
       *uninstall_protocol_interface;
  efi_handle_protocol handle_protocol;
  void *reserved, *register_protocol_notify;
  efi_locate_handle locate_handle;
  void *locate_device_path, *install_configuration_table, *load_image,
       *start_image, *exit, *unload_image, *exit_boot_services,
       *get_next_monotonic_count;
  efi_stall stall;
};

struct efi_system_table {
  struct efi_table_header header;
  char16 *firmware_vendor;
  uint32_t firmware_revision, padding;
  efi_handle console_in_handle;
  void *console_in;
  efi_handle console_out_handle;
  struct efi_simple_text_output *console_out;
  efi_handle standard_error_handle;
  struct efi_simple_text_output *standard_error;
  struct efi_runtime_services *runtime_services;
  struct efi_boot_services *boot_services;
  uint64_t number_of_table_entries;
  void *configuration_table;
};

struct efi_configuration_table {
  struct efi_guid vendor_guid;
  void *vendor_table;
};

struct __attribute__((packed)) acpi_rsdp_v2 {
  char signature[8];
  uint8_t checksum;
  char oem_id[6];
  uint8_t revision;
  uint32_t rsdt_address, length;
  uint64_t xsdt_address;
  uint8_t extended_checksum, reserved[3];
};

struct __attribute__((packed)) acpi_sdt_header {
  char signature[4];
  uint32_t length;
  uint8_t revision, checksum;
  char oem_id[6], oem_table_id[8];
  uint32_t oem_revision, creator_id, creator_revision;
};

typedef efi_status(EFIAPI *efi_get_variable)(char16 *, const struct efi_guid *,
                                              uint32_t *, uint64_t *, void *);
typedef efi_status(EFIAPI *efi_set_variable)(char16 *, const struct efi_guid *,
                                              uint32_t, uint64_t, void *);
typedef void(EFIAPI *efi_reset_system)(uint32_t, efi_status, uint64_t, void *);
struct efi_runtime_services {
  struct efi_table_header header;
  void *get_time, *set_time, *get_wakeup_time, *set_wakeup_time,
       *set_virtual_address_map, *convert_pointer;
  efi_get_variable get_variable;
  void *get_next_variable_name;
  efi_set_variable set_variable;
  void *get_next_high_monotonic_count;
  efi_reset_system reset_system;
  void *update_capsule, *query_capsule_capabilities, *query_variable_info;
};

_Static_assert(offsetof(struct efi_runtime_services,get_variable)==0x48,
               "UEFI runtime GetVariable offset");
_Static_assert(offsetof(struct efi_runtime_services,set_variable)==0x58,
               "UEFI runtime SetVariable offset");
_Static_assert(offsetof(struct efi_runtime_services,reset_system)==0x68,
               "UEFI runtime ResetSystem offset");

struct efi_loaded_image_protocol {
  uint32_t revision;
  efi_handle parent_handle;
  struct efi_system_table *system_table;
  efi_handle device_handle;
  void *file_path, *reserved;
  uint32_t load_options_size;
  void *load_options, *image_base;
  uint64_t image_size;
  uint32_t image_code_type, image_data_type;
  void *unload;
};

struct efi_graphics_output_mode_info {
  uint32_t version, horizontal_resolution, vertical_resolution, pixel_format;
  uint32_t pixel_information[4], pixels_per_scan_line;
};
struct efi_graphics_output_mode {
  uint32_t max_mode, mode;
  struct efi_graphics_output_mode_info *info;
  uint64_t size_of_info, framebuffer_base, framebuffer_size;
};
struct efi_graphics_output_protocol {
  void *query_mode, *set_mode, *blt;
  struct efi_graphics_output_mode *mode;
};

union efi_ip_address {
  uint8_t bytes[16];
  uint32_t words[4];
};

struct efi_pxe_base_code_protocol;
typedef efi_status(EFIAPI *efi_pxe_udp_write)(
    struct efi_pxe_base_code_protocol *, uint16_t, union efi_ip_address *,
    uint16_t *, union efi_ip_address *, union efi_ip_address *, uint16_t *,
    uint64_t *, void *, uint64_t *, void *);
typedef efi_status(EFIAPI *efi_pxe_udp_read)(
    struct efi_pxe_base_code_protocol *, uint16_t, union efi_ip_address *,
    uint16_t *, union efi_ip_address *, uint16_t *, uint64_t *, void *,
    uint64_t *, void *);
struct efi_pxe_base_code_protocol {
  uint64_t revision;
  void *start, *stop, *dhcp, *discover, *mtftp;
  efi_pxe_udp_write udp_write;
  efi_pxe_udp_read udp_read;
  void *set_ip_filter, *arp, *set_parameters, *set_station_ip,
       *set_packets, *mode;
};

_Static_assert(offsetof(struct efi_pxe_base_code_protocol,udp_write)==0x30,
               "UEFI PXE UdpWrite offset");
_Static_assert(offsetof(struct efi_pxe_base_code_protocol,udp_read)==0x38,
               "UEFI PXE UdpRead offset");

struct efi_pci_io_protocol;
typedef efi_status(EFIAPI *efi_pci_config_access)(struct efi_pci_io_protocol *,
                                                  uint32_t, uint32_t, uint64_t,
                                                  void *);
struct efi_pci_access { efi_pci_config_access read, write; };
typedef efi_status(EFIAPI *efi_pci_mem_access)(struct efi_pci_io_protocol *,
                                               uint32_t, uint8_t, uint64_t,
                                               uint64_t, void *);
struct efi_pci_mem { efi_pci_mem_access read, write; };
typedef efi_status(EFIAPI *efi_pci_map)(struct efi_pci_io_protocol *, uint32_t,
                                        void *, uint64_t *, uint64_t *, void **);
typedef efi_status(EFIAPI *efi_pci_unmap)(struct efi_pci_io_protocol *, void *);
typedef efi_status(EFIAPI *efi_pci_allocate_buffer)(struct efi_pci_io_protocol *,
                                                    uint32_t, uint32_t, uint64_t,
                                                    void **, uint64_t);
typedef efi_status(EFIAPI *efi_pci_free_buffer)(struct efi_pci_io_protocol *,
                                                uint64_t, void *);
typedef efi_status(EFIAPI *efi_pci_flush)(struct efi_pci_io_protocol *);
typedef efi_status(EFIAPI *efi_pci_get_location)(struct efi_pci_io_protocol *,
                                                 uint64_t *, uint64_t *,
                                                 uint64_t *, uint64_t *);
typedef efi_status(EFIAPI *efi_pci_attributes)(struct efi_pci_io_protocol *,
                                               uint32_t, uint64_t, uint64_t *);
struct efi_pci_io_protocol {
  void *poll_mem, *poll_io;
  struct efi_pci_mem mem, io;
  struct efi_pci_access pci;
  void *copy_mem;
  efi_pci_map map;
  efi_pci_unmap unmap;
  efi_pci_allocate_buffer allocate_buffer;
  efi_pci_free_buffer free_buffer;
  efi_pci_flush flush;
  efi_pci_get_location get_location;
  efi_pci_attributes attributes;
  void *get_bar_attributes, *set_bar_attributes;
  uint64_t rom_size;
  void *rom_image;
};

struct dbc_trb {
  uint64_t parameter;
  uint32_t status;
  uint32_t control;
} __attribute__((aligned(16)));

struct dbc_erst_entry {
  uint64_t base;
  uint32_t size;
  uint32_t reserved;
};

struct dbc_dma {
  _Alignas(64) uint8_t context[192];
  struct dbc_erst_entry erst;
  uint8_t erst_padding[48];
  _Alignas(64) struct dbc_trb event_ring[DBC_RING_TRBS];
  _Alignas(64) struct dbc_trb out_ring[DBC_RING_TRBS];
  _Alignas(64) struct dbc_trb in_ring[DBC_RING_TRBS];
  _Alignas(64) uint8_t strings[128];
  _Alignas(64) uint8_t transmit[1024];
  _Alignas(64) uint8_t receive[1024];
};

_Static_assert(offsetof(struct dbc_dma, context) == 0x000, "DbC context offset");
_Static_assert(offsetof(struct dbc_dma, erst) == 0x0c0, "DbC ERST offset");
_Static_assert(offsetof(struct dbc_dma, event_ring) == 0x100, "DbC event offset");
_Static_assert(offsetof(struct dbc_dma, out_ring) == 0x200, "DbC OUT offset");
_Static_assert(offsetof(struct dbc_dma, in_ring) == 0x300, "DbC IN offset");
_Static_assert(sizeof(struct dbc_dma) <= DBC_DMA_BYTES, "DbC DMA page overflow");

struct dbc_state {
  struct efi_pci_io_protocol *pci;
  struct dbc_dma *dma;
  void *mapping;
  uint64_t device_base;
  uint32_t capability_offset;
  uint8_t bus, device, function;
  uint8_t active, configured;
  uint8_t event_cycle, out_cycle, in_cycle;
  uint8_t event_index, out_index, in_index;
  uint8_t transmit_busy, receive_busy;
  uint32_t heartbeat_ticks, preconfigure_ticks;
  uint64_t transmit_trb, receive_trb;
  uint64_t sequence, received;
  uint32_t last_control, last_port;
};

struct aiueos_qualification_record {
  uint32_t magic;
  uint16_t version, state;
  uint32_t code, reserved;
};

static const struct efi_guid pci_io_guid =
  {0x4cf5b200,0x68b8,0x4ca5,{0x9e,0xec,0xb2,0x3e,0x3f,0x50,0x02,0x9a}};
static const struct efi_guid loaded_image_guid =
  {0x5b1b31a1,0x9562,0x11d2,{0x8e,0x3f,0x00,0xa0,0xc9,0x69,0x72,0x3b}};
static const struct efi_guid pxe_base_code_guid =
  {0x03c4e603,0xac28,0x11d3,{0x9a,0x2d,0x00,0x90,0x27,0x3f,0xc1,0x4d}};
static const struct efi_guid graphics_output_guid =
  {0x9042a9de,0x23dc,0x4a38,{0x96,0xfb,0x7a,0xde,0xd0,0x80,0x51,0x6a}};
static const struct efi_guid acpi_20_table_guid =
  {0x8868e871,0xe4f1,0x11d3,{0xbc,0x22,0x00,0x80,0xc7,0x3c,0x88,0x81}};
static const struct efi_guid acpi_10_table_guid =
  {0xeb9d2d30,0x2d88,0x11d3,{0x9a,0x16,0x00,0x90,0x27,0x3f,0xc1,0x4d}};
static const struct efi_guid global_variable_guid =
  {0x8be4df61,0x93ca,0x11d2,{0xaa,0x0d,0x00,0xe0,0x98,0x03,0x2b,0x8c}};
static const struct efi_guid qualification_guid =
  {0x73953a72,0x6627,0x4b62,{0x9a,0x9c,0x10,0x38,0xd9,0x20,0x9a,0x16}};
static char16 boot_current_name[] =
  {'B','o','o','t','C','u','r','r','e','n','t',0};
static char16 boot_next_name[] = {'B','o','o','t','N','e','x','t',0};
static char16 qualification_name[] =
  {'A','I','U','E','O','S','Q','u','a','l','i','f','i','c','a','t','i','o','n',
   'R','e','s','u','l','t',0};
static struct efi_simple_text_output *console;
static struct efi_boot_services *boot_services;
static struct efi_pxe_base_code_protocol *pxe_handles[MAX_PXE_HANDLES];
static uint32_t pxe_count;
static int32_t active_pxe=-1;
static uint64_t control_nonce;
static struct dbc_state controllers[MAX_DBC_CONTROLLERS];
static uint32_t controller_count;

static uint64_t ascii_length(const char *text) {
  uint64_t length=0;
  while (text[length]) length++;
  return length;
}

static int netlog_send_with(struct efi_pxe_base_code_protocol *pxe,
                            const char *text) {
  if (!pxe || !pxe->udp_write || !text) return 0;
  union efi_ip_address destination={{10,77,0,1}};
  uint16_t port=NETLOG_PORT;
  uint64_t bytes=ascii_length(text);
  return pxe->udp_write(pxe,0,&destination,&port,0,0,0,0,0,&bytes,
                        (void *)(uintptr_t)text)==EFI_SUCCESS;
}

static void netlog_ascii(const char *text) {
  if (active_pxe>=0 && (uint32_t)active_pxe<pxe_count &&
      netlog_send_with(pxe_handles[active_pxe],text)) return;
  active_pxe=-1;
  for (uint32_t index=0;index<pxe_count;index++) {
    if (netlog_send_with(pxe_handles[index],text)) {
      active_pxe=(int32_t)index;
      return;
    }
  }
}

static void console_ascii(const char *text) {
  netlog_ascii(text);
  char16 buffer[96];
  while (*text && console && console->output_string) {
    uint32_t count = 0;
    while (*text && count < 95) buffer[count++] = (uint8_t)*text++;
    buffer[count] = 0;
    console->output_string(console, buffer);
  }
}

static void add_pxe_handle(struct efi_pxe_base_code_protocol *pxe) {
  if (!pxe || !pxe->udp_write) return;
  for (uint32_t index=0;index<pxe_count;index++)
    if (pxe_handles[index]==pxe) return;
  if (pxe_count<MAX_PXE_HANDLES) pxe_handles[pxe_count++]=pxe;
}

static void discover_netlog(efi_handle image) {
  if (!boot_services || !boot_services->handle_protocol) return;
  struct efi_loaded_image_protocol *loaded=0;
  struct efi_pxe_base_code_protocol *pxe=0;
  if (boot_services->handle_protocol(image,&loaded_image_guid,
                                     (void **)&loaded)==EFI_SUCCESS &&
      loaded && loaded->device_handle &&
      boot_services->handle_protocol(loaded->device_handle,&pxe_base_code_guid,
                                     (void **)&pxe)==EFI_SUCCESS)
    add_pxe_handle(pxe);

  if (!boot_services->locate_handle) return;
  uint64_t bytes=0;
  efi_status status=boot_services->locate_handle(
      EFI_BY_PROTOCOL,&pxe_base_code_guid,0,&bytes,0);
  if (status!=EFI_BUFFER_TOO_SMALL || !bytes ||
      bytes>MAX_PXE_HANDLES*sizeof(efi_handle)) return;
  efi_handle handles[MAX_PXE_HANDLES];
  if (boot_services->locate_handle(EFI_BY_PROTOCOL,&pxe_base_code_guid,0,
                                   &bytes,handles)!=EFI_SUCCESS) return;
  for (uint64_t index=0;index<bytes/sizeof(efi_handle);index++) {
    pxe=0;
    if (boot_services->handle_protocol(handles[index],&pxe_base_code_guid,
                                       (void **)&pxe)==EFI_SUCCESS)
      add_pxe_handle(pxe);
  }
}

static char *append_ascii(char *output, const char *text) {
  while (*text) *output++ = *text++;
  return output;
}

static char *append_dec(char *output, uint64_t value) {
  char reverse[24];
  uint32_t count = 0;
  do {
    reverse[count++] = (char)('0' + value % 10);
    value /= 10;
  } while (value && count < sizeof(reverse));
  while (count) *output++ = reverse[--count];
  return output;
}

static char *append_hex(char *output, uint64_t value, uint32_t digits) {
  static const char hex[] = "0123456789abcdef";
  for (uint32_t index = digits; index; index--)
    *output++ = hex[(value >> ((index - 1) * 4)) & 15];
  return output;
}

static void append_line_end(char **output) {
  *(*output)++ = '\r';
  *(*output)++ = '\n';
  **output = 0;
}

static void report_graphics_output(struct efi_system_table *system) {
  if (!system || !boot_services || !boot_services->handle_protocol) return;
  struct efi_graphics_output_protocol *gop=0;
  if (system->console_out_handle)
    boot_services->handle_protocol(system->console_out_handle,
                                   &graphics_output_guid,(void **)&gop);
  if (!gop && boot_services->locate_handle) {
    efi_handle handles[32];
    uint64_t bytes=sizeof(handles);
    if (boot_services->locate_handle(EFI_BY_PROTOCOL,&graphics_output_guid,0,
                                     &bytes,handles)==EFI_SUCCESS)
      for (uint64_t index=0;index<bytes/sizeof(efi_handle) && !gop;index++)
        boot_services->handle_protocol(handles[index],&graphics_output_guid,
                                       (void **)&gop);
  }
  if (!gop || !gop->mode || !gop->mode->info) {
    console_ascii("AIUEOS_PXE_GOP state=unavailable\r\n");
    return;
  }
  struct efi_graphics_output_mode *mode=gop->mode;
  struct efi_graphics_output_mode_info *info=mode->info;
  char line[224],*output=append_ascii(line,"AIUEOS_PXE_GOP state=ready base=");
  output=append_hex(output,mode->framebuffer_base,16);
  output=append_ascii(output," bytes=");
  output=append_dec(output,mode->framebuffer_size);
  output=append_ascii(output," width=");
  output=append_dec(output,info->horizontal_resolution);
  output=append_ascii(output," height=");
  output=append_dec(output,info->vertical_resolution);
  output=append_ascii(output," stride=");
  output=append_dec(output,info->pixels_per_scan_line);
  output=append_ascii(output," format=");
  output=append_dec(output,info->pixel_format);
  append_line_end(&output);
  console_ascii(line);
}

static int guid_equal(const struct efi_guid *left,
                      const struct efi_guid *right) {
  if (!left || !right || left->a!=right->a || left->b!=right->b ||
      left->c!=right->c) return 0;
  for (uint32_t index=0;index<8;index++)
    if (left->d[index]!=right->d[index]) return 0;
  return 1;
}

static int acpi_bytes_equal(const char *left, const char *right,
                            uint32_t bytes) {
  for (uint32_t index=0;index<bytes;index++)
    if (left[index]!=right[index]) return 0;
  return 1;
}

static int acpi_checksum_ok(const void *table, uint32_t bytes) {
  if (!table || !bytes || bytes>ACPI_MAX_TABLE_SIZE) return 0;
  const uint8_t *input=table;
  uint8_t sum=0;
  for (uint32_t index=0;index<bytes;index++) sum=(uint8_t)(sum+input[index]);
  return sum==0;
}

static int acpi_sdt_header_sane(const struct acpi_sdt_header *header) {
  return header && header->length>=sizeof(*header) &&
         header->length<=ACPI_MAX_TABLE_SIZE;
}

static int acpi_below_kernel_identity_limit(uint64_t address,
                                            uint32_t bytes) {
  return address && bytes && address<ACPI_BOOTSTRAP_IDENTITY_LIMIT &&
         address<=ACPI_BOOTSTRAP_IDENTITY_LIMIT-bytes;
}

static void append_acpi_signature(char **output, const char signature[4]) {
  for (uint32_t index=0;index<4;index++) {
    uint8_t value=(uint8_t)signature[index];
    *(*output)++=(value>=0x20 && value<=0x7e) ? (char)value : '?';
  }
}

static void report_acpi_madt(const struct acpi_sdt_header *header) {
  if (!acpi_sdt_header_sane(header) || header->length<sizeof(*header)+8) return;
  const uint8_t *cursor=(const uint8_t *)header+sizeof(*header)+8;
  const uint8_t *end=(const uint8_t *)header+header->length;
  uint32_t cpus=0,ioapics=0,timer_gsi=0,first_ioapic=0,first_gsi_base=0;
  int malformed=0;
  while (cursor<end) {
    if ((uint64_t)(end-cursor)<2 || cursor[1]<2 ||
        (uint64_t)(end-cursor)<cursor[1]) {
      malformed=1;
      break;
    }
    uint8_t type=cursor[0],length=cursor[1];
    if (type==0 && length>=8) {
      uint32_t flags=*(const uint32_t *)(const void *)(cursor+4);
      if (flags&3U) cpus++;
    } else if (type==9 && length>=16) {
      uint32_t flags=*(const uint32_t *)(const void *)(cursor+8);
      if (flags&3U) cpus++;
    } else if (type==1 && length>=12) {
      uint32_t address=*(const uint32_t *)(const void *)(cursor+4);
      uint32_t gsi_base=*(const uint32_t *)(const void *)(cursor+8);
      if (!ioapics) {
        first_ioapic=address;
        first_gsi_base=gsi_base;
      }
      ioapics++;
    } else if (type==2 && length>=10 && cursor[2]==0 && cursor[3]==0) {
      timer_gsi=*(const uint32_t *)(const void *)(cursor+4);
    }
    cursor+=length;
  }
  char line[256],*output=append_ascii(line,"AIUEOS_PXE_ACPI_MADT cpus=");
  output=append_dec(output,cpus);
  output=append_ascii(output," ioapics=");
  output=append_dec(output,ioapics);
  output=append_ascii(output," first-ioapic=");
  output=append_hex(output,first_ioapic,8);
  output=append_ascii(output," first-gsi-base=");
  output=append_dec(output,first_gsi_base);
  output=append_ascii(output," timer-gsi=");
  output=append_dec(output,timer_gsi);
  output=append_ascii(output," malformed=");
  output=append_dec(output,(uint32_t)malformed);
  append_line_end(&output);
  console_ascii(line);
}

static void report_acpi_dmar(const struct acpi_sdt_header *header) {
  if (!acpi_sdt_header_sane(header) || header->length<sizeof(*header)+12) return;
  const uint8_t *bytes=(const uint8_t *)header;
  const uint8_t *cursor=bytes+sizeof(*header)+12;
  const uint8_t *end=bytes+header->length;
  uint32_t drhds=0,segment0=0,include_all=0;
  uint64_t segment0_base=0;
  int malformed=0;
  while (cursor<end) {
    if ((uint64_t)(end-cursor)<4) { malformed=1; break; }
    uint16_t type=*(const uint16_t *)(const void *)cursor;
    uint16_t length=*(const uint16_t *)(const void *)(cursor+2);
    if (length<4 || (uint64_t)(end-cursor)<length) { malformed=1; break; }
    if (type==0) {
      if (length<16) { malformed=1; break; }
      uint16_t segment=*(const uint16_t *)(const void *)(cursor+6);
      uint64_t base=*(const uint64_t *)(const void *)(cursor+8);
      drhds++;
      if (!segment0 && segment==0) {
        segment0=1;
        include_all=cursor[4]&1U;
        segment0_base=base;
      }
    }
    cursor+=length;
  }
  char line[256],*output=append_ascii(line,"AIUEOS_PXE_ACPI_DMAR width=");
  output=append_dec(output,bytes[sizeof(*header)]);
  output=append_ascii(output," drhds=");
  output=append_dec(output,drhds);
  output=append_ascii(output," segment0=");
  output=append_dec(output,segment0);
  output=append_ascii(output," include-all=");
  output=append_dec(output,include_all);
  output=append_ascii(output," register-base=");
  output=append_hex(output,segment0_base,16);
  output=append_ascii(output," malformed=");
  output=append_dec(output,(uint32_t)malformed);
  append_line_end(&output);
  console_ascii(line);
}

static void report_acpi(struct efi_system_table *system) {
  if (!system || !system->configuration_table ||
      system->number_of_table_entries>4096) {
    console_ascii("AIUEOS_PXE_ACPI_RSDP state=unavailable reason=configuration-table\r\n");
    return;
  }
  const struct efi_configuration_table *tables=system->configuration_table;
  const struct acpi_rsdp_v2 *rsdp=0;
  const char *source="none";
  for (uint64_t index=0;index<system->number_of_table_entries;index++) {
    if (guid_equal(&tables[index].vendor_guid,&acpi_20_table_guid)) {
      rsdp=tables[index].vendor_table;
      source="acpi20";
      break;
    }
    if (!rsdp && guid_equal(&tables[index].vendor_guid,&acpi_10_table_guid)) {
      rsdp=tables[index].vendor_table;
      source="acpi10";
    }
  }
  if (!rsdp) {
    console_ascii("AIUEOS_PXE_ACPI_RSDP state=unavailable reason=guid-not-found\r\n");
    return;
  }
  int signature=acpi_bytes_equal(rsdp->signature,"RSD PTR ",8);
  int checksum20=signature && acpi_checksum_ok(rsdp,20);
  uint32_t rsdp_length=rsdp->revision>=2 ? rsdp->length : 20;
  int length_sane=rsdp_length>=20 && rsdp_length<=4096;
  int checksum_full=length_sane && acpi_checksum_ok(rsdp,rsdp_length);
  char line[320],*output=append_ascii(line,"AIUEOS_PXE_ACPI_RSDP state=ready source=");
  output=append_ascii(output,source);
  output=append_ascii(output," address=");
  output=append_hex(output,(uint64_t)(uintptr_t)rsdp,16);
  output=append_ascii(output," revision=");
  output=append_dec(output,rsdp->revision);
  output=append_ascii(output," length=");
  output=append_dec(output,rsdp_length);
  output=append_ascii(output," checksum20=");
  output=append_dec(output,(uint32_t)checksum20);
  output=append_ascii(output," checksum-full=");
  output=append_dec(output,(uint32_t)checksum_full);
  output=append_ascii(output," below-1g=");
  output=append_dec(output,(uint32_t)acpi_below_kernel_identity_limit(
      (uint64_t)(uintptr_t)rsdp,rsdp_length));
  append_line_end(&output);
  console_ascii(line);
  if (!signature || !checksum20 || !length_sane || !checksum_full) return;

  uint32_t entry_width=rsdp->revision>=2 ? 8U : 4U;
  uint64_t root_address=rsdp->revision>=2 ? rsdp->xsdt_address :
                                           rsdp->rsdt_address;
  const struct acpi_sdt_header *root=(const void *)(uintptr_t)root_address;
  if (!acpi_sdt_header_sane(root)) {
    console_ascii("AIUEOS_PXE_ACPI_ROOT state=invalid reason=length\r\n");
    return;
  }
  uint32_t payload=root->length-sizeof(*root);
  uint32_t entries=payload/entry_width;
  int aligned=(payload%entry_width)==0;
  output=append_ascii(line,"AIUEOS_PXE_ACPI_ROOT state=ready signature=");
  append_acpi_signature(&output,root->signature);
  output=append_ascii(output," address=");
  output=append_hex(output,root_address,16);
  output=append_ascii(output," length=");
  output=append_dec(output,root->length);
  output=append_ascii(output," entry-width=");
  output=append_dec(output,entry_width);
  output=append_ascii(output," entries=");
  output=append_dec(output,entries);
  output=append_ascii(output," aligned=");
  output=append_dec(output,(uint32_t)aligned);
  output=append_ascii(output," checksum=");
  output=append_dec(output,(uint32_t)acpi_checksum_ok(root,root->length));
  output=append_ascii(output," below-1g=");
  output=append_dec(output,(uint32_t)acpi_below_kernel_identity_limit(
      root_address,root->length));
  append_line_end(&output);
  console_ascii(line);
  if (!aligned || entries>ACPI_MAX_ROOT_ENTRIES) {
    console_ascii("AIUEOS_PXE_ACPI_ROOT_ENUM state=refused reason=entry-bound\r\n");
    return;
  }

  const uint8_t *entry_bytes=(const uint8_t *)root+sizeof(*root);
  for (uint32_t index=0;index<entries;index++) {
    uint64_t address=entry_width==8
      ? *(const uint64_t *)(const void *)(entry_bytes+(uint64_t)index*8)
      : *(const uint32_t *)(const void *)(entry_bytes+(uint64_t)index*4);
    const struct acpi_sdt_header *candidate=(const void *)(uintptr_t)address;
    output=append_ascii(line,"AIUEOS_PXE_ACPI_TABLE index=");
    output=append_dec(output,index);
    output=append_ascii(output," address=");
    output=append_hex(output,address,16);
    output=append_ascii(output," signature=");
    append_acpi_signature(&output,candidate->signature);
    output=append_ascii(output," length=");
    output=append_dec(output,candidate->length);
    output=append_ascii(output," sane=");
    output=append_dec(output,(uint32_t)acpi_sdt_header_sane(candidate));
    output=append_ascii(output," checksum=");
    output=append_dec(output,(uint32_t)(acpi_sdt_header_sane(candidate) &&
        acpi_checksum_ok(candidate,candidate->length)));
    output=append_ascii(output," below-1g=");
    output=append_dec(output,(uint32_t)(acpi_sdt_header_sane(candidate) &&
        acpi_below_kernel_identity_limit(address,candidate->length)));
    append_line_end(&output);
    console_ascii(line);
    if (!acpi_sdt_header_sane(candidate)) continue;
    if (acpi_bytes_equal(candidate->signature,"APIC",4))
      report_acpi_madt(candidate);
    else if (acpi_bytes_equal(candidate->signature,"DMAR",4))
      report_acpi_dmar(candidate);
  }
}

static void zero_bytes(void *memory, uint64_t bytes) {
  uint8_t *target = memory;
  for (uint64_t index = 0; index < bytes; index++) target[index] = 0;
}

static void copy_bytes(void *destination, const void *source, uint64_t bytes) {
  uint8_t *target = destination;
  const uint8_t *input = source;
  for (uint64_t index = 0; index < bytes; index++) target[index] = input[index];
}

static int bytes_start_with(const uint8_t *input, uint64_t input_bytes,
                            const char *prefix) {
  uint64_t index=0;
  while (prefix[index]) {
    if (index>=input_bytes || input[index]!=(uint8_t)prefix[index]) return 0;
    index++;
  }
  return 1;
}

static int bytes_equal_ascii(const uint8_t *input, uint64_t input_bytes,
                             const char *expected) {
  uint64_t expected_bytes=ascii_length(expected);
  if (input_bytes!=expected_bytes) return 0;
  for (uint64_t index=0;index<input_bytes;index++)
    if (input[index]!=(uint8_t)expected[index]) return 0;
  return 1;
}

static uint64_t timestamp_counter(void) {
  uint32_t low=0,high=0;
  __asm__ volatile("rdtsc" : "=a"(low),"=d"(high));
  return ((uint64_t)high<<32)|low;
}

static uint64_t format_control_command(char *buffer, const char *command) {
  char *output=append_ascii(buffer,"AIUEOS_CTL_V1 nonce=");
  output=append_hex(output,control_nonce,16);
  output=append_ascii(output," command=");
  output=append_ascii(output,command);
  *output=0;
  return (uint64_t)(output-buffer);
}

static efi_status select_current_boot_next(struct efi_system_table *system,
                                           uint16_t *selected) {
  if (!system || !system->runtime_services ||
      !system->runtime_services->get_variable ||
      !system->runtime_services->set_variable || !selected)
    return EFI_NOT_FOUND;
  uint32_t attributes=0;
  uint64_t bytes=sizeof(*selected);
  efi_status status=system->runtime_services->get_variable(
      boot_current_name,&global_variable_guid,&attributes,&bytes,selected);
  if (status!=EFI_SUCCESS) return status;
  if (bytes!=sizeof(*selected)) return EFI_INVALID_PARAMETER;
  attributes=EFI_VARIABLE_NON_VOLATILE|EFI_VARIABLE_BOOTSERVICE_ACCESS|
             EFI_VARIABLE_RUNTIME_ACCESS;
  return system->runtime_services->set_variable(
      boot_next_name,&global_variable_guid,attributes,sizeof(*selected),selected);
}

static void report_qualification_result(struct efi_system_table *system) {
  if (!system || !system->runtime_services ||
      !system->runtime_services->get_variable) return;
  struct aiueos_qualification_record record={0};
  uint32_t attributes=0;
  uint64_t bytes=sizeof(record);
  if (system->runtime_services->get_variable(
          qualification_name,&qualification_guid,&attributes,&bytes,
          &record)!=EFI_SUCCESS || bytes!=sizeof(record) ||
      record.magic!=0x514b3241U || record.version!=2 || record.state>2) return;
  const char *state=record.state==1 ? "success" :
                    record.state==2 ? "failure" : "incomplete";
  char line[192],*output=append_ascii(line,"AIUEOS_QUALIFICATION_RESULT state=");
  output=append_ascii(output,state);
  output=append_ascii(output," code=");
  output=append_dec(output,record.code);
  output=append_ascii(output,
      " source=uefi-nvram internal-ssd-writes=none retained=yes");
  append_line_end(&output);
  console_ascii(line);
}

static void report_control_ready(void) {
  char line[192],*output=append_ascii(line,"AIUEOS_CONTROL_READY nonce=");
  output=append_hex(output,control_nonce,16);
  output=append_ascii(output,
      " listen=10.77.0.10:7778 source=10.77.0.1 commands=ping,reboot-pxe");
  append_line_end(&output);
  console_ascii(line);
}

static void handle_control(struct efi_system_table *system,
                           const uint8_t *payload, uint64_t payload_bytes) {
  char expected[96];
  format_control_command(expected,"ping");
  if (bytes_equal_ascii(payload,payload_bytes,expected)) {
    char line[128],*output=append_ascii(line,
        "AIUEOS_CONTROL_ACK command=ping nonce=");
    output=append_hex(output,control_nonce,16);
    append_line_end(&output);
    console_ascii(line);
    return;
  }

  format_control_command(expected,"reboot-pxe");
  if (!bytes_equal_ascii(payload,payload_bytes,expected)) {
    console_ascii("AIUEOS_CONTROL_REJECT reason=nonce-or-command\r\n");
    return;
  }

  uint16_t boot_current=0;
  efi_status status=select_current_boot_next(system,&boot_current);
  if (status!=EFI_SUCCESS) {
    char line[160],*output=append_ascii(line,
        "AIUEOS_CONTROL_FAIL command=reboot-pxe stage=set-boot-next status=");
    output=append_hex(output,status,16);
    append_line_end(&output);
    console_ascii(line);
    return;
  }

  char line[160],*output=append_ascii(line,
      "AIUEOS_CONTROL_ACK command=reboot-pxe boot_current=");
  output=append_hex(output,boot_current,4);
  output=append_ascii(output," boot_next=");
  output=append_hex(output,boot_current,4);
  append_line_end(&output);
  console_ascii(line);
  if (boot_services && boot_services->stall) boot_services->stall(200000);
  if (system && system->runtime_services && system->runtime_services->reset_system)
    system->runtime_services->reset_system(EFI_RESET_COLD,EFI_SUCCESS,0,0);
}

static void service_control(struct efi_system_table *system) {
  if (active_pxe<0 || (uint32_t)active_pxe>=pxe_count) return;
  struct efi_pxe_base_code_protocol *pxe=pxe_handles[active_pxe];
  if (!pxe || !pxe->udp_read) return;
  union efi_ip_address destination={{10,77,0,10}};
  union efi_ip_address source={{10,77,0,1}};
  uint16_t destination_port=CONTROL_PORT;
  uint8_t payload[256];
  uint64_t payload_bytes=sizeof(payload);
  efi_status status=pxe->udp_read(
      pxe,PXE_UDP_ANY_SRC_PORT,&destination,&destination_port,&source,0,
      0,0,&payload_bytes,payload);
  if (status==EFI_SUCCESS) handle_control(system,payload,payload_bytes);
  else if (status!=EFI_TIMEOUT) {
    char line[128],*output=append_ascii(line,"AIUEOS_CONTROL_READ status=");
    output=append_hex(output,status,16);
    append_line_end(&output);
    console_ascii(line);
  }
}

static void dma_barrier(void) {
  __asm__ volatile("mfence" ::: "memory");
}

static int mmio_read32(struct efi_pci_io_protocol *pci, uint64_t offset,
                       uint32_t *value) {
  return pci && pci->mem.read && value &&
    pci->mem.read(pci,EFI_PCI_IO_WIDTH_UINT32,0,offset,1,value)==EFI_SUCCESS;
}

static int mmio_write32(struct efi_pci_io_protocol *pci, uint64_t offset,
                        uint32_t value) {
  return pci && pci->mem.write &&
    pci->mem.write(pci,EFI_PCI_IO_WIDTH_UINT32,0,offset,1,&value)==EFI_SUCCESS;
}

static int mmio_read64(struct efi_pci_io_protocol *pci, uint64_t offset,
                       uint64_t *value) {
  return pci && pci->mem.read && value &&
    pci->mem.read(pci,EFI_PCI_IO_WIDTH_UINT64,0,offset,1,value)==EFI_SUCCESS;
}

static int mmio_write64(struct efi_pci_io_protocol *pci, uint64_t offset,
                        uint64_t value) {
  return pci && pci->mem.write &&
    pci->mem.write(pci,EFI_PCI_IO_WIDTH_UINT64,0,offset,1,&value)==EFI_SUCCESS;
}

static int find_dbc(struct efi_pci_io_protocol *pci, uint32_t *found) {
  uint32_t hccparams = 0;
  if (!mmio_read32(pci,0x10,&hccparams)) return 0;
  uint32_t offset = ((hccparams >> 16) & 0xffffU) << 2;
  for (uint32_t visited = 0; offset && visited < MAX_XHCI_EXT_CAPS; visited++) {
    if (offset > MAX_XHCI_EXT_CAP_OFFSET - 4) return 0;
    uint32_t header = 0;
    if (!mmio_read32(pci,offset,&header)) return 0;
    if ((header & 0xffU) == 10U) {
      *found = offset;
      return 1;
    }
    uint32_t next = (header >> 8) & 0xffU;
    if (!next || offset > MAX_XHCI_EXT_CAP_OFFSET - (next << 2)) return 0;
    offset += next << 2;
  }
  return 0;
}

static uint64_t device_address(const struct dbc_state *state, const void *pointer) {
  return state->device_base +
    (uint64_t)((const uint8_t *)pointer - (const uint8_t *)state->dma);
}

static uint8_t usb_string(uint8_t *destination, uint64_t capacity,
                          const char *ascii) {
  uint64_t length = 0;
  while (ascii[length]) length++;
  if (length > 126 || 2 + length * 2 > capacity) return 0;
  destination[0] = (uint8_t)(2 + length * 2);
  destination[1] = 3;
  for (uint64_t index = 0; index < length; index++) {
    destination[2 + index * 2] = (uint8_t)ascii[index];
    destination[3 + index * 2] = 0;
  }
  return destination[0];
}

static void initialize_link(struct dbc_state *state, struct dbc_trb *ring,
                            uint8_t cycle) {
  struct dbc_trb *link = &ring[DBC_USABLE_TRBS];
  link->parameter = device_address(state,ring);
  link->status = 0;
  link->control = (DBC_TRB_LINK << 10) | DBC_LINK_TC | cycle;
}

static void initialize_endpoint(uint8_t *context, uint32_t endpoint_type,
                                uint32_t max_burst, uint64_t ring) {
  uint32_t *words = (uint32_t *)(void *)context;
  words[0] = 0;
  words[1] = (endpoint_type << 3) | (max_burst << 8) | (1024U << 16);
  *(uint64_t *)(void *)&words[2] = ring | 1U;
  words[4] = 1024U;
}

static void report_controller(const struct dbc_state *state, const char *status) {
  char line[256], *output = append_ascii(line,"AIUEOS_DBC_CONTROLLER bdf=");
  output=append_hex(output,state->bus,2);*output++=':';
  output=append_hex(output,state->device,2);*output++='.';
  output=append_hex(output,state->function,1);
  output=append_ascii(output," offset=");
  output=append_hex(output,state->capability_offset,8);
  output=append_ascii(output," state=");
  output=append_ascii(output,status);
  append_line_end(&output);
  console_ascii(line);
}

static int enable_controller(struct dbc_state *state,
                             struct efi_boot_services *boot) {
  struct efi_pci_io_protocol *pci = state->pci;
  uint32_t capability = 0, operational_status = 0;
  if (!mmio_read32(pci,0,&capability) ||
      !mmio_read32(pci,(capability & 0xffU) + 4U,&operational_status) ||
      (operational_status & (1U << 11))) {
    report_controller(state,"controller-not-ready");
    return 0;
  }
  uint32_t control = 0;
  if (!mmio_read32(pci,state->capability_offset+0x20,&control)) {
    report_controller(state,"control-unreadable");
    return 0;
  }
  if (control & DBC_DCE) {
    if (!mmio_write32(pci,state->capability_offset+0x20,0)) {
      report_controller(state,"disable-failed");
      return 0;
    }
    if (boot->stall) boot->stall(1000);
  }
  if (!pci->allocate_buffer || !pci->map ||
      (pci->attributes &&
       pci->attributes(pci,EFI_PCI_IO_ATTRIBUTE_ENABLE,
                       EFI_PCI_IO_ATTRIBUTE_MEMORY|EFI_PCI_IO_ATTRIBUTE_BUS_MASTER,
                       0)!=EFI_SUCCESS)) {
    report_controller(state,"dma-unavailable");
    return 0;
  }
  void *host = 0;
  uint8_t dma_64=1;
  efi_status allocated = pci->allocate_buffer(
      pci,EFI_ALLOCATE_ANY_PAGES,EFI_BOOT_SERVICES_DATA,1,&host,
      EFI_PCI_IO_ATTRIBUTE_DUAL_ADDRESS_CYCLE);
  if (allocated != EFI_SUCCESS) {
    dma_64=0;
    allocated = pci->allocate_buffer(
        pci,EFI_ALLOCATE_ANY_PAGES,EFI_BOOT_SERVICES_DATA,1,&host,0);
  }
  if (allocated != EFI_SUCCESS || !host) {
    report_controller(state,"allocation-failed");
    return 0;
  }
  uint64_t bytes = DBC_DMA_BYTES, device = 0;
  void *mapping = 0;
  uint32_t operation=dma_64 ? EFI_PCI_IO_OPERATION_COMMON_BUFFER_64 :
                              EFI_PCI_IO_OPERATION_COMMON_BUFFER;
  if (pci->map(pci,operation,host,&bytes,&device,
               &mapping)!=EFI_SUCCESS || bytes != DBC_DMA_BYTES || !device) {
    if (pci->free_buffer) pci->free_buffer(pci,1,host);
    report_controller(state,"mapping-failed");
    return 0;
  }
  state->dma = host;
  state->device_base = device;
  state->mapping = mapping;
  zero_bytes(host,DBC_DMA_BYTES);

  uint8_t *strings = state->dma->strings;
  strings[0]=4;strings[1]=3;strings[2]=0x09;strings[3]=0x04;
  uint8_t language_length=4;
  uint8_t manufacturer_length=usb_string(strings+8,32,"AIUEOS");
  uint8_t product_length=usb_string(strings+40,40,"AIUEOS DbC Live");
  char serial[32], *serial_end=append_ascii(serial,"K16-");
  serial_end=append_hex(serial_end,state->bus,2);*serial_end++='-';
  serial_end=append_hex(serial_end,state->device,2);*serial_end++='-';
  serial_end=append_hex(serial_end,state->function,1);*serial_end=0;
  uint8_t serial_length=usb_string(strings+80,40,serial);
  uint64_t *info=(uint64_t *)(void *)state->dma->context;
  info[0]=device_address(state,strings);
  info[1]=device_address(state,strings+8);
  info[2]=device_address(state,strings+40);
  info[3]=device_address(state,strings+80);
  ((uint32_t *)(void *)state->dma->context)[8]=
    (uint32_t)language_length | ((uint32_t)manufacturer_length<<8) |
    ((uint32_t)product_length<<16) | ((uint32_t)serial_length<<24);

  uint32_t max_burst=(control>>16)&0xffU;
  initialize_endpoint(state->dma->context+0x40,2,max_burst,
                      device_address(state,state->dma->out_ring));
  initialize_endpoint(state->dma->context+0x80,6,max_burst,
                      device_address(state,state->dma->in_ring));
  initialize_link(state,state->dma->out_ring,0);
  initialize_link(state,state->dma->in_ring,0);
  state->dma->erst.base=device_address(state,state->dma->event_ring);
  state->dma->erst.size=DBC_RING_TRBS;
  state->event_cycle=state->out_cycle=state->in_cycle=1;

  uint64_t base=state->capability_offset;
  dma_barrier();
  if (!mmio_write32(pci,base+0x08,1) ||
      !mmio_write64(pci,base+0x10,device_address(state,&state->dma->erst)) ||
      !mmio_write64(pci,base+0x18,device_address(state,state->dma->event_ring)) ||
      !mmio_write64(pci,base+0x30,device_address(state,state->dma->context)) ||
      !mmio_write32(pci,base+0x38,(DBC_VENDOR_ID<<16)) ||
      !mmio_write32(pci,base+0x3c,(0x0100U<<16)|DBC_PRODUCT_ID)) {
    report_controller(state,"register-programming-failed");
    return 0;
  }
  if (pci->flush) pci->flush(pci);
  uint64_t context_readback=0, erst_readback=0;
  if (!mmio_read64(pci,base+0x30,&context_readback) ||
      !mmio_read64(pci,base+0x10,&erst_readback) ||
      (context_readback&~0xfULL)!=(device_address(state,state->dma->context)&~0xfULL) ||
      (erst_readback&~0xfULL)!=(device_address(state,&state->dma->erst)&~0xfULL) ||
      !mmio_write32(pci,base+0x20,DBC_DCE)) {
    report_controller(state,"enable-failed");
    return 0;
  }
  if (pci->flush) pci->flush(pci);
  state->active=1;
  state->last_control=UINT32_MAX;
  state->last_port=UINT32_MAX;
  report_controller(state,"enabled");
  return 1;
}

static void prepare_link_for_wrap(struct dbc_state *state, struct dbc_trb *ring,
                                  uint8_t index, uint8_t cycle) {
  if (index==DBC_USABLE_TRBS-1) initialize_link(state,ring,cycle);
}

static uint64_t build_heartbeat(struct dbc_state *state) {
  char message[256], *output=append_ascii(message,"AIUEOS_DBC_LIVE seq=");
  output=append_dec(output,state->sequence++);
  output=append_ascii(output," rx=");output=append_dec(output,state->received);
  output=append_ascii(output," bdf=");output=append_hex(output,state->bus,2);
  *output++=':';output=append_hex(output,state->device,2);*output++='.';
  output=append_hex(output,state->function,1);
  append_line_end(&output);
  uint64_t bytes=(uint64_t)(output-message);
  copy_bytes(state->dma->transmit,message,bytes);
  return bytes;
}

/* Per xHCI 1.2b section 7.6.3.2, the endpoint presented as IN to the Debug
   Host is cross-coupled to the DbC OUT Transfer Ring. */
static void queue_transmit(struct dbc_state *state) {
  if (state->transmit_busy) return;
  uint64_t bytes=build_heartbeat(state);
  struct dbc_trb *trb=&state->dma->out_ring[state->out_index];
  prepare_link_for_wrap(state,state->dma->out_ring,state->out_index,state->out_cycle);
  trb->parameter=device_address(state,state->dma->transmit);
  trb->status=(uint32_t)bytes;
  dma_barrier();
  trb->control=(DBC_TRB_NORMAL<<10)|DBC_TRB_IOC|state->out_cycle;
  state->transmit_trb=device_address(state,trb);
  state->transmit_busy=1;
  state->heartbeat_ticks=0;
  dma_barrier();
  if (state->pci->flush) state->pci->flush(state->pci);
  mmio_write32(state->pci,state->capability_offset+0x04,0U);
}

/* The endpoint presented as OUT to the Debug Host is cross-coupled to the
   DbC IN Transfer Ring, which owns receive buffers on the target. */
static void queue_receive(struct dbc_state *state) {
  if (state->receive_busy) return;
  struct dbc_trb *trb=&state->dma->in_ring[state->in_index];
  prepare_link_for_wrap(state,state->dma->in_ring,state->in_index,state->in_cycle);
  trb->parameter=device_address(state,state->dma->receive);
  trb->status=sizeof(state->dma->receive);
  dma_barrier();
  trb->control=(DBC_TRB_NORMAL<<10)|DBC_TRB_IOC|DBC_TRB_ISP|state->in_cycle;
  state->receive_trb=device_address(state,trb);
  state->receive_busy=1;
  dma_barrier();
  if (state->pci->flush) state->pci->flush(state->pci);
  mmio_write32(state->pci,state->capability_offset+0x04,1U<<8);
}

static void advance_ring(uint8_t *index, uint8_t *cycle) {
  (*index)++;
  if (*index==DBC_USABLE_TRBS) {
    *index=0;
    *cycle^=1U;
  }
}

static void transfer_complete(struct dbc_state *state,
                              const struct dbc_trb *event) {
  uint32_t completion=event->status>>24;
  if (event->parameter==state->transmit_trb && state->transmit_busy) {
    state->transmit_busy=0;
    advance_ring(&state->out_index,&state->out_cycle);
  } else if (event->parameter==state->receive_trb && state->receive_busy) {
    uint32_t residual=event->status&0x00ffffffU;
    uint32_t transferred=residual<=sizeof(state->dma->receive) ?
                         (uint32_t)sizeof(state->dma->receive)-residual : 0;
    if ((completion==DBC_COMPLETION_SUCCESS ||
         completion==DBC_COMPLETION_SHORT_PACKET) &&
        bytes_start_with(state->dma->receive,transferred,"AIUEOS_DBC_ACK "))
      state->received++;
    state->receive_busy=0;
    advance_ring(&state->in_index,&state->in_cycle);
  }
}

static void drain_events(struct dbc_state *state) {
  for (uint32_t count=0;count<DBC_RING_TRBS;count++) {
    volatile struct dbc_trb *volatile_event=&state->dma->event_ring[state->event_index];
    uint32_t control=volatile_event->control;
    if ((control&1U)!=state->event_cycle) break;
    struct dbc_trb event={volatile_event->parameter,volatile_event->status,control};
    uint32_t type=(event.control>>10)&0x3fU;
    if (type==DBC_TRB_TRANSFER_EVENT) transfer_complete(state,&event);
    state->event_index++;
    if (state->event_index==DBC_RING_TRBS) {
      state->event_index=0;
      state->event_cycle^=1U;
    }
    dma_barrier();
    mmio_write64(state->pci,state->capability_offset+0x18,
                 device_address(state,&state->dma->event_ring[state->event_index]));
  }
}

static void report_state(struct dbc_state *state, uint32_t control,
                         uint32_t port, uint32_t debug_status) {
  if (control==state->last_control && port==state->last_port) return;
  state->last_control=control;
  state->last_port=port;
  char line[320],*output=append_ascii(line,"AIUEOS_DBC_STATE bdf=");
  output=append_hex(output,state->bus,2);*output++=':';
  output=append_hex(output,state->device,2);*output++='.';
  output=append_hex(output,state->function,1);
  output=append_ascii(output," dce=");output=append_dec(output,(control>>31)&1U);
  output=append_ascii(output," debug_port=");output=append_dec(output,debug_status>>24);
  output=append_ascii(output," ccs=");output=append_dec(output,port&1U);
  output=append_ascii(output," ped=");output=append_dec(output,(port>>1)&1U);
  output=append_ascii(output," pls=");output=append_dec(output,(port>>5)&15U);
  output=append_ascii(output," speed=");output=append_dec(output,(port>>10)&15U);
  output=append_ascii(output," dcr=");output=append_dec(output,control&1U);
  append_line_end(&output);
  console_ascii(line);
}

static int rtl8125_mac_valid(uint32_t low, uint32_t high) {
  uint64_t mac=(uint64_t)low|((uint64_t)(high&0xffffU)<<32);
  return mac && mac!=0xffffffffffffULL && !(low&1U);
}

/* Capture the exact firmware-PXE handoff state before ExitBootServices.  This
   intentionally uses only EFI_PCI_IO_PROTOCOL reads: it does not reset the
   device, enable bus mastering, acknowledge an interrupt, alter a BAR or
   touch a descriptor.  The native driver can therefore be derived from the
   state the physical K16 is actually using instead of from an assumed board
   revision. */
static void report_rtl8125_handoff(struct efi_pci_io_protocol *pci,
                                   uint8_t bus, uint8_t device,
                                   uint8_t function, uint32_t command) {
  if (!pci || !pci->pci.read || !pci->mem.read) return;
  uint32_t bars[6]={0};
  if (pci->pci.read(pci,EFI_PCI_IO_WIDTH_UINT32,0x10,6,bars)!=EFI_SUCCESS)
    return;
  uint32_t reported=0;
  for (uint8_t bar=0;bar<6;bar++) {
    uint32_t mac_low=0,mac_high=0,tx_config=0,rx_config=0;
    uint8_t chip_command=0,phy_status=0;
    if (pci->mem.read(pci,EFI_PCI_IO_WIDTH_UINT32,bar,0x00,1,&mac_low)!=EFI_SUCCESS ||
        pci->mem.read(pci,EFI_PCI_IO_WIDTH_UINT32,bar,0x04,1,&mac_high)!=EFI_SUCCESS ||
        pci->mem.read(pci,EFI_PCI_IO_WIDTH_UINT8,bar,0x37,1,&chip_command)!=EFI_SUCCESS ||
        pci->mem.read(pci,EFI_PCI_IO_WIDTH_UINT32,bar,0x40,1,&tx_config)!=EFI_SUCCESS ||
        pci->mem.read(pci,EFI_PCI_IO_WIDTH_UINT32,bar,0x44,1,&rx_config)!=EFI_SUCCESS ||
        pci->mem.read(pci,EFI_PCI_IO_WIDTH_UINT8,bar,0x6c,1,&phy_status)!=EFI_SUCCESS ||
        !rtl8125_mac_valid(mac_low,mac_high)) continue;
    char line[320],*output=append_ascii(line,"AIUEOS_RTL8125_HANDOFF bdf=");
    output=append_hex(output,bus,2);*output++=':';
    output=append_hex(output,device,2);*output++='.';
    output=append_hex(output,function,1);
    output=append_ascii(output," bar=");output=append_dec(output,bar);
    output=append_ascii(output," command=");output=append_hex(output,command&0xffffU,4);
    output=append_ascii(output," bar-raw=");output=append_hex(output,bars[bar],8);
    output=append_ascii(output," mac=");
    for (uint32_t octet=0;octet<6;octet++) {
      if (octet) *output++=':';
      uint64_t mac=(uint64_t)mac_low|((uint64_t)mac_high<<32);
      output=append_hex(output,(mac>>(octet*8))&0xffU,2);
    }
    output=append_ascii(output," chipcmd=");output=append_hex(output,chip_command,2);
    output=append_ascii(output," txconfig=");output=append_hex(output,tx_config,8);
    output=append_ascii(output," rxconfig=");output=append_hex(output,rx_config,8);
    output=append_ascii(output," phystatus=");output=append_hex(output,phy_status,2);
    output=append_ascii(output," access=mmio-read-only");
    append_line_end(&output);
    console_ascii(line);
    reported++;
  }
  if (!reported) {
    char line[160],*output=append_ascii(line,"AIUEOS_RTL8125_HANDOFF_FAIL bdf=");
    output=append_hex(output,bus,2);*output++=':';
    output=append_hex(output,device,2);*output++='.';
    output=append_hex(output,function,1);
    output=append_ascii(output," reason=mmio-bar-unreadable access=read-only");
    append_line_end(&output);
    console_ascii(line);
  }
}

static void service_controller(struct dbc_state *state) {
  if (!state->active) return;
  uint32_t control=0,status=0,port=0;
  uint64_t base=state->capability_offset;
  if (!mmio_read32(state->pci,base+0x20,&control) ||
      !mmio_read32(state->pci,base+0x24,&status) ||
      !mmio_read32(state->pci,base+0x28,&port)) return;
  report_state(state,control,port,status);
  if (!(control&DBC_DCE)) {
    console_ascii("AIUEOS_DBC_RESET_DETECTED reenable-required\r\n");
    state->active=0;
    return;
  }
  drain_events(state);
  if ((port&DBC_PORT_CHANGE_MASK) ||
      ((port&DBC_PORT_CCS) && !(port&DBC_PORT_PED))) {
    uint32_t port_write=port&DBC_PORT_CHANGE_MASK;
    if (port&DBC_PORT_CCS) port_write|=DBC_PORT_PED;
    mmio_write32(state->pci,base+0x28,port_write);
  }
  if (control&DBC_DRC)
    mmio_write32(state->pci,base+0x20,DBC_DCE|DBC_DRC);
  state->configured=(control&DBC_DCR)!=0;
  if (state->configured) {
    state->preconfigure_ticks=0;
    queue_receive(state);
    if (state->heartbeat_ticks<100) state->heartbeat_ticks++;
    if (!state->sequence || state->heartbeat_ticks>=100) queue_transmit(state);
  } else if (!state->sequence && ++state->preconfigure_ticks>=300) {
    /* The console may have scrolled past the first state transition by the
       time a technician photographs a stalled target.  Re-emit the complete
       link state immediately before each enumeration retry so the physical
       port assignment can be diagnosed without a writable log device. */
    state->last_control=UINT32_MAX;
    state->last_port=UINT32_MAX;
    report_state(state,control,port,status);
    console_ascii("AIUEOS_DBC_ENUM_RETRY dce-toggle=yes\r\n");
    mmio_write32(state->pci,base+0x20,0);
    if (state->pci->flush) state->pci->flush(state->pci);
    if (boot_services && boot_services->stall) boot_services->stall(1000);
    mmio_write32(state->pci,base+0x20,DBC_DCE);
    if (state->pci->flush) state->pci->flush(state->pci);
    state->preconfigure_ticks=0;
  }
}

static void discover_controllers(struct efi_boot_services *boot) {
  uint64_t bytes=0;
  efi_status status=boot->locate_handle(EFI_BY_PROTOCOL,&pci_io_guid,0,&bytes,0);
  if (status!=EFI_BUFFER_TOO_SMALL || !bytes ||
      bytes>MAX_PCI_HANDLES*sizeof(efi_handle)) {
    console_ascii("AIUEOS_DBC_DISCOVERY_FAIL pci-handle-bound\r\n");
    return;
  }
  efi_handle handles[MAX_PCI_HANDLES];
  if (boot->locate_handle(EFI_BY_PROTOCOL,&pci_io_guid,0,&bytes,handles)!=EFI_SUCCESS) {
    console_ascii("AIUEOS_DBC_DISCOVERY_FAIL pci-enumeration\r\n");
    return;
  }
  for (uint64_t index=0;index<bytes/sizeof(efi_handle);index++) {
    struct efi_pci_io_protocol *pci=0;
    uint32_t config[4]={0};
    uint64_t segment=0,bus=0,device=0,function=0;
    if (boot->handle_protocol(handles[index],&pci_io_guid,(void **)&pci)!=EFI_SUCCESS ||
        !pci || !pci->pci.read || !pci->get_location ||
        pci->get_location(pci,&segment,&bus,&device,&function)!=EFI_SUCCESS ||
        pci->pci.read(pci,EFI_PCI_IO_WIDTH_UINT32,0,4,config)!=EFI_SUCCESS)
      continue;
    if ((config[0]&0xffffU)==0x10ecU && (config[0]>>16)==0x8125U)
      report_rtl8125_handoff(pci,(uint8_t)bus,(uint8_t)device,
                             (uint8_t)function,config[1]);
#ifdef AIUEOS_PXE_ONLY_CONTROL
    continue;
#endif
    if (controller_count>=MAX_DBC_CONTROLLERS ||
        ((config[2]>>8)&0xffffffU)!=0x0c0330U) continue;
    uint32_t dbc_offset=0;
    if (!find_dbc(pci,&dbc_offset)) continue;
    struct dbc_state *state=&controllers[controller_count++];
    zero_bytes(state,sizeof(*state));
    state->pci=pci;
    state->capability_offset=dbc_offset;
    state->bus=(uint8_t)bus;
    state->device=(uint8_t)device;
    state->function=(uint8_t)function;
    enable_controller(state,boot);
  }
}

efi_status EFIAPI efi_main(efi_handle image, struct efi_system_table *system) {
  (void)image;
  if (!system || !system->boot_services || !system->console_out ||
      !system->console_out->output_string) return EFI_INVALID_PARAMETER;
  console=system->console_out;
  boot_services=system->boot_services;
  control_nonce=timestamp_counter()^(uint64_t)(uintptr_t)image^
                (uint64_t)(uintptr_t)system;
  if (!control_nonce) control_nonce=0xa11e10c077000001ULL;
  discover_netlog(image);
  report_graphics_output(system);
  report_acpi(system);
  report_qualification_result(system);
#ifdef AIUEOS_PXE_ONLY_CONTROL
  console_ascii("\r\nAIUEOS PXE CONTROL (NO DISK WRITES)\r\n");
  console_ascii("AIUEOS_PXE_CONTROL_START transport=uefi-pxe-base-code internal-ssd-writes=none usb-log-writes=none\r\n");
#else
  console_ascii("\r\nAIUEOS DBC LIVE PROBE (NO DISK WRITES)\r\n");
  console_ascii("AIUEOS_DBC_START transport=xhci-dbc direction=duplex internal-ssd-writes=none usb-log-writes=none\r\n");
#endif
  discover_controllers(system->boot_services);
#ifndef AIUEOS_PXE_ONLY_CONTROL
  char summary[128],*output=append_ascii(summary,"AIUEOS_DBC_DISCOVERY controllers=");
  output=append_dec(output,controller_count);
  output=append_ascii(output," max=5\r\n");*output=0;
  console_ascii(summary);
  if (!controller_count) {
    console_ascii("AIUEOS_DBC_TERMINAL no-debug-capability\r\n");
  } else {
    console_ascii("AIUEOS_DBC_WAITING connect-or-replug-type-c mac-receiver-required\r\n");
  }
#else
  console_ascii("AIUEOS_PXE_CONTROL_READY diagnostics=gop+acpi+rtl8125+nvram control=udp\r\n");
#endif
  report_control_ready();
  for (;;) {
    for (uint32_t index=0;index<controller_count;index++)
      service_controller(&controllers[index]);
    service_control(system);
    if (system->boot_services->stall) system->boot_services->stall(10000);
  }
}
