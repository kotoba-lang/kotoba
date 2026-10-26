#include <stdint.h>
#include <stddef.h>

#include "smp.h"

#define AP_TRAMPOLINE 0x8000U
#define APIC_ID 0x20U
#define APIC_ICR_LOW 0x300U
#define APIC_ICR_HIGH 0x310U

extern const uint8_t aiueos_ap_trampoline_start[], aiueos_ap_trampoline_end[];
extern const uint64_t aiueos_ap_trampoline_cr3, aiueos_ap_trampoline_entry;
extern const uint64_t aiueos_ap_trampoline_stack;
extern volatile uint32_t *aiueos_apic_mmio_base;
extern uint32_t aiueos_acpi_cpu_count(void);
extern uint32_t aiueos_acpi_apic_id(uint32_t index);
extern int aiueos_paging_seal_ap_trampoline(void);

static uint8_t ap_stack[65536]
  __attribute__((section(".high_bss"), aligned(4096)));
static volatile uint32_t ap_online;
static volatile uint32_t ap_observed_id;
static volatile uint32_t ap_dispatch_qualified;
static aiueos_smp_work_fn ap_work;
static void *ap_work_context;
static volatile uint64_t ap_work_generation;
static volatile uint64_t ap_work_completed;

#define AP_WORK_WAIT_BUDGET 5000000000ULL

static void pause_loop(uint32_t count) {
  while (count--) __asm__ volatile("pause");
}
static void apic_write(uint32_t offset, uint32_t value) {
  aiueos_apic_mmio_base[offset / 4] = value;
  (void)aiueos_apic_mmio_base[APIC_ID / 4];
}
static int wait_icr(void) {
  for (uint32_t i = 0; i < 10000000U; i++) {
    if (!(aiueos_apic_mmio_base[APIC_ICR_LOW / 4] & (1U << 12))) return 1;
    __asm__ volatile("pause");
  }
  return 0;
}
static void patch64(uint8_t *copy, const uint64_t *symbol, uint64_t value) {
  uintptr_t offset = (uintptr_t)symbol - (uintptr_t)aiueos_ap_trampoline_start;
  *(uint64_t *)(void *)(copy + offset) = value;
}

/* A SIPI starts an AP with reset extended-state controls.  The Qwen worker
   executes compiler-generated SSE and an AVX2 target function, so it must not
   inherit those controls by assumption from the BSP's UEFI state. */
static void ap_enable_extended_state(void) {
  uint32_t eax, ebx, ecx, edx;
  __asm__ volatile("cpuid"
                   : "=a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx)
                   : "a"(1U), "c"(0U));
  uintptr_t cr4;
  __asm__ volatile("mov %%cr4, %0" : "=r"(cr4));
  cr4 |= (1U << 9) | (1U << 10);
  if ((ecx & (1U << 26)) && (ecx & (1U << 28))) cr4 |= (1U << 18);
  __asm__ volatile("mov %0, %%cr4" : : "r"(cr4) : "memory");
  if (cr4 & (1U << 18)) {
    uint32_t xcr0_low, xcr0_high;
    __asm__ volatile("xgetbv" : "=a"(xcr0_low), "=d"(xcr0_high) : "c"(0U));
    xcr0_low |= 0x6U;
    __asm__ volatile("xsetbv" : : "a"(xcr0_low), "d"(xcr0_high), "c"(0U));
  }
}

__attribute__((noreturn)) void aiueos_ap_entry(void) {
  uint32_t id = aiueos_apic_mmio_base[APIC_ID / 4] >> 24;
  ap_enable_extended_state();
  ap_observed_id = id;
  __atomic_store_n(&ap_online, 1, __ATOMIC_RELEASE);
  __asm__ volatile("outb %0, $0xe9" : : "a"((uint8_t)'A'));
  uint64_t observed = 0;
  for (;;) {
    uint64_t generation = __atomic_load_n(
      &ap_work_generation, __ATOMIC_ACQUIRE);
    if (generation == observed) {
      __asm__ volatile("pause");
      continue;
    }
    aiueos_smp_work_fn work = ap_work;
    void *context = ap_work_context;
    observed = generation;
    if (work) work(context);
    __atomic_store_n(&ap_work_completed, generation, __ATOMIC_RELEASE);
  }
}

