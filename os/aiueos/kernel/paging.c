#include <stdint.h>
#include <stddef.h>

#define PAGE_SIZE 4096ULL
#define ENTRY_COUNT 512
#define PTE_PRESENT (1ULL << 0)
#define PTE_WRITABLE (1ULL << 1)
#define PTE_USER (1ULL << 2)
#define PTE_HUGE (1ULL << 7)
#define PTE_WRITE_THROUGH (1ULL << 3)
#define PTE_CACHE_DISABLE (1ULL << 4)
#define PTE_NX (1ULL << 63)

extern uint8_t aiueos_text_start[], aiueos_text_end[];
extern uint8_t aiueos_rodata_start[], aiueos_rodata_end[];
extern uint8_t aiueos_data_start[], aiueos_kernel_end[];
extern uint8_t aiueos_user_text_start[], aiueos_user_text_end[];
extern uint8_t aiueos_user_data_start[], aiueos_user_data_end[];

static uint64_t pml4[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t pdpt[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t page_directory[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t low_page_table[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t apic_page_directory[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t pci_page_directory[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t framebuffer_page_directory[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t pci_pdpt[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t pci_pdpt_index = UINT64_MAX;
static uint64_t pci_pml4_index = UINT64_MAX;

/* Phase-3 address-space vertical slice.  Kernel/MMIO branches stay shared,
 * while each process owns the complete low-2MiB page-table path. */
struct process_address_space {
  uint64_t pml4[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
  uint64_t pdpt[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
  uint64_t directory[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
  uint64_t low[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
};
static struct process_address_space process_spaces[2];
static uint8_t process_private_pages[2][PAGE_SIZE] __attribute__((aligned(PAGE_SIZE)));
static uint64_t kernel_cr3;

#define PROCESS_PRIVATE_0 0x1fc000ULL
#define PROCESS_PRIVATE_1 0x1fd000ULL

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
    apic_page_directory[i] = pci_page_directory[i] = pci_pdpt[i] = 0;
    framebuffer_page_directory[i] = 0;
  }
  pml4[0] = (uint64_t)(uintptr_t)pdpt | PTE_PRESENT | PTE_WRITABLE;
  pdpt[0] = (uint64_t)(uintptr_t)page_directory | PTE_PRESENT | PTE_WRITABLE;
  page_directory[0] = (uint64_t)(uintptr_t)low_page_table | PTE_PRESENT | PTE_WRITABLE;
  pml4[0] |= PTE_USER; pdpt[0] |= PTE_USER; page_directory[0] |= PTE_USER;
  for (uint64_t i = 1; i < ENTRY_COUNT; i++) {
    page_directory[i] = (i * 0x200000ULL) | PTE_PRESENT | PTE_WRITABLE | PTE_HUGE | PTE_NX;
  }
  pdpt[3] = (uint64_t)(uintptr_t)apic_page_directory | PTE_PRESENT | PTE_WRITABLE;
  const uint64_t apic_base = 0xfee00000ULL;
  const uint64_t apic_pde = (apic_base >> 21) & 0x1ff;
  apic_page_directory[apic_pde] = apic_base | PTE_PRESENT | PTE_WRITABLE |
    PTE_HUGE | PTE_NX | PTE_WRITE_THROUGH | PTE_CACHE_DISABLE;
  const uint64_t ioapic_base = 0xfec00000ULL;
  const uint64_t ioapic_pde = (ioapic_base >> 21) & 0x1ff;
  apic_page_directory[ioapic_pde] = ioapic_base | PTE_PRESENT | PTE_WRITABLE |
    PTE_HUGE | PTE_NX | PTE_WRITE_THROUGH | PTE_CACHE_DISABLE;
  for (uint64_t i = 0; i < ENTRY_COUNT; i++) {
    uint64_t page = i * PAGE_SIZE;
    uint64_t flags = PTE_PRESENT | PTE_NX;
    if (!within(page, aiueos_text_start, aiueos_text_end) &&
        !within(page, aiueos_rodata_start, aiueos_rodata_end)) flags |= PTE_WRITABLE;
    if (within(page, aiueos_text_start, aiueos_text_end)) flags &= ~PTE_NX;
    if (within(page, aiueos_user_text_start, aiueos_user_text_end))
      flags = PTE_PRESENT | PTE_USER;
    if (within(page, aiueos_user_data_start, aiueos_user_data_end))
      flags = PTE_PRESENT | PTE_USER | PTE_WRITABLE | PTE_NX;
    if (page == (uint64_t)(uintptr_t)aiueos_user_data_end) flags = 0;
    low_page_table[i] = page | flags;
  }
  low_page_table[(uint64_t)(uintptr_t)aiueos_user_data_end / PAGE_SIZE] = 0;

  write_msr(0xc0000080U, read_msr(0xc0000080U) | (1ULL << 11));
  write_cr0(read_cr0() | (1ULL << 16));
  write_cr3((uint64_t)(uintptr_t)pml4);
  kernel_cr3 = (uint64_t)(uintptr_t)pml4;

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

int aiueos_address_spaces_initialize(void) {
  const uint64_t private_va[2] = {PROCESS_PRIVATE_0, PROCESS_PRIVATE_1};
  for (uint64_t process = 0; process < 2; process++) {
    struct process_address_space *space = &process_spaces[process];
    for (uint64_t i = 0; i < ENTRY_COUNT; i++) {
      space->pml4[i] = pml4[i];
      space->pdpt[i] = pdpt[i];
      space->directory[i] = page_directory[i];
      space->low[i] = low_page_table[i];
    }
    space->pml4[0] = (uint64_t)(uintptr_t)space->pdpt |
      PTE_PRESENT | PTE_WRITABLE | PTE_USER;
    space->pdpt[0] = (uint64_t)(uintptr_t)space->directory |
      PTE_PRESENT | PTE_WRITABLE | PTE_USER;
    space->directory[0] = (uint64_t)(uintptr_t)space->low |
      PTE_PRESENT | PTE_WRITABLE | PTE_USER;
    /* Neither process can name the other's page. */
    space->low[PROCESS_PRIVATE_0 / PAGE_SIZE] = 0;
    space->low[PROCESS_PRIVATE_1 / PAGE_SIZE] = 0;
    space->low[private_va[process] / PAGE_SIZE] =
      (uint64_t)(uintptr_t)process_private_pages[process] |
      PTE_PRESENT | PTE_USER | PTE_WRITABLE | PTE_NX;
  }
  return (uint64_t)(uintptr_t)process_spaces[0].pml4 !=
      (uint64_t)(uintptr_t)process_spaces[1].pml4 &&
    process_spaces[0].low[PROCESS_PRIVATE_1 / PAGE_SIZE] == 0 &&
    process_spaces[1].low[PROCESS_PRIVATE_0 / PAGE_SIZE] == 0;
}

uint64_t aiueos_address_space_enter(unsigned process) {
  if (process >= 2) return 0;
  write_cr3((uint64_t)(uintptr_t)process_spaces[process].pml4);
  return read_cr3();
}

void aiueos_address_space_leave(void) { write_cr3(kernel_cr3); }
uint64_t aiueos_address_space_private_va(unsigned process) {
  return process == 0 ? PROCESS_PRIVATE_0 : process == 1 ? PROCESS_PRIVATE_1 : 0;
}

/* GOP memory is mapped supervisor-only, non-executable and uncached.  Its
 * dedicated directory prevents a display capability from replacing RAM or
 * PCI transport mappings. */
int aiueos_map_framebuffer(uint64_t address, uint64_t length) {
  if (!length || address < 0x40000000ULL || address >= 0xc0000000ULL ||
      address + length < address || address + length > 0xc0000000ULL)
    return 0;
  uint64_t pdpt_index = address >> 30;
  if (pdpt_index < 1 || pdpt_index > 2 ||
      pdpt_index != ((address + length - 1) >> 30) || pdpt[pdpt_index])
    return 0;
  pdpt[pdpt_index] = (uint64_t)(uintptr_t)framebuffer_page_directory |
    PTE_PRESENT | PTE_WRITABLE;
  uint64_t first = address & ~0x1fffffULL;
  uint64_t last = (address + length - 1) & ~0x1fffffULL;
  for (uint64_t page = first;; page += 0x200000ULL) {
    uint64_t index = (page >> 21) & 0x1ff;
    framebuffer_page_directory[index] = page | PTE_PRESENT | PTE_WRITABLE |
      PTE_HUGE | PTE_NX | PTE_WRITE_THROUGH | PTE_CACHE_DISABLE;
    if (page == last) break;
  }
  write_cr3(read_cr3());
  return 1;
}

int aiueos_user_mapping_verify(void) {
  uint64_t tx = (uint64_t)(uintptr_t)aiueos_user_text_start / PAGE_SIZE;
  uint64_t rw = (uint64_t)(uintptr_t)aiueos_user_data_start / PAGE_SIZE;
  uint64_t guard = (uint64_t)(uintptr_t)aiueos_user_data_end / PAGE_SIZE;
  if (tx >= ENTRY_COUNT || rw >= ENTRY_COUNT || guard >= ENTRY_COUNT) return 0;
  int result = 0;
  if ((low_page_table[tx] & (PTE_PRESENT|PTE_USER|PTE_WRITABLE|PTE_NX)) ==
      (PTE_PRESENT|PTE_USER)) result |= 1;
  if ((low_page_table[rw] & (PTE_PRESENT|PTE_USER|PTE_WRITABLE|PTE_NX)) ==
      (PTE_PRESENT|PTE_USER|PTE_WRITABLE|PTE_NX)) result |= 2;
  if (!low_page_table[guard]) result |= 4;
  return result;
}

int aiueos_paging_seal_ap_trampoline(void) {
  const uint64_t index = 0x8000ULL / PAGE_SIZE;
  if ((low_page_table[index] & PTE_PRESENT) == 0) return 0;
  low_page_table[index] &= ~(PTE_WRITABLE | PTE_NX);
  write_cr3(read_cr3());
  return (low_page_table[index] & (PTE_WRITABLE | PTE_NX)) == 0;
}

/* Map PCI MMIO in the already-owned top GiB using 2 MiB UC/NX pages.  Keep
 * the interface deliberately narrow: PCI must never turn an arbitrary BAR
 * into an executable or cached mapping. */
int aiueos_map_pci_mmio(uint64_t address, uint64_t length) {
  if (!length || address < 0xc0000000ULL || address >= 0x10000000000ULL ||
      length > 0x40000000ULL || address + length < address ||
      address + length > 0x10000000000ULL ||
      (address >> 30) != ((address + length - 1) >> 30)) return 0;
  uint64_t pml4_index = address >> 39;
  uint64_t pdpt_index = (address >> 30) & 0x1ff;
  uint64_t *directory;
  if (pml4_index == 0 && pdpt_index == 3) directory = apic_page_directory;
  else {
    if (pci_pdpt_index == UINT64_MAX) {
      uint64_t *target_pdpt;
      if (pml4_index == 0) target_pdpt = pdpt;
      else {
        if (pml4[pml4_index]) return 0;
        pml4[pml4_index] = (uint64_t)(uintptr_t)pci_pdpt | PTE_PRESENT | PTE_WRITABLE;
        target_pdpt = pci_pdpt;
      }
      if (target_pdpt[pdpt_index]) return 0;
      pci_pml4_index = pml4_index;
      pci_pdpt_index = pdpt_index;
      target_pdpt[pdpt_index] = (uint64_t)(uintptr_t)pci_page_directory | PTE_PRESENT | PTE_WRITABLE;
    }
    if (pci_pml4_index != pml4_index || pci_pdpt_index != pdpt_index) return 0;
    directory = pci_page_directory;
  }
  uint64_t first = address & ~0x1fffffULL;
  uint64_t last = (address + length - 1) & ~0x1fffffULL;
  for (uint64_t page = first;; page += 0x200000ULL) {
    uint64_t index = (page >> 21) & 0x1ff;
    uint64_t prior = directory[index];
    uint64_t wanted = page | PTE_PRESENT | PTE_WRITABLE | PTE_HUGE | PTE_NX |
      PTE_WRITE_THROUGH | PTE_CACHE_DISABLE;
    if (prior && (prior & 0x000fffffffe00000ULL) != page) return 0;
    directory[index] = wanted;
    __asm__ volatile("invlpg (%0)" : : "r"((void *)(uintptr_t)page) : "memory");
    if (page == last) break;
  }
  return 1;
}
