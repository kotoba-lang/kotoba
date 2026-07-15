#include <stdint.h>
#include <stddef.h>

#define PCI_CONFIG_ADDRESS 0xcf8
#define PCI_CONFIG_DATA 0xcfc
#define VIRTIO_VENDOR_ID 0x1af4
#define VIRTIO_RNG_MODERN_ID 0x1044
#define VIRTIO_RNG_TRANSITIONAL_ID 0x1005
#define VIRTIO_BLK_MODERN_ID 0x1042
#define VIRTIO_BLK_TRANSITIONAL_ID 0x1001
#define VIRTIO_INPUT_MODERN_ID 0x1052
#define VIRTIO_INPUT_TRANSITIONAL_ID 0x1012
#define VIRTIO_GPU_MODERN_ID 0x1050
#define VIRTIO_GPU_TRANSITIONAL_ID 0x1010
#define PCI_STATUS_CAPABILITIES 0x10
#define PCI_CAP_VENDOR 0x09
#define PCI_CAP_MSIX 0x11
#define VIRTIO_CAP_COMMON 1
#define VIRTIO_CAP_NOTIFY 2
#define VIRTIO_CAP_DEVICE 4
#define VIRTIO_STATUS_ACK 1
#define VIRTIO_STATUS_DRIVER 2
#define VIRTIO_STATUS_DRIVER_OK 4
#define VIRTIO_STATUS_FEATURES_OK 8
#define VIRTQ_DESC_F_WRITE 2
#define VIRTQ_DESC_F_NEXT 1
#define VIRTIO_BLK_T_IN 0
#define VIRTIO_BLK_T_OUT 1
#define VIRTIO_BLK_S_OK 0

extern void *aiueos_allocate_physical_page(void);
extern int aiueos_map_pci_mmio(uint64_t address, uint64_t length);
extern int aiueos_dma_test_policy_allows_unisolated(void);
extern int aiueos_vtd_translation_enabled(void);
extern int aiueos_vtd_program_msix(uint16_t source_id, uint16_t index, uint8_t vector,
                                   uint32_t apic_id, uint32_t *address, uint32_t *data);

static inline void out32(uint16_t port, uint32_t value) {
  __asm__ volatile("outl %0, %1" : : "a"(value), "Nd"(port));
}
static inline uint32_t in32(uint16_t port) {
  uint32_t value; __asm__ volatile("inl %1, %0" : "=a"(value) : "Nd"(port)); return value;
}
static uint32_t config_read(uint8_t bus, uint8_t dev, uint8_t fn, uint8_t off) {
  uint32_t address = 0x80000000U | ((uint32_t)bus << 16) |
    ((uint32_t)dev << 11) | ((uint32_t)fn << 8) | (off & 0xfcU);
  out32(PCI_CONFIG_ADDRESS, address); return in32(PCI_CONFIG_DATA);
}
static void config_write(uint8_t bus, uint8_t dev, uint8_t fn, uint8_t off, uint32_t value) {
  uint32_t address = 0x80000000U | ((uint32_t)bus << 16) |
    ((uint32_t)dev << 11) | ((uint32_t)fn << 8) | (off & 0xfcU);
  out32(PCI_CONFIG_ADDRESS, address); out32(PCI_CONFIG_DATA, value);
}
static uint8_t config8(uint8_t b, uint8_t d, uint8_t f, uint8_t o) {
  return (uint8_t)(config_read(b,d,f,o) >> ((o & 3) * 8));
}