int aiueos_smp_start_application_processor(void) {
  if (__atomic_load_n(&ap_online, __ATOMIC_ACQUIRE)) return 1;
  if (aiueos_acpi_cpu_count() < 2 || !aiueos_apic_mmio_base) return 0;
  uint32_t bsp = aiueos_apic_mmio_base[APIC_ID / 4] >> 24;
  uint32_t target = 0xffffffffU;
  for (uint32_t i = 0; i < aiueos_acpi_cpu_count(); i++) {
    uint32_t id = aiueos_acpi_apic_id(i);
    if (id != bsp) { target = id; break; }
  }
  if (target == 0xffffffffU || target > 255U) return 0;
  size_t size = (size_t)(aiueos_ap_trampoline_end-aiueos_ap_trampoline_start);
  if (size > 4096) return 0;
  uint8_t *copy = (uint8_t *)(uintptr_t)AP_TRAMPOLINE;
  for (size_t i = 0; i < size; i++) copy[i] = aiueos_ap_trampoline_start[i];
  uint64_t cr3; __asm__ volatile("mov %%cr3, %0" : "=r"(cr3));
  patch64(copy, &aiueos_ap_trampoline_cr3, cr3);
  patch64(copy, &aiueos_ap_trampoline_entry, (uint64_t)(uintptr_t)aiueos_ap_entry);
  patch64(copy, &aiueos_ap_trampoline_stack,
          (uint64_t)(uintptr_t)(ap_stack + sizeof(ap_stack)));
  if (!aiueos_paging_seal_ap_trampoline()) return 0;
  ap_online = 0;
  ap_dispatch_qualified = 0;
  ap_work = 0;
  ap_work_context = 0;
  ap_work_generation = 0;
  ap_work_completed = 0;
  apic_write(APIC_ICR_HIGH, target << 24);
  apic_write(APIC_ICR_LOW, 0x0000c500U);
  if (!wait_icr()) return 0;
  pause_loop(1000000);
  apic_write(APIC_ICR_HIGH, target << 24);
  apic_write(APIC_ICR_LOW, 0x00008500U);
  if (!wait_icr()) return 0;
  pause_loop(1000000);
  for (int attempt = 0; attempt < 2; attempt++) {
    apic_write(APIC_ICR_HIGH, target << 24);
    apic_write(APIC_ICR_LOW, 0x00000608U);
    if (!wait_icr()) return 0;
    pause_loop(2000000);
    if (__atomic_load_n(&ap_online, __ATOMIC_ACQUIRE)) break;
  }
  return ap_online && ap_observed_id == target;
}

uint32_t aiueos_smp_worker_threads(void) {
  return __atomic_load_n(&ap_online, __ATOMIC_ACQUIRE) &&
         __atomic_load_n(&ap_dispatch_qualified, __ATOMIC_ACQUIRE) ? 2U : 1U;
}

int aiueos_smp_dispatch(aiueos_smp_work_fn work, void *context) {
  if (!work || !__atomic_load_n(&ap_online, __ATOMIC_ACQUIRE)) return 0;
  uint64_t generation = __atomic_load_n(
    &ap_work_generation, __ATOMIC_ACQUIRE);
  if (__atomic_load_n(&ap_work_completed, __ATOMIC_ACQUIRE) != generation)
    return 0;
  ap_work = work;
  ap_work_context = context;
  __atomic_store_n(&ap_work_generation, generation + 1U, __ATOMIC_RELEASE);
  return 1;
}

int aiueos_smp_join(void) {
  uint64_t generation = __atomic_load_n(
    &ap_work_generation, __ATOMIC_ACQUIRE);
  for (uint64_t budget = 0; budget < AP_WORK_WAIT_BUDGET; budget++) {
    if (__atomic_load_n(&ap_work_completed, __ATOMIC_ACQUIRE) == generation)
      return 1;
    __asm__ volatile("pause");
  }
  return 0;
}

static void ap_selftest_work(void *opaque) {
  uint64_t *value = opaque;
  *value = 0x41505545534d5032ULL;
}

int aiueos_smp_dispatch_selftest(void) {
  uint64_t value = 0;
  int ok = aiueos_smp_dispatch(ap_selftest_work, &value) &&
           aiueos_smp_join() && value == 0x41505545534d5032ULL;
  __atomic_store_n(&ap_dispatch_qualified, ok ? 1U : 0U, __ATOMIC_RELEASE);
  return ok;
}
