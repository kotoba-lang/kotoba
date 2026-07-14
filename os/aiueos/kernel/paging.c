#include <stdint.h>
#include <stddef.h>

#define PAGE_SIZE 4096ULL
#define ENTRY_COUNT 512
#define PTE_PRESENT (1ULL << 0)
#define PTE_WRITABLE (1ULL << 1)
#define PTE_HUGE (1ULL << 7)
#define PTE_NX (1ULL << 63)

extern uint8_t aiueos_text_start[], aiueos_text_end[];
extern uint8_t aiueos_rodata_start[], aiueos_rodata_end[];
extern uint8_t aiueos_data_start[], aiueos_kernel_end[];

static uint64_t pml4[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t pdpt[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t page_directory[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t low_page_table[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));

static uint64_t read_cr0(void) {
  uint64_t value; __asm__ volatile("mov %%cr0, %0" : "=r"(value)); return value;
}
static uint64_t read_cr3(void) {
  uint64_t value; __asm__ volatile("mov %%cr3, %0" : "=r"(value)); return value;
}
static void write_cr0(uint64_t value) { __asm__ volatile("mov %0, %%cr0" : : "r"(value) : "memory"); }
static void write_cr3(uint64_t value) { __asm__ volatile("mov %0, %%cr3" : : "r"(value) : "memory"); }
static uint64_t read_msr(uint32_t msr) {
  uint32_t lo, hi; __asm__ volatile("rdmsr" : "=a"(lo), "=d"(hi) : "c"(msr));
  return ((uint64_t)hi << 32) | lo;
}
static void write_msr(uint32_t msr, uint64_t value) {
  __asm__ volatile("wrmsr" : : "c"(msr), "a"((uint32_t)value), "d"((uint32_t)(value >> 32)));
}
static int nx_supported(void) {
  uint32_t eax = 0x80000000, ebx, ecx, edx;
  __asm__ volatile("cpuid" : "+a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx));
  if (eax < 0x80000001) return 0;
  eax = 0x80000001;
  __asm__ volatile("cpuid" : "+a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx));
  return (edx & (1U << 20)) != 0;
}
static int within(uint64_t page, const uint8_t *start, const uint8_t *end) {
  return page >= (uint64_t)(uintptr_t)start && page < (uint64_t)(uintptr_t)end;
}

int aiueos_paging_initialize(void) {
  if (!nx_supported()) return 0;

  for (uint64_t i = 0; i < ENTRY_COUNT; i++) {
    pml4[i] = pdpt[i] = page_directory[i] = low_page_table[i] = 0;
  }
  pml4[0] = (uint64_t)(uintptr_t)pdpt | PTE_PRESENT | PTE_WRITABLE;
  pdpt[0] = (uint64_t)(uintptr_t)page_directory | PTE_PRESENT | PTE_WRITABLE;
  page_directory[0] = (uint64_t)(uintptr_t)low_page_table | PTE_PRESENT | PTE_WRITABLE;
  for (uint64_t i = 1; i < ENTRY_COUNT; i++) {
    page_directory[i] = (i * 0x200000ULL) | PTE_PRESENT | PTE_WRITABLE | PTE_HUGE | PTE_NX;
  }
  for (uint64_t i = 0; i < ENTRY_COUNT; i++) {
    uint64_t page = i * PAGE_SIZE;
    uint64_t flags = PTE_PRESENT | PTE_NX;
    if (!within(page, aiueos_text_start, aiueos_text_end) &&
        !within(page, aiueos_rodata_start, aiueos_rodata_end)) flags |= PTE_WRITABLE;
    if (within(page, aiueos_text_start, aiueos_text_end)) flags &= ~PTE_NX;
    low_page_table[i] = page | flags;
  }

  write_msr(0xc0000080U, read_msr(0xc0000080U) | (1ULL << 11));
  write_cr0(read_cr0() | (1ULL << 16));
  write_cr3((uint64_t)(uintptr_t)pml4);

  uint64_t text_index = (uint64_t)(uintptr_t)aiueos_text_start / PAGE_SIZE;
  uint64_t rodata_index = (uint64_t)(uintptr_t)aiueos_rodata_start / PAGE_SIZE;
  uint64_t data_index = (uint64_t)(uintptr_t)aiueos_data_start / PAGE_SIZE;
  if (text_index >= ENTRY_COUNT || rodata_index >= ENTRY_COUNT || data_index >= ENTRY_COUNT) return 0;
  return read_cr3() == (uint64_t)(uintptr_t)pml4 &&
         !(low_page_table[text_index] & PTE_WRITABLE) && !(low_page_table[text_index] & PTE_NX) &&
         !(low_page_table[rodata_index] & PTE_WRITABLE) && (low_page_table[rodata_index] & PTE_NX) &&
         (low_page_table[data_index] & PTE_WRITABLE) && (low_page_table[data_index] & PTE_NX) &&
         ((uint64_t)(uintptr_t)aiueos_kernel_end < 0x200000ULL);
}