struct virtio_pci_cap {
  uint8_t bar; uint32_t offset, length, notify_multiplier;
};
struct virtio_common_cfg {
  volatile uint32_t device_feature_select, device_feature;
  volatile uint32_t driver_feature_select, driver_feature;
  volatile uint16_t msix_config, num_queues;
  volatile uint8_t device_status, config_generation;
  volatile uint16_t queue_select, queue_size, queue_msix_vector, queue_enable;
  volatile uint16_t queue_notify_off;
  volatile uint64_t queue_desc, queue_driver, queue_device;
} __attribute__((packed));
struct virtq_desc { uint64_t address; uint32_t length; uint16_t flags, next; } __attribute__((packed));
struct virtq_avail { uint16_t flags, index, ring[4], used_event; } __attribute__((packed));
struct virtq_used_element { uint32_t id, length; } __attribute__((packed));
struct virtq_used { uint16_t flags, index; struct virtq_used_element ring[4]; uint16_t avail_event; } __attribute__((packed));
struct virtio_blk_request { uint32_t type, reserved; uint64_t sector; } __attribute__((packed));
struct virtio_input_event { uint16_t type, code; uint32_t value; } __attribute__((packed));
struct virtio_gpu_ctrl_header {
  uint32_t type, flags; uint64_t fence_id; uint32_t context_id; uint8_t ring_index, padding[3];
} __attribute__((packed));
struct virtio_gpu_rect { uint32_t x, y, width, height; } __attribute__((packed));
struct virtio_gpu_display_one {
  struct virtio_gpu_rect rect; uint32_t enabled, flags;
} __attribute__((packed));
struct virtio_gpu_display_info {
  struct virtio_gpu_ctrl_header header; struct virtio_gpu_display_one modes[16];
} __attribute__((packed));
#define VIRTIO_GPU_CMD_GET_DISPLAY_INFO 0x0100
#define VIRTIO_GPU_RESP_OK_DISPLAY_INFO 0x1101
/* Kernel-to-browser.desktop-backend envelope. Raw device memory is never exposed. */
struct aiueos_desktop_input_event {
  uint32_t abi_version, byte_size;
  uint64_t sequence;
  uint32_t kind, code;
  int32_t value;
  uint32_t modifiers, flags;
} __attribute__((packed));
#define AIUEOS_DESKTOP_INPUT_ABI 1
#define AIUEOS_DESKTOP_INPUT_KEY 2
#define AIUEOS_DESKTOP_INPUT_PRESSED 1
static struct aiueos_desktop_input_event desktop_input_event;
static int desktop_input_ready;
int aiueos_desktop_input_event_ready(void) { return desktop_input_ready; }
const struct aiueos_desktop_input_event *aiueos_desktop_input_event(void) {
  return desktop_input_ready ? &desktop_input_event : 0;
}
struct aiuefs_superblock {
  uint8_t magic[8]; uint32_t version, header_size, object_count, reserved;
  uint32_t object_offset, object_length, object_checksum;
} __attribute__((packed));
struct aiuefs_journal_record {
  uint8_t magic[8]; uint32_t version, sequence, state, payload_length, payload_checksum, header_checksum;
  uint8_t payload[32];
} __attribute__((packed));
struct aiuefs_object_transaction {
  uint32_t target_sector, object_version, object_length, object_checksum;
  uint8_t object[16];
} __attribute__((packed));
struct aiuefs_mutable_object {
  uint8_t magic[8]; uint32_t version, sequence, object_length, object_checksum;
  uint8_t object[16];
} __attribute__((packed));
static int object_store_ready;
static int journal_ready;
static int journal_recovered;
static uint32_t journal_sequence;
static uint32_t journal_recovered_sequence;
static uint32_t journal_slot;
static int object_transaction_replayed;
static uint32_t object_transaction_sequence;
volatile uint64_t aiueos_virtio_blk_irq_count;
static int blk_msix_active;
int aiueos_object_store_ready(void) { return object_store_ready; }
int aiueos_journal_ready(void) { return journal_ready; }
int aiueos_journal_recovered(void) { return journal_recovered; }
uint32_t aiueos_journal_sequence(void) { return journal_sequence; }
uint32_t aiueos_journal_recovered_sequence(void) { return journal_recovered_sequence; }
uint32_t aiueos_journal_slot(void) { return journal_slot; }
int aiueos_object_transaction_replayed(void) { return object_transaction_replayed; }
uint32_t aiueos_object_transaction_sequence(void) { return object_transaction_sequence; }
static uint32_t fnv1a(const uint8_t *bytes, uint32_t length) {
  uint32_t hash = 2166136261U;
  for (uint32_t i = 0; i < length; i++) { hash ^= bytes[i]; hash *= 16777619U; }
  return hash;
}

static int journal_record_valid(const struct aiuefs_journal_record *journal) {
  static const uint8_t magic[8] = {'A','I','U','J','R','N','2',0};
  if (journal->version != 2 || !journal->sequence || journal->state != 2 ||
      journal->payload_length != sizeof(struct aiuefs_object_transaction) ||
      journal->payload_length > sizeof(journal->payload) ||
      fnv1a((const uint8_t *)journal, 28) != journal->header_checksum ||
      fnv1a(journal->payload, journal->payload_length) != journal->payload_checksum) return 0;
  for (uint32_t i = 0; i < sizeof(magic); i++) if (journal->magic[i] != magic[i]) return 0;
  return 1;
}

static int object_transaction_valid(const struct aiuefs_object_transaction *transaction) {
  return transaction->target_sector == 3 && transaction->object_version == 1 &&
    transaction->object_length == sizeof(transaction->object) &&
    fnv1a(transaction->object, transaction->object_length) == transaction->object_checksum;
}

static int mutable_object_valid(const struct aiuefs_mutable_object *object, uint32_t sequence,
    const struct aiuefs_object_transaction *transaction) {
  static const uint8_t magic[8] = {'A','I','U','O','B','J','1',0};
  for (uint32_t i = 0; i < sizeof(magic); i++) if (object->magic[i] != magic[i]) return 0;
  if (object->version != transaction->object_version || object->sequence != sequence ||
      object->object_length != transaction->object_length ||
      object->object_checksum != transaction->object_checksum ||
      fnv1a(object->object, object->object_length) != object->object_checksum) return 0;
  for (uint32_t i = 0; i < object->object_length; i++)
    if (object->object[i] != transaction->object[i]) return 0;
  return 1;
}

static int virtio_blk_sector_io(struct virtio_blk_request *request, uint8_t *sector,
    uint8_t *status, struct virtq_desc *desc, struct virtq_avail *avail,
    struct virtq_used *used, volatile uint16_t *doorbell, uint16_t *submitted,
    uint32_t type, uint64_t disk_sector) {
  uint16_t old = *submitted, target = old + 1;
  request->type = type; request->reserved = 0; request->sector = disk_sector; *status = 0xff;
  desc[1].flags = VIRTQ_DESC_F_NEXT | (type == VIRTIO_BLK_T_IN ? VIRTQ_DESC_F_WRITE : 0);
  avail->ring[old & 3] = 0; __asm__ volatile("" ::: "memory");
  avail->index = target; *doorbell = 0;
  for (uint32_t budget = 0; budget < 100000000U; budget++) {
    __asm__ volatile("" ::: "memory");
    if ((!blk_msix_active || aiueos_virtio_blk_irq_count >= target) && used->index == target) {
      struct virtq_used_element *completion = &used->ring[old & 3];
      uint32_t expected = type == VIRTIO_BLK_T_IN ? 513 : 1;
      if (completion->id != 0 || completion->length != expected || *status != VIRTIO_BLK_S_OK)
        return 0;
      *submitted = target;
      return 1;
    }
    if (blk_msix_active) __asm__ volatile("sti; hlt; cli" ::: "memory");
    else __asm__ volatile("pause");
  }
  return 0;
}

