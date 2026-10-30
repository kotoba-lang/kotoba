/* The C enumeration decisions before JUN-598 moved them to kotoba/pci-enum.o, verbatim from kernel/pci.c (main
   a4a2eaac): aiueos_virtio_probe's presence test, function count, device-ID dispatch and result cascade, and the
   RTL8125 scan's ID test, each lifted into a function of the configuration word it read (the dispatch answers which of
   its branches would call a driver: 2 RNG, 3 block, 4 input, 5 GPU, 6 net, 7 sound, 1 another virtio, 0 none). */
#include <stdint.h>
#define VIRTIO_VENDOR_ID 0x1af4
#define VIRTIO_RNG_MODERN_ID 0x1044
#define VIRTIO_RNG_TRANSITIONAL_ID 0x1005
#define VIRTIO_BLK_MODERN_ID 0x1042
#define VIRTIO_BLK_TRANSITIONAL_ID 0x1001
#define VIRTIO_INPUT_MODERN_ID 0x1052
#define VIRTIO_INPUT_TRANSITIONAL_ID 0x1012
#define VIRTIO_GPU_MODERN_ID 0x1050
#define VIRTIO_GPU_TRANSITIONAL_ID 0x1010
#define VIRTIO_NET_MODERN_ID 0x1041
#define VIRTIO_NET_TRANSITIONAL_ID 0x1000
#define VIRTIO_SND_MODERN_ID 0x1059
int old_present(uint32_t id0) { return !((id0 & 0xffffU) == 0xffffU); }
int old_functions(uint8_t header) { uint8_t functions = (header & 0x80) ? 8 : 1; return functions; }
int old_driver(uint32_t id) {
  if ((id & 0xffffU) == VIRTIO_VENDOR_ID) {
    uint16_t device_id = (uint16_t)(id >> 16);
    if (device_id == VIRTIO_RNG_MODERN_ID || device_id == VIRTIO_RNG_TRANSITIONAL_ID) return 2;
    if (device_id == VIRTIO_BLK_MODERN_ID || device_id == VIRTIO_BLK_TRANSITIONAL_ID) return 3;
    if (device_id == VIRTIO_INPUT_MODERN_ID || device_id == VIRTIO_INPUT_TRANSITIONAL_ID) return 4;
    if (device_id == VIRTIO_GPU_MODERN_ID || device_id == VIRTIO_GPU_TRANSITIONAL_ID) return 5;
    if (device_id == VIRTIO_NET_MODERN_ID || device_id == VIRTIO_NET_TRANSITIONAL_ID) return 6;
    if (device_id == VIRTIO_SND_MODERN_ID) return 7;
    return 1;
  }
  return 0;
}
int old_result(int rng_ok, int blk_ok, int input_ok, int gpu_ok, uint32_t present, uint32_t virtio) {
  if (rng_ok && blk_ok && input_ok && gpu_ok) return 15;
  if (rng_ok && blk_ok && input_ok) return 7;
  if (rng_ok && blk_ok) return 3;
  if (rng_ok) return 2;
  return present && virtio ? 1 : 0;
}
int old_rtl8125(uint32_t id) { return (id&0xffffU)==0x10ecU&&(id>>16)==0x8125U; }
