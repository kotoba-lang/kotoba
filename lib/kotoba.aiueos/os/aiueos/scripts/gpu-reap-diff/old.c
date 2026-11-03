/* gpu_ctrl before JUN-598 moved its used-entry classification to kotoba/gpu-reap.o: verbatim from kernel/pci.c (main
   368643d2) as old_ctrl, its 10^8 budget the harness's budget_limit and its driver globals renamed old_* so new_ctrl's
   can be compared with them. */
#include "common.h"
#define gpu_event_buf old_event_buf
#define gpu_avail_next old_avail_next
#define gpu_used_consumed old_used_consumed
#define gpu_display_events old_display_events
struct virtio_gpu_event gpu_event_buf; uint16_t gpu_avail_next, gpu_used_consumed; uint32_t gpu_display_events;
int old_ctrl(struct virtq_desc *desc, struct virtq_avail *avail,
                    struct virtq_used *used, volatile uint16_t *doorbell,
                    uint16_t *submitted,
                    void *req, uint32_t req_len,
                    struct virtio_gpu_ctrl_header *resp, uint32_t resp_len,
                    uint32_t expect_type) {
  gpu_zero(resp, resp_len);
  desc[0] = (struct virtq_desc){(uint64_t)(uintptr_t)req, req_len, VIRTQ_DESC_F_NEXT, 1};
  desc[1] = (struct virtq_desc){(uint64_t)(uintptr_t)resp, resp_len, VIRTQ_DESC_F_WRITE, 0};
  uint16_t slot = gpu_avail_next++;
  avail->ring[slot & 3] = 0;
  __asm__ volatile("" ::: "memory");
  avail->index = gpu_avail_next;
  *doorbell = 0;
  for (uint32_t budget = 0; budget < budget_limit; budget++) {
    __asm__ volatile("" ::: "memory");
    int responded = 0;
    while (gpu_used_consumed != used->index) {
      struct virtq_used_element *done = &used->ring[gpu_used_consumed & 3];
      gpu_used_consumed++;
      if (done->id == 2) {
        /* the event buffer: record, clear, re-post */
        gpu_display_events |= gpu_event_buf.events;
        gpu_event_buf.events = 0;
        desc[2] = (struct virtq_desc){(uint64_t)(uintptr_t)&gpu_event_buf,
                                      sizeof(gpu_event_buf), VIRTQ_DESC_F_WRITE, 0};
        uint16_t eslot = gpu_avail_next++;
        avail->ring[eslot & 3] = 2;
        __asm__ volatile("" ::: "memory");
        avail->index = gpu_avail_next;
        *doorbell = 0;
      } else if (done->id == 0 && !responded) {
        responded = 1;
        if (done->length < sizeof(*resp)) {
          extern void aiueos_kernel_serial_marker(const char *text);
          aiueos_kernel_serial_marker("AIUEOS_GPU_CMD_FAIL short\r\n");
          *submitted = gpu_avail_next; return 0;
        }
        if (done->length > resp_len) {
          extern void aiueos_kernel_serial_marker(const char *text);
          aiueos_kernel_serial_marker("AIUEOS_GPU_CMD_FAIL long\r\n");
          *submitted = gpu_avail_next; return 0;
        }
        if (resp->type != expect_type) {
          extern void aiueos_kernel_serial_marker(const char *text);
          aiueos_kernel_serial_marker("AIUEOS_GPU_CMD_FAIL type\r\n");
          *submitted = gpu_avail_next; return 0;
        }
      }
    }
    if (responded) {
      *submitted = gpu_avail_next;
      return 1;
    }
    __asm__ volatile("pause");
  }
  {
    extern void aiueos_kernel_serial_marker(const char *text);
    aiueos_kernel_serial_marker("AIUEOS_GPU_CMD_FAIL timeout\r\n");
  }
  return 0;
}