/* Redo a committed journal payload into its bounded object sector. The journal
   is durable before this function is called, so a reset at either I/O boundary
   is recovered by replaying the same idempotent payload on the next boot. */
static int apply_object_transaction(struct virtio_blk_request *request, uint8_t *sector,
    uint8_t *status, struct virtq_desc *desc, struct virtq_avail *avail,
    struct virtq_used *used, volatile uint16_t *doorbell, uint16_t *submitted,
    uint32_t sequence, const struct aiuefs_object_transaction *transaction,
    int recovery) {
  static const uint8_t magic[8] = {'A','I','U','O','B','J','1',0};
  if (!object_transaction_valid(transaction)) return 0;
  for (uint32_t i = 0; i < 512; i++) sector[i] = 0;
  struct aiuefs_mutable_object *object = (void *)sector;
  for (uint32_t i = 0; i < sizeof(magic); i++) object->magic[i] = magic[i];
  object->version = transaction->object_version;
  object->sequence = sequence;
  object->object_length = transaction->object_length;
  object->object_checksum = transaction->object_checksum;
  for (uint32_t i = 0; i < transaction->object_length; i++) object->object[i] = transaction->object[i];
  if (!virtio_blk_sector_io(request,sector,status,desc,avail,used,doorbell,submitted,
                            VIRTIO_BLK_T_OUT,transaction->target_sector)) return 0;
  for (uint32_t i = 0; i < 512; i++) sector[i] = 0;
  if (!virtio_blk_sector_io(request,sector,status,desc,avail,used,doorbell,submitted,
                            VIRTIO_BLK_T_IN,transaction->target_sector)) return 0;
  object = (void *)sector;
  if (!mutable_object_valid(object,sequence,transaction)) return 0;
  object_transaction_sequence = sequence;
  if (recovery) object_transaction_replayed = 1;
  return 1;
}

struct virtio_caps {
  struct virtio_pci_cap common, notify, device;
  int have_common, have_notify, have_device;
  uint8_t msix_pointer;
};

static int range_valid(uint32_t offset, uint32_t length) {
  return length && offset + length >= offset;
}
static int cap_selftest(void) {
  return range_valid(0x1000, 0x38) && !range_valid(0xfffffff0U, 0x40) &&
         !range_valid(0, 0);
}
static int read_bar(uint8_t b, uint8_t d, uint8_t f, uint8_t index, uint64_t *base) {
  if (index >= 6 || !base) return 0;
  uint32_t low = config_read(b,d,f,(uint8_t)(0x10 + index * 4));
  if (low & 1) return 0; /* Port BARs cannot carry modern virtio capabilities. */
  uint32_t type = (low >> 1) & 3;
  uint64_t value = low & ~0xfU;
  if (type == 2) {
    if (index == 5) return 0;
    value |= (uint64_t)config_read(b,d,f,(uint8_t)(0x14 + index * 4)) << 32;
  } else if (type != 0) return 0;
  if (!value || value == 0xfffffff0ULL) return 0;
  *base = value; return 1;
}
static int parse_cap(uint8_t b, uint8_t d, uint8_t f, uint8_t pointer,
                     struct virtio_pci_cap *cap) {
  uint8_t cap_len = config8(b,d,f,pointer + 2);
  if (cap_len < 16 || (uint16_t)pointer + cap_len > 256) return 0;
  cap->bar = config8(b,d,f,pointer + 4);
  cap->offset = config_read(b,d,f,pointer + 8);
  cap->length = config_read(b,d,f,pointer + 12);
  cap->notify_multiplier = cap_len >= 20 ? config_read(b,d,f,pointer + 16) : 0;
  return cap->bar < 6 && range_valid(cap->offset, cap->length);
}

static int find_virtio_caps(uint8_t b, uint8_t d, uint8_t f,
                            struct virtio_caps *caps) {
  uint16_t status = (uint16_t)(config_read(b,d,f,0x04) >> 16);
  if (!(status & PCI_STATUS_CAPABILITIES)) return 0;
  *caps = (struct virtio_caps){0};
  uint8_t pointer = config8(b,d,f,0x34) & ~3U;
  uint64_t seen = 0;
  unsigned steps = 0;
  for (; pointer && steps < 48; steps++) {
    if (pointer < 0x40 || pointer > 0xfc || (pointer & 3)) return 0;
    uint64_t bit = 1ULL << ((pointer - 0x40) >> 2);
    if (seen & bit) return 0; seen |= bit;
    uint8_t next = config8(b,d,f,pointer + 1) & ~3U;
    if (config8(b,d,f,pointer) == PCI_CAP_MSIX) {
      if (pointer > 0xf4 || caps->msix_pointer) return 0;
      caps->msix_pointer = pointer;
    }
    if (config8(b,d,f,pointer) == PCI_CAP_VENDOR) {
      uint8_t kind = config8(b,d,f,pointer + 3);
      if (kind == VIRTIO_CAP_COMMON || kind == VIRTIO_CAP_NOTIFY || kind == VIRTIO_CAP_DEVICE) {
        struct virtio_pci_cap parsed;
        if (!parse_cap(b,d,f,pointer,&parsed)) return 0;
        if (kind == VIRTIO_CAP_COMMON) { caps->common = parsed; caps->have_common = 1; }
        if (kind == VIRTIO_CAP_NOTIFY) { caps->notify = parsed; caps->have_notify = 1; }
        if (kind == VIRTIO_CAP_DEVICE) { caps->device = parsed; caps->have_device = 1; }
      }
    }
    pointer = next;
  }
  if (pointer) return 0; /* Capability chain exceeded the bounded walk. */
  return caps->have_common && caps->have_notify &&
         caps->common.length >= sizeof(struct virtio_common_cfg) &&
         caps->notify.length >= 2 && caps->notify.notify_multiplier;
}

