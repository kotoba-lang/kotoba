#include <stdint.h>
#include <stddef.h>

#define PCI_CONFIG_ADDRESS 0xcf8
#define PCI_CONFIG_DATA 0xcfc
#define VIRTIO_VENDOR_ID 0x1af4
#define VIRTIO_RNG_MODERN_ID 0x1044
#define VIRTIO_RNG_TRANSITIONAL_ID 0x1005
#define VIRTIO_BLK_MODERN_ID 0x1042
#define VIRTIO_BLK_TRANSITIONAL_ID 0x1001
#define PCI_STATUS_CAPABILITIES 0x10
#define PCI_CAP_VENDOR 0x09
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
#define VIRTIO_BLK_S_OK 0

extern void *aiueos_allocate_physical_page(void);
extern int aiueos_map_pci_mmio(uint64_t address, uint64_t length);
extern int aiueos_dma_test_policy_allows_unisolated(void);

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
struct virtq_avail { uint16_t flags, index, ring[1], used_event; } __attribute__((packed));
struct virtq_used_element { uint32_t id, length; } __attribute__((packed));
struct virtq_used { uint16_t flags, index; struct virtq_used_element ring[1]; uint16_t avail_event; } __attribute__((packed));
struct virtio_blk_request { uint32_t type, reserved; uint64_t sector; } __attribute__((packed));
struct aiuefs_superblock {
  uint8_t magic[8]; uint32_t version, header_size, object_count, reserved;
  uint32_t object_offset, object_length, object_checksum;
} __attribute__((packed));
static int object_store_ready;
int aiueos_object_store_ready(void) { return object_store_ready; }
static uint32_t fnv1a(const uint8_t *bytes, uint32_t length) {
  uint32_t hash = 2166136261U;
  for (uint32_t i = 0; i < length; i++) { hash ^= bytes[i]; hash *= 16777619U; }
  return hash;
}

struct virtio_caps {
  struct virtio_pci_cap common, notify, device;
  int have_common, have_notify, have_device;
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
  if (!doorbell) return 0;
  cfg->device_status |= VIRTIO_STATUS_DRIVER_OK;
  *doorbell = 0;
  for (uint32_t budget = 0; budget < 100000000U; budget++) {
    __asm__ volatile("" ::: "memory");
    if (used->index == 1) return used->ring[0].id == 0 && used->ring[0].length == 32;
    __asm__ volatile("pause");
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
  avail->ring[0] = 0; __asm__ volatile("" ::: "memory"); avail->index = 1;
  /* Split rings use a power-of-two queue; the request consumes three entries. */
  volatile uint16_t *doorbell = prepare_queue(cfg,&caps,notify_base,4,desc,avail,used);
  if (!doorbell) return 0;
  cfg->device_status |= VIRTIO_STATUS_DRIVER_OK;
  *doorbell = 0;
  for (uint32_t budget = 0; budget < 100000000U; budget++) {
    __asm__ volatile("" ::: "memory");
    if (used->index == 1) {
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
      return 1;
    }
    __asm__ volatile("pause");
  }
  return 0;
}

int aiueos_pci_enumerate(void) {
  object_store_ready = 0;
  if (!aiueos_dma_test_policy_allows_unisolated()) return 0;
  if (!cap_selftest()) return 0;
  uint32_t present = 0, virtio = 0;
  int rng_ok = 0, blk_ok = 0;
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
      }
    }
  }
  if (rng_ok && blk_ok) return 3;
  if (rng_ok) return 2;
  return present && virtio ? 1 : 0;
}
