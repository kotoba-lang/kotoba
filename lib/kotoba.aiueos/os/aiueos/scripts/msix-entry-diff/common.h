/* Shared by old.c, new.c and driver.c (JUN-598): kernel/pci.c's struct virtio_common_cfg and struct msix_entry. */
#include <stdint.h>
struct virtio_common_cfg {
  volatile uint32_t device_feature_select, device_feature;
  volatile uint32_t driver_feature_select, driver_feature;
  volatile uint16_t msix_config, num_queues;
  volatile uint8_t device_status, config_generation;
  volatile uint16_t queue_select, queue_size, queue_msix_vector, queue_enable;
  volatile uint16_t queue_notify_off;
  volatile uint64_t queue_desc, queue_driver, queue_device;
} __attribute__((packed));
struct msix_entry {
  volatile uint32_t address_low, address_high, data, vector_control;
};
extern uint64_t kotoba_aiueos_cpu_apic_id(void);
