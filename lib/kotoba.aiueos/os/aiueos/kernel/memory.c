#include <stdint.h>
#include <stddef.h>
#include "../include/boot_info.h"

#define EFI_CONVENTIONAL_MEMORY 7U
#define PAGE_SIZE 4096ULL
#define IDENTITY_LIMIT 0x40000000ULL

struct efi_memory_descriptor_prefix {
  uint32_t type, padding;
  uint64_t physical_start, virtual_start, number_of_pages, attributes;
};
extern uint8_t aiueos_kernel_end[];

static uint64_t next_page;
static uint64_t remaining_pages;
static void *free_pages;
static volatile uint8_t allocator_lock;
static uint64_t allocator_reuse_count;
#define ALLOCATION_RECORDS 256
struct allocation_record { void *page; uint8_t active; };
static struct allocation_record allocation_records[ALLOCATION_RECORDS];

/* The record-table decision -- which slot to claim for a fresh page, and
 * whether a page being freed is the one a live record names -- lives in the
 * compiler-emitted Kotoba object kotoba_aiueos_allocator_plan (allocator-plan
 * allow-list entry, kernel-object ABI). C keeps the mechanism: the lock, the
 * next_page/remaining_pages advance, the free-list pointer write, and zeroing.
 *
 *   request == 0 : return the one-based index of a free record, or 0 if the
 *                  table is full.
 *   request != 0 : HIGH 32 bits = page address, LOW 16 bits = record index to
 *                  release. Returns 1 only when that live record names that
 *                  page; 0 on double free / unknown / mismatch.
 *
 * The table layout matches struct allocation_record: page @0..7, active @8,
 * stride 16, and the object requires exactly (length,count,stride) =
 * (4096,256,16). */
extern uint64_t kotoba_aiueos_allocator_plan(uint64_t table, uint64_t length,
  uint64_t count, uint64_t stride, uint64_t request);

static void lock(void) { while (__atomic_test_and_set(&allocator_lock,__ATOMIC_ACQUIRE)) __asm__ volatile("pause"); }
static void unlock(void) { __atomic_clear(&allocator_lock,__ATOMIC_RELEASE); }
static void zero_page(void *page) {
  uint64_t *words=page;
  for (uint64_t i=0;i<PAGE_SIZE/sizeof(uint64_t);i++) words[i]=0;
}

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
  free_pages=0; allocator_lock=0; allocator_reuse_count=0;
  for (uint32_t i=0;i<ALLOCATION_RECORDS;i++) allocation_records[i]=(struct allocation_record){0,0};
  return next_page != 0 && remaining_pages >= 32;
}

void *aiueos_allocate_physical_page(void) {
  lock(); void *page=0;
  if (free_pages) {
    page=free_pages; free_pages=*(void **)free_pages; allocator_reuse_count++;
    for (uint32_t i=0;i<ALLOCATION_RECORDS;i++)
      if (allocation_records[i].page==page) { allocation_records[i].active=1; break; }
  } else if (remaining_pages && next_page && next_page<IDENTITY_LIMIT) {
    /* The record to claim is a Kotoba decision: scan the bounded 4096,256,16
     * table for the first free record, and refuse when full. C only advances
     * next_page / consumes remaining_pages and stores the record. */
    uint64_t slot = kotoba_aiueos_allocator_plan(
      (uint64_t)(uintptr_t)allocation_records, ALLOCATION_RECORDS*16ULL,
      ALLOCATION_RECORDS, 16ULL, 0);
    if (slot >= 1 && slot <= ALLOCATION_RECORDS) {
      uint32_t i = (uint32_t)(slot - 1);
      if (!allocation_records[i].page && !allocation_records[i].active) {
        page=(void *)(uintptr_t)next_page; next_page+=PAGE_SIZE; remaining_pages--;
        allocation_records[i]=(struct allocation_record){page,1};
      }
    }
  }
  if (page) zero_page(page); unlock(); return page;
}

/* Reserve one boot-lifetime contiguous arena without consuming the small
   individually-freeable allocation record table.  Model decode state is
   never returned during this native boot, so recording tens of thousands of
   component pages would add metadata without enabling a valid free path. */
void *aiueos_allocate_contiguous_physical_pages(uint64_t page_count) {
  if (!page_count || page_count > UINT64_MAX / PAGE_SIZE) return 0;
  lock();
  uint64_t bytes = page_count * PAGE_SIZE;
  uint64_t start = next_page;
  if (!start || page_count > remaining_pages ||
      start >= IDENTITY_LIMIT || bytes > IDENTITY_LIMIT - start) {
    unlock();
    return 0;
  }
  next_page += bytes;
  remaining_pages -= page_count;
  unlock();
  uint8_t *memory = (uint8_t *)(uintptr_t)start;
  for (uint64_t page = 0; page < page_count; page++)
    zero_page(memory + page * PAGE_SIZE);
  return memory;
}

int aiueos_free_physical_page(void *page) {
  if (!page || ((uintptr_t)page&(PAGE_SIZE-1)) || (uintptr_t)page>=IDENTITY_LIMIT) return 0;
  lock();
  /* Find the record that names this page (mechanism: a bounded linear scan),
   * then ask Kotoba whether that live active record may be released. Kotoba
   * owns the decision: a double free, an unknown page, or a page named by an
   * already-inactive record is refused before C zeroes or re-links anything. */
  for (uint32_t i=0;i<ALLOCATION_RECORDS;i++) if (allocation_records[i].page==page) {
    uint64_t admitted = kotoba_aiueos_allocator_plan(
      (uint64_t)(uintptr_t)allocation_records, ALLOCATION_RECORDS*16ULL,
      ALLOCATION_RECORDS, 16ULL,
      (((uint64_t)(uint32_t)(uintptr_t)page) << 32) | (uint64_t)(i + 1));
    if (!admitted || !allocation_records[i].active) { unlock(); return 0; }
    allocation_records[i].active=0; zero_page(page); *(void **)page=free_pages; free_pages=page;
    unlock(); return 1;
  }
  unlock(); return 0;
}
uint64_t aiueos_physical_allocator_reuse_count(void) {
  lock(); uint64_t count=allocator_reuse_count; unlock(); return count;
}
