/* setup_rng_msix's and setup_blk_msix's MSI-X programming before JUN-598 moved it to kotoba/msix-entry.o:
   verbatim from kernel/pci.c (main 4008b9d7), between the table entry pointer and the MSI-X enable. */
#include "common.h"
int old_rng(volatile struct virtio_common_cfg *cfg, struct msix_entry *entry) {
  entry[0].vector_control = 1;
  entry[0].address_low =
    0xfee00000U | ((uint32_t)kotoba_aiueos_cpu_apic_id() << 12);
  entry[0].address_high = 0;
  entry[0].data = 34;
  __asm__ volatile("" ::: "memory");
  cfg->queue_msix_vector = 0;
  if (cfg->queue_msix_vector != 0) return 0;
  entry[0].vector_control = 0;
  return 1;
}
int old_blk(volatile struct virtio_common_cfg *cfg, struct msix_entry *entry, uint32_t message_address, uint32_t message_data) {
  entry[1].vector_control = 1;
  entry[1].address_low = message_address;
  entry[1].address_high = 0;
  entry[1].data = message_data;
  __asm__ volatile("" ::: "memory");
  cfg->queue_msix_vector = 1;
  if (cfg->queue_msix_vector != 1) return 0;
  entry[1].vector_control = 0;
  return 1;
}