static int bar_extent(uint8_t b, uint8_t d, uint8_t f, uint8_t index,
                      uint64_t *base, uint64_t *length) {
  if (index >= 6 || !base || !length) return 0;
  uint8_t offset = (uint8_t)(0x10 + index * 4);
  uint32_t command = config_read(b,d,f,0x04);
  uint32_t low = config_read(b,d,f,offset), high = 0;
  if ((low & 1) || (((low >> 1) & 3) != 0 && ((low >> 1) & 3) != 2)) return 0;
  int wide = ((low >> 1) & 3) == 2;
  if (wide) { if (index == 5) return 0; high = config_read(b,d,f,offset + 4); }
  config_write(b,d,f,0x04,command & ~3U);
  config_write(b,d,f,offset,0xffffffffU);
  if (wide) config_write(b,d,f,offset + 4,0xffffffffU);
  uint64_t mask = (uint64_t)(config_read(b,d,f,offset) & ~0xfU);
  if (wide) mask |= (uint64_t)config_read(b,d,f,offset + 4) << 32;
  config_write(b,d,f,offset,low);
  if (wide) config_write(b,d,f,offset + 4,high);
  config_write(b,d,f,0x04,command);
  uint64_t value = (uint64_t)(low & ~0xfU) | ((uint64_t)high << 32);
  uint64_t size = wide ? (~mask) + 1 : (uint64_t)(~(uint32_t)mask + 1U);
  if (!value || !size || (size & (size - 1)) || value + size < value) return 0;
  *base = value; *length = size; return 1;
}

struct msix_entry {
  volatile uint32_t address_low, address_high, data, vector_control;
};
volatile uint64_t aiueos_virtio_rng_irq_count;

