/* rng_refill's completion wait before JUN-598 moved it to kotoba/virtq-wait.o: verbatim from kernel/pci.c (main
   dae5aa5c) with its 10^8 budget made a parameter and rng_backend's fields as parameters, as old_wait (1 when the
   completion was seen -- the length check after it is unchanged C -- 0 when the budget ran out). */
#include <stdint.h>
extern volatile uint64_t aiueos_virtio_rng_irq_count;
extern int64_t kotoba_aiueos_virtq_used_index(uint64_t used, uint64_t used_length);
extern int64_t kotoba_aiueos_virtq_used_elem(uint64_t used, uint64_t used_length, uint64_t slot);
int old_wait(void *used, uint64_t before, uint16_t posted, uint32_t budget_limit) {
  for (uint32_t budget = 0; budget < budget_limit; budget++) {
    __asm__ volatile("" ::: "memory");
    if (aiueos_virtio_rng_irq_count != before &&
        kotoba_aiueos_virtq_used_index((uint64_t)(uintptr_t)used, 4096) == posted) {
      return 1;
    }
    __asm__ volatile("sti; hlt; cli" ::: "memory");
  }
  return 0;
}
