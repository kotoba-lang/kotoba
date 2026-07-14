#include <stdint.h>
#include <stddef.h>

#define EFI_CONVENTIONAL_MEMORY 7U
#define PAGE_SIZE 4096ULL
#define IDENTITY_LIMIT 0x40000000ULL

struct aiueos_boot_info {
  uint64_t magic, version;
  void *memory_map; uint64_t memory_map_size, descriptor_size, descriptor_version;
  void *acpi_rsdp;
  uint64_t framebuffer_base, framebuffer_size;
  uint32_t framebuffer_width, framebuffer_height, framebuffer_stride, framebuffer_format;
};
struct efi_memory_descriptor_prefix {
  uint32_t type, padding;
  uint64_t physical_start, virtual_start, number_of_pages, attributes;
};
extern uint8_t aiueos_kernel_end[];

static uint64_t next_page;
static uint64_t remaining_pages;

int aiueos_physical_allocator_initialize(const struct aiueos_boot_info *boot) {
  if (!boot || !boot->memory_map ||
      boot->descriptor_size < sizeof(struct efi_memory_descriptor_prefix) ||
      boot->descriptor_size > 4096 ||
      boot->memory_map_size < boot->descriptor_size ||
      boot->memory_map_size % boot->descriptor_size != 0) return 0;

  uint64_t kernel_limit = ((uint64_t)(uintptr_t)aiueos_kernel_end + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1);
  uint8_t *cursor = boot->memory_map;
  uint8_t *end = cursor + boot->memory_map_size;
  uint64_t best_start = 0, best_pages = 0;
  while (cursor < end) {
    const struct efi_memory_descriptor_prefix *descriptor = (const void *)cursor;
    if (descriptor->type == EFI_CONVENTIONAL_MEMORY && descriptor->number_of_pages &&
        descriptor->physical_start < IDENTITY_LIMIT) {
      uint64_t start = descriptor->physical_start;
      uint64_t pages = descriptor->number_of_pages;
      if (start < kernel_limit) {
        uint64_t skipped = (kernel_limit - start + PAGE_SIZE - 1) / PAGE_SIZE;
        if (skipped >= pages) pages = 0;
        else { start += skipped * PAGE_SIZE; pages -= skipped; }
      }
      uint64_t limit_pages = (IDENTITY_LIMIT - start) / PAGE_SIZE;
      if (pages > limit_pages) pages = limit_pages;
      if (pages > best_pages) { best_start = start; best_pages = pages; }
    }
    cursor += boot->descriptor_size;
  }
  next_page = best_start;
  remaining_pages = best_pages;
  return next_page != 0 && remaining_pages >= 2;
}

void *aiueos_allocate_physical_page(void) {
  if (!remaining_pages || !next_page || next_page >= IDENTITY_LIMIT) return 0;
  uint64_t address = next_page;
  next_page += PAGE_SIZE;
  remaining_pages--;
  uint64_t *words = (uint64_t *)(uintptr_t)address;
  for (uint64_t i = 0; i < PAGE_SIZE / sizeof(uint64_t); i++) words[i] = 0;
  return (void *)(uintptr_t)address;
}