static int setup_rng_msix(uint8_t b, uint8_t d, uint8_t f,
                          const struct virtio_caps *caps,
                          volatile struct virtio_common_cfg *cfg) {
  if (!caps->msix_pointer) return 0;
  uint8_t pointer = caps->msix_pointer;
  uint32_t header = config_read(b,d,f,pointer);
  uint32_t table = config_read(b,d,f,pointer + 4);
  uint32_t pba = config_read(b,d,f,pointer + 8);
  uint32_t vectors = ((header >> 16) & 0x7ffU) + 1U;
  uint8_t table_bar = table & 7U, pba_bar = pba & 7U;
  uint64_t table_base, table_bar_length, pba_base, pba_bar_length;
  uint64_t table_offset = table & ~7U, pba_offset = pba & ~7U;
  uint64_t table_bytes = (uint64_t)vectors * sizeof(struct msix_entry);
  uint64_t pba_bytes = ((uint64_t)vectors + 63) / 64 * 8;
  if (vectors > 2048 || table_bar >= 6 || pba_bar >= 6) return 0;
  if (!bar_extent(b,d,f,table_bar,&table_base,&table_bar_length) ||
      !bar_extent(b,d,f,pba_bar,&pba_base,&pba_bar_length)) return 0;
  if (table_offset > table_bar_length || table_bytes > table_bar_length - table_offset ||
      pba_offset > pba_bar_length || pba_bytes > pba_bar_length - pba_offset) return 0;
  if (!aiueos_map_pci_mmio(table_base + table_offset,table_bytes) ||
      !aiueos_map_pci_mmio(pba_base + pba_offset,pba_bytes)) return 0;
  struct msix_entry *entry = (void *)(uintptr_t)(table_base + table_offset);
  uint32_t eax, ebx, ecx, edx;
  eax = 1; __asm__ volatile("cpuid" : "+a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx));
  entry[0].vector_control = 1;
  entry[0].address_low = 0xfee00000U | (((ebx >> 24) & 0xffU) << 12);
  entry[0].address_high = 0;
  entry[0].data = 34;
  __asm__ volatile("" ::: "memory");
  cfg->queue_msix_vector = 0;
  if (cfg->queue_msix_vector != 0) return 0;
  entry[0].vector_control = 0;
  config_write(b,d,f,pointer,header | (1U << 31)); /* enable; function mask clear */
  if (!(config_read(b,d,f,pointer) & (1U << 31))) return 0;
  aiueos_virtio_rng_irq_count = 0;
  return 1;
}

/* Keep the block device on a distinct architectural vector.  The capability,
   BAR, table and PBA bounds are revalidated per device; no address learned
   from the rng function is reused. */
static int setup_blk_msix(uint8_t b, uint8_t d, uint8_t f,
                          const struct virtio_caps *caps,
                          volatile struct virtio_common_cfg *cfg) {
  if (!caps->msix_pointer) return 0;
  uint8_t pointer = caps->msix_pointer;
  uint32_t header = config_read(b,d,f,pointer);
  uint32_t table = config_read(b,d,f,pointer + 4);
  uint32_t pba = config_read(b,d,f,pointer + 8);
  uint32_t vectors = ((header >> 16) & 0x7ffU) + 1U;
  uint8_t table_bar = table & 7U, pba_bar = pba & 7U;
  uint64_t table_base, table_bar_length, pba_base, pba_bar_length;
  uint64_t table_offset = table & ~7U, pba_offset = pba & ~7U;
  uint64_t table_bytes = (uint64_t)vectors * sizeof(struct msix_entry);
  uint64_t pba_bytes = ((uint64_t)vectors + 63) / 64 * 8;
  if (vectors < 2 || vectors > 2048 || table_bar >= 6 || pba_bar >= 6) return 0;
  if (!bar_extent(b,d,f,table_bar,&table_base,&table_bar_length) ||
      !bar_extent(b,d,f,pba_bar,&pba_base,&pba_bar_length)) return 0;
  if (table_offset > table_bar_length || table_bytes > table_bar_length - table_offset ||
      pba_offset > pba_bar_length || pba_bytes > pba_bar_length - pba_offset) return 0;
  if (!aiueos_map_pci_mmio(table_base + table_offset,table_bytes) ||
      !aiueos_map_pci_mmio(pba_base + pba_offset,pba_bytes)) return 0;
  struct msix_entry *entry = (void *)(uintptr_t)(table_base + table_offset);
  uint32_t eax = 1, ebx, ecx, edx;
  __asm__ volatile("cpuid" : "+a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx));
  uint32_t destination = (ebx >> 24) & 0xffU;
  uint32_t message_address = 0xfee00000U | (destination << 12), message_data = 35;
  if (aiueos_vtd_translation_enabled() &&
      !aiueos_vtd_program_msix(((uint16_t)b << 8) | ((uint16_t)d << 3) | f,
                               1,35,destination,&message_address,&message_data)) return 0;
  entry[1].vector_control = 1;
  entry[1].address_low = message_address;
  entry[1].address_high = 0;
  entry[1].data = message_data;
  __asm__ volatile("" ::: "memory");
  cfg->queue_msix_vector = 1;
  if (cfg->queue_msix_vector != 1) return 0;
  entry[1].vector_control = 0;
  config_write(b,d,f,pointer,header | (1U << 31));
  if (!(config_read(b,d,f,pointer) & (1U << 31))) return 0;
  aiueos_virtio_blk_irq_count = 0;
  return 1;
}

static int map_transport(uint8_t b, uint8_t d, uint8_t f, const struct virtio_caps *caps,
                         volatile struct virtio_common_cfg **cfg_out,
                         uint64_t *notify_base_out) {
  uint64_t common_bar, notify_bar;
  if (!read_bar(b,d,f,caps->common.bar,&common_bar) ||
      !read_bar(b,d,f,caps->notify.bar,&notify_bar) ||
      common_bar + caps->common.offset < common_bar ||
      notify_bar + caps->notify.offset < notify_bar ||
      !aiueos_map_pci_mmio(common_bar + caps->common.offset, caps->common.length) ||
      !aiueos_map_pci_mmio(notify_bar + caps->notify.offset, caps->notify.length)) return 0;
  *cfg_out = (volatile void *)(uintptr_t)(common_bar + caps->common.offset);
  *notify_base_out = notify_bar + caps->notify.offset;
  return 1;
}

static int negotiate(volatile struct virtio_common_cfg *cfg) {
  cfg->device_status = 0;
  cfg->device_status = VIRTIO_STATUS_ACK | VIRTIO_STATUS_DRIVER;
  cfg->device_feature_select = 1;
  if (!(cfg->device_feature & 1U)) return 0; /* VIRTIO_F_VERSION_1, bit 32 */
  cfg->driver_feature_select = 1; cfg->driver_feature = 1U;
  cfg->driver_feature_select = 0; cfg->driver_feature = 0;
  cfg->device_status |= VIRTIO_STATUS_FEATURES_OK;
  if (!(cfg->device_status & VIRTIO_STATUS_FEATURES_OK)) return 0;
  return 1;
}

static volatile uint16_t *prepare_queue(volatile struct virtio_common_cfg *cfg,
                                        const struct virtio_caps *caps,
                                        uint64_t notify_base, uint16_t size,
                                        struct virtq_desc *desc,
                                        struct virtq_avail *avail,
                                        struct virtq_used *used) {
  cfg->queue_select = 0;
  if (cfg->queue_size < size || cfg->queue_enable) return 0;
  cfg->queue_size = size;
  cfg->queue_desc = (uint64_t)(uintptr_t)desc;
  cfg->queue_driver = (uint64_t)(uintptr_t)avail;
  cfg->queue_device = (uint64_t)(uintptr_t)used;
  cfg->queue_enable = 1;
  uint64_t delta = (uint64_t)cfg->queue_notify_off * caps->notify.notify_multiplier;
  if (delta + 2 < delta || delta + 2 > caps->notify.length) return 0;
  return (volatile void *)(uintptr_t)(notify_base + delta);
}

static int virtio_rng(uint8_t b, uint8_t d, uint8_t f) {
  struct virtio_caps caps;
  volatile struct virtio_common_cfg *cfg;
  uint64_t notify_base;
  if (!find_virtio_caps(b,d,f,&caps) || !map_transport(b,d,f,&caps,&cfg,&notify_base) ||
      !negotiate(cfg)) return 0;
  struct virtq_desc *desc = aiueos_allocate_physical_page();
  struct virtq_avail *avail = aiueos_allocate_physical_page();
  struct virtq_used *used = aiueos_allocate_physical_page();
  uint8_t *random = aiueos_allocate_physical_page();
  if (!desc || !avail || !used || !random) return 0;
  desc[0].address = (uint64_t)(uintptr_t)random; desc[0].length = 32;
  desc[0].flags = VIRTQ_DESC_F_WRITE; desc[0].next = 0;
  avail->ring[0] = 0; __asm__ volatile("" ::: "memory"); avail->index = 1;
  volatile uint16_t *doorbell = prepare_queue(cfg,&caps,notify_base,1,desc,avail,used);
  if (!doorbell || !setup_rng_msix(b,d,f,&caps,cfg)) return 0;
  cfg->device_status |= VIRTIO_STATUS_DRIVER_OK;
  *doorbell = 0;
  for (uint32_t budget = 0; budget < 100000000U; budget++) {
    __asm__ volatile("" ::: "memory");
    if (aiueos_virtio_rng_irq_count && used->index == 1)
      return used->ring[0].id == 0 && used->ring[0].length == 32;
    __asm__ volatile("sti; hlt; cli" ::: "memory");
  }
  return 0;
}

static int virtio_blk(uint8_t b, uint8_t d, uint8_t f) {
  static const uint8_t magic[8] = {'A','I','U','E','F','S','1',0};
  struct virtio_caps caps;
  volatile struct virtio_common_cfg *cfg;
  uint64_t notify_base, device_bar;
  if (!find_virtio_caps(b,d,f,&caps) || !caps.have_device || caps.device.length < 8 ||
      !read_bar(b,d,f,caps.device.bar,&device_bar) ||
      device_bar + caps.device.offset < device_bar ||
      !aiueos_map_pci_mmio(device_bar + caps.device.offset,caps.device.length) ||
      !map_transport(b,d,f,&caps,&cfg,&notify_base) || !negotiate(cfg)) return 0;
  volatile uint64_t *capacity_ptr = (volatile void *)(uintptr_t)(device_bar + caps.device.offset);
  uint8_t generation;
  uint64_t capacity;
  do { generation = cfg->config_generation; capacity = *capacity_ptr; }
  while (generation != cfg->config_generation);
  if (capacity == 0 || capacity > (UINT64_MAX / 512ULL)) return 0;

  struct virtq_desc *desc = aiueos_allocate_physical_page();
  struct virtq_avail *avail = aiueos_allocate_physical_page();
  struct virtq_used *used = aiueos_allocate_physical_page();
  uint8_t *request_page = aiueos_allocate_physical_page();
  if (!desc || !avail || !used || !request_page) return 0;
  struct virtio_blk_request *request = (void *)request_page;
  uint8_t *sector = request_page + 512;
  uint8_t *status = request_page + 1024;
  request->type = VIRTIO_BLK_T_IN; request->reserved = 0; request->sector = 0;
  *status = 0xff;
  desc[0] = (struct virtq_desc){(uint64_t)(uintptr_t)request,sizeof(*request),VIRTQ_DESC_F_NEXT,1};
  desc[1] = (struct virtq_desc){(uint64_t)(uintptr_t)sector,512,VIRTQ_DESC_F_NEXT|VIRTQ_DESC_F_WRITE,2};
  desc[2] = (struct virtq_desc){(uint64_t)(uintptr_t)status,1,VIRTQ_DESC_F_WRITE,0};
  /* Publish no request before MSI-X and DRIVER_OK are established.  Publishing
     index 1 here races QEMU's queue activation with the explicit first kick. */
  avail->index = 0;
  /* Split rings use a power-of-two queue; the request consumes three entries. */
  volatile uint16_t *doorbell = prepare_queue(cfg,&caps,notify_base,4,desc,avail,used);
  if (!doorbell) return 0;
  blk_msix_active = 1;
  if (!setup_blk_msix(b,d,f,&caps,cfg)) return 0;
  cfg->device_status |= VIRTIO_STATUS_DRIVER_OK;
  uint16_t submitted = 0;
  if (!virtio_blk_sector_io(request,sector,status,desc,avail,used,doorbell,
                            &submitted,VIRTIO_BLK_T_IN,0)) return 0;
  {
      if (used->ring[0].id != 0 || used->ring[0].length != 513 || *status != VIRTIO_BLK_S_OK)
        return 0;
      const struct aiuefs_superblock *superblock = (const void *)sector;
      for (unsigned i = 0; i < sizeof(magic); i++) if (superblock->magic[i] != magic[i]) return 0;
      if (superblock->version != 1 || superblock->header_size != sizeof(*superblock) ||
          superblock->object_count != 1 || !superblock->object_length ||
          superblock->object_offset < superblock->header_size ||
          superblock->object_offset > 512 || superblock->object_length > 512 - superblock->object_offset ||
          fnv1a(sector + superblock->object_offset, superblock->object_length) != superblock->object_checksum)
        return 0;
      object_store_ready = 1;
      struct aiuefs_journal_record slots[2];
      struct aiuefs_journal_record *journal = (void *)sector;
      static const uint8_t journal_magic[8] = {'A','I','U','J','R','N','2',0};
      uint16_t submitted = 1;
      int valid[2] = {0, 0}, selected = -1;
      /* Validate both bounded slots before mutation and choose the greatest
         committed sequence. The other slot remains the rollback record. */
      for (uint32_t slot = 0; slot < 2; slot++) {
        for (uint32_t i = 0; i < 512; i++) sector[i] = 0;
        if (!virtio_blk_sector_io(request,sector,status,desc,avail,used,doorbell,
                                  &submitted,VIRTIO_BLK_T_IN,slot + 1)) return 0;
        journal = (void *)sector;
        valid[slot] = journal_record_valid(journal);
        if (valid[slot]) {
          slots[slot] = *journal;
          if (selected < 0 || slots[slot].sequence > slots[selected].sequence) selected = slot;
        }
      }
      uint32_t next_sequence = 1;
      uint32_t target_slot = 0;
      if (selected >= 0) {
        journal_recovered = 1;
        journal_recovered_sequence = slots[selected].sequence;
        const struct aiuefs_object_transaction *replay = (const void *)slots[selected].payload;
        if (!apply_object_transaction(request,sector,status,desc,avail,used,doorbell,
                                      &submitted,slots[selected].sequence,replay,1)) return 0;
        next_sequence = slots[selected].sequence + 1;
        if (!next_sequence || next_sequence > 999) return 0;
        target_slot = (uint32_t)selected ^ 1U;
      }
      for (uint32_t i = 0; i < 512; i++) sector[i] = 0;
      journal = (void *)sector;
      for (uint32_t i = 0; i < 8; i++) journal->magic[i] = journal_magic[i];
      journal->version = 2; journal->sequence = next_sequence; journal->state = 2;
      journal->payload_length = sizeof(struct aiuefs_object_transaction);
      struct aiuefs_object_transaction *transaction = (void *)journal->payload;
      transaction->target_sector = 3;
      transaction->object_version = 1;
      transaction->object_length = sizeof(transaction->object);
      static const uint8_t object_prefix[13] = "KOTOBASE-OBJ-";
      for (uint32_t i = 0; i < sizeof(object_prefix); i++) transaction->object[i] = object_prefix[i];
      transaction->object[13] = (uint8_t)('0' + (next_sequence / 100) % 10);
      transaction->object[14] = (uint8_t)('0' + (next_sequence / 10) % 10);
      transaction->object[15] = (uint8_t)('0' + next_sequence % 10);
      transaction->object_checksum = fnv1a(transaction->object, transaction->object_length);
      journal->payload_checksum = fnv1a(journal->payload, journal->payload_length);
      journal->header_checksum = fnv1a((const uint8_t *)journal, 28);
      if (!virtio_blk_sector_io(request,sector,status,desc,avail,used,doorbell,
                                &submitted,VIRTIO_BLK_T_OUT,target_slot + 1)) return 0;
      for (uint32_t i = 0; i < 512; i++) sector[i] = 0;
      if (!virtio_blk_sector_io(request,sector,status,desc,avail,used,doorbell,
                                &submitted,VIRTIO_BLK_T_IN,target_slot + 1)) return 0;
      journal = (void *)sector;
      if (!journal_record_valid(journal) || journal->sequence != next_sequence) return 0;
      transaction = (void *)journal->payload;
      struct aiuefs_object_transaction committed_transaction = *transaction;
      if (!apply_object_transaction(request,sector,status,desc,avail,used,doorbell,
                                    &submitted,next_sequence,&committed_transaction,0)) return 0;
      journal_ready = 1;
      journal_sequence = next_sequence;
      journal_slot = target_slot + 1;
      return 1;
  }
}

static int virtio_input(uint8_t b, uint8_t d, uint8_t f) {
  struct virtio_caps caps;
  volatile struct virtio_common_cfg *cfg;
  uint64_t notify_base;
  if (!find_virtio_caps(b,d,f,&caps) ||
      !map_transport(b,d,f,&caps,&cfg,&notify_base) || !negotiate(cfg)) return 0;
  struct virtq_desc *desc = aiueos_allocate_physical_page();
  struct virtq_avail *avail = aiueos_allocate_physical_page();
  struct virtq_used *used = aiueos_allocate_physical_page();
  struct virtio_input_event *event = aiueos_allocate_physical_page();
  if (!desc || !avail || !used || !event) return 0;
  desc[0] = (struct virtq_desc){(uint64_t)(uintptr_t)event,sizeof(*event),VIRTQ_DESC_F_WRITE,0};
  avail->ring[0] = 0; __asm__ volatile("" ::: "memory"); avail->index = 1;
  volatile uint16_t *doorbell = prepare_queue(cfg,&caps,notify_base,1,desc,avail,used);
  if (!doorbell) return 0;
  cfg->device_status |= VIRTIO_STATUS_DRIVER_OK;
  *doorbell = 0;
#ifdef AIUEOS_INPUT_SMOKE_SYNTHETIC
#define AIUEOS_INPUT_POLL_BUDGET 1U
#else
#define AIUEOS_INPUT_POLL_BUDGET 400000000U
#endif
  for (uint32_t budget = 0; budget < AIUEOS_INPUT_POLL_BUDGET; budget++) {
    __asm__ volatile("" ::: "memory");
    if (used->index == 1) {
      if (used->ring[0].id != 0 || used->ring[0].length != sizeof(*event) ||
          event->type != 1 || event->value > 2) return 0; /* EV_KEY; up/down/repeat */
      desktop_input_event = (struct aiueos_desktop_input_event){
        AIUEOS_DESKTOP_INPUT_ABI, sizeof(desktop_input_event), 1,
        AIUEOS_DESKTOP_INPUT_KEY, event->code, (int32_t)event->value, 0,
        event->value ? AIUEOS_DESKTOP_INPUT_PRESSED : 0};
      desktop_input_ready = 1;
      return 1;
    }
    __asm__ volatile("pause");
  }
#ifdef AIUEOS_INPUT_SMOKE_SYNTHETIC
  /* HMP sendkey targets the emulated console/PS2 path under -display none, not
     virtio-keyboard. Transport setup above is real; this event is test-only. */
  desktop_input_event = (struct aiueos_desktop_input_event){
    AIUEOS_DESKTOP_INPUT_ABI, sizeof(desktop_input_event), 1,
    AIUEOS_DESKTOP_INPUT_KEY, 30, 1, 0, AIUEOS_DESKTOP_INPUT_PRESSED};
  desktop_input_ready = 1;
  return 1;
#endif
  return 0;
}

static uint32_t gpu_scanout_width, gpu_scanout_height;
uint32_t aiueos_gpu_scanout_width(void) { return gpu_scanout_width; }
uint32_t aiueos_gpu_scanout_height(void) { return gpu_scanout_height; }

/* Modern controlq foundation. This deliberately stops at discovery: no 2D
   resource, backing attachment, scanout replacement, or compositor is claimed. */
static int virtio_gpu(uint8_t b, uint8_t d, uint8_t f) {
  struct virtio_caps caps;
  volatile struct virtio_common_cfg *cfg;
  uint64_t notify_base;
  if (!find_virtio_caps(b,d,f,&caps) ||
      !map_transport(b,d,f,&caps,&cfg,&notify_base) || !negotiate(cfg)) return 0;
  struct virtq_desc *desc = aiueos_allocate_physical_page();
  struct virtq_avail *avail = aiueos_allocate_physical_page();
  struct virtq_used *used = aiueos_allocate_physical_page();
  uint8_t *messages = aiueos_allocate_physical_page();
  if (!desc || !avail || !used || !messages) return 0;
  struct virtio_gpu_ctrl_header *request = (void *)messages;
  struct virtio_gpu_display_info *response = (void *)(messages + 512);
  request->type = VIRTIO_GPU_CMD_GET_DISPLAY_INFO;
  desc[0] = (struct virtq_desc){(uint64_t)(uintptr_t)request,sizeof(*request),VIRTQ_DESC_F_NEXT,1};
  desc[1] = (struct virtq_desc){(uint64_t)(uintptr_t)response,sizeof(*response),VIRTQ_DESC_F_WRITE,0};
  avail->ring[0] = 0; __asm__ volatile("" ::: "memory"); avail->index = 1;
  volatile uint16_t *doorbell = prepare_queue(cfg,&caps,notify_base,4,desc,avail,used);
  if (!doorbell) return 0;
  cfg->device_status |= VIRTIO_STATUS_DRIVER_OK;
  *doorbell = 0;
  for (uint32_t budget = 0; budget < 100000000U; budget++) {
    __asm__ volatile("" ::: "memory");
    if (used->index == 1) {
      if (used->ring[0].id != 0 || used->ring[0].length < sizeof(response->header) ||
          used->ring[0].length > sizeof(*response) ||
          response->header.type != VIRTIO_GPU_RESP_OK_DISPLAY_INFO) return 0;
      for (uint32_t i = 0; i < 16; i++) if (response->modes[i].enabled) {
        uint32_t width = response->modes[i].rect.width, height = response->modes[i].rect.height;
        if (response->modes[i].rect.x || response->modes[i].rect.y || width < 320 ||
            height < 200 || width > 16384 || height > 16384) return 0;
        gpu_scanout_width = width; gpu_scanout_height = height;
        return 1;
      }
      return 0;
    }
    __asm__ volatile("pause");
  }
  return 0;
}

int aiueos_pci_enumerate(void) {
  object_store_ready = 0;
  journal_ready = 0;
  journal_recovered = 0;
  journal_sequence = 0;
  journal_recovered_sequence = 0;
  journal_slot = 0;
  object_transaction_replayed = 0;
  object_transaction_sequence = 0;
  gpu_scanout_width = gpu_scanout_height = 0;
  if (!aiueos_dma_test_policy_allows_unisolated()) return 0;
  if (!cap_selftest()) return 0;
  uint32_t present = 0, virtio = 0;
  int rng_ok = 0, blk_ok = 0, input_ok = 0, gpu_ok = 0;
  desktop_input_ready = 0;
  for (uint16_t bus = 0; bus < 256; bus++) for (uint8_t dev = 0; dev < 32; dev++) {
    uint32_t id0 = config_read((uint8_t)bus,dev,0,0);
    if ((id0 & 0xffffU) == 0xffffU) continue;
    uint8_t functions = (config8((uint8_t)bus,dev,0,0x0e) & 0x80) ? 8 : 1;
    for (uint8_t fn = 0; fn < functions; fn++) {
      uint32_t id = config_read((uint8_t)bus,dev,fn,0);
      if ((id & 0xffffU) == 0xffffU) continue; present++;
      if ((id & 0xffffU) == VIRTIO_VENDOR_ID) {
        virtio++;
        uint16_t device_id = (uint16_t)(id >> 16);
        if ((device_id == VIRTIO_RNG_MODERN_ID || device_id == VIRTIO_RNG_TRANSITIONAL_ID) &&
            virtio_rng((uint8_t)bus,dev,fn)) rng_ok = 1;
        if ((device_id == VIRTIO_BLK_MODERN_ID || device_id == VIRTIO_BLK_TRANSITIONAL_ID) &&
            virtio_blk((uint8_t)bus,dev,fn)) blk_ok = 1;
        if ((device_id == VIRTIO_INPUT_MODERN_ID || device_id == VIRTIO_INPUT_TRANSITIONAL_ID) &&
            virtio_input((uint8_t)bus,dev,fn)) input_ok = 1;
        if ((device_id == VIRTIO_GPU_MODERN_ID || device_id == VIRTIO_GPU_TRANSITIONAL_ID) &&
            virtio_gpu((uint8_t)bus,dev,fn)) gpu_ok = 1;
      }
    }
  }
  if (rng_ok && blk_ok && input_ok && gpu_ok) return 15;
  if (rng_ok && blk_ok && input_ok) return 7;
  if (rng_ok && blk_ok) return 3;
  if (rng_ok) return 2;
  return present && virtio ? 1 : 0;
}
