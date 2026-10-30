/* gpu_ctrl's completion walk (JUN-598): old_ctrl (verbatim) and new_ctrl (over kotoba/gpu-reap.o) run from the same
   rings and script -- up to 5 used entries waiting from a free-running consumed position that wraps at 2^16, ids 0, 1,
   2 and 3 (2 the event buffer, 0 the response, which only the first counts), lengths around the 24-byte header and
   the response length, a response header of the expected type or not, event bits pending or not, budgets of 1..40
   polls -- and must answer the same, write the same failure markers, and leave the same descriptors, available ring,
   indexes, event state and doorbell. 60000 cases. */
#include "common.h"
int old_ctrl(struct virtq_desc *, struct virtq_avail *, struct virtq_used *, volatile uint16_t *, uint16_t *, void *,
             uint32_t, struct virtio_gpu_ctrl_header *, uint32_t, uint32_t);
int new_ctrl(struct virtq_desc *, struct virtq_avail *, struct virtq_used *, volatile uint16_t *, uint16_t *, void *,
             uint32_t, struct virtio_gpu_ctrl_header *, uint32_t, uint32_t);
extern struct virtio_gpu_event old_event_buf, new_event_buf;
extern uint16_t old_avail_next, new_avail_next, old_used_consumed, new_used_consumed;
extern uint32_t old_display_events, new_display_events;
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
uint32_t budget_limit;
static uint64_t markers;
void aiueos_kernel_serial_marker(const char *text) { while (*text) markers = (markers ^ (uint8_t)*text++) * 1099511628211ull; }
static uint32_t respond_type;
void device_respond(void *p, uint32_t n) { if (n >= 4) ((struct virtio_gpu_ctrl_header *)p)->type = respond_type; }
static uint8_t desc_page[4096] __attribute__((aligned(4096))), avail_page[4096] __attribute__((aligned(4096))),
  used_page[4096] __attribute__((aligned(4096))), resp_buf[128] __attribute__((aligned(16))), req_buf[64];
static uint8_t desc0[64], avail0[16], used0[64], desc1[64], avail1[16], resp1[128];
static volatile uint16_t bell;
static uint64_t seed = 2440;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 21; }
void test_main(void) {
  puts_("GPUREAPDIFF\n");
  unsigned n_cases = 0, n_ok = 0, n_fail = 0, n_bad = 0;
  for (unsigned k = 0; k < 60000; k++) {
    for (int i = 0; i < 64; i++) { desc0[i] = (uint8_t)rnd(); used0[i] = (uint8_t)rnd(); }
    for (int i = 0; i < 16; i++) avail0[i] = (uint8_t)rnd();
    uint16_t consumed = (uint16_t)(k % 19 == 0 ? 0xfffd + rnd() % 3 : rnd()), next = (uint16_t)rnd();
    struct virtq_used *u = (struct virtq_used *)used0;
    u->index = (uint16_t)(consumed + rnd() % 6);
    uint32_t resp_len = (uint32_t)(24 + rnd() % 80), expect = (uint32_t)(0x1100 + rnd() % 3);
    for (int i = 0; i < 4; i++) {
      unsigned c = (unsigned)(rnd() % 8);
      u->ring[i].id = c < 3 ? 0 : c < 6 ? 2 : (uint32_t)(c == 6 ? 1 : 3 + rnd() % 1000);
      unsigned l = (unsigned)(rnd() % 5);
      u->ring[i].length = l == 0 ? (uint32_t)(rnd() % 24) : l == 1 ? resp_len + 1 + (uint32_t)(rnd() % 9) :
                          l == 2 ? 24 : l == 3 ? resp_len : 24 + (uint32_t)(rnd() % (resp_len - 23));
    }
    respond_type = rnd() % 5 == 0 ? expect + 1 : expect;
    uint32_t events = (uint32_t)(rnd() % 3 == 0 ? rnd() : 0), display = (uint32_t)rnd();
    budget_limit = (uint32_t)(1 + rnd() % 40);
    uint16_t submitted0 = (uint16_t)rnd();
    int r[2]; uint64_t mk[2]; uint16_t sub[2], an[2], uc[2], bl[2]; uint32_t de[2], ev[2];
    for (int w = 0; w < 2; w++) {
      for (int i = 0; i < 4096; i++) { desc_page[i] = i < 64 ? desc0[i] : 0; avail_page[i] = i < 16 ? avail0[i] : 0;
                                       used_page[i] = i < 64 ? used0[i] : 0; }
      for (int i = 0; i < 128; i++) resp_buf[i] = 0x5a;
      markers = 14695981039346656037ull; bell = 1; uint16_t submitted = submitted0;
      if (w == 0) { old_used_consumed = consumed; old_avail_next = next; old_display_events = display; old_event_buf.events = events; }
      else { new_used_consumed = consumed; new_avail_next = next; new_display_events = display; new_event_buf.events = events; }
      r[w] = (w == 0 ? old_ctrl : new_ctrl)((struct virtq_desc *)desc_page, (struct virtq_avail *)avail_page,
               (struct virtq_used *)used_page, &bell, &submitted, req_buf, 40, (struct virtio_gpu_ctrl_header *)resp_buf,
               resp_len, expect);
      mk[w] = markers; sub[w] = submitted; bl[w] = bell;
      an[w] = w == 0 ? old_avail_next : new_avail_next; uc[w] = w == 0 ? old_used_consumed : new_used_consumed;
      de[w] = w == 0 ? old_display_events : new_display_events; ev[w] = w == 0 ? old_event_buf.events : new_event_buf.events;
      if (w == 0) { for (int i = 0; i < 64; i++) desc1[i] = desc_page[i]; for (int i = 0; i < 16; i++) avail1[i] = avail_page[i];
                    for (int i = 0; i < 128; i++) resp1[i] = resp_buf[i]; }
    }
    int same = r[0] == r[1] && mk[0] == mk[1] && sub[0] == sub[1] && bl[0] == bl[1] && an[0] == an[1] && uc[0] == uc[1] &&
               de[0] == de[1] && ev[0] == ev[1];
    /* the event descriptor's address is each file's own gpu_event_buf: compare desc 0, 1 and desc 2's length/flags */
    for (int i = 0; i < 64; i++) if (desc_page[i] != desc1[i] && !(i >= 32 && i < 40)) same = 0;
    for (int i = 0; i < 16; i++) if (avail_page[i] != avail1[i]) same = 0;
    for (int i = 0; i < 128; i++) if (resp_buf[i] != resp1[i]) same = 0;
    n_cases++; if (r[0]) n_ok++; if (mk[0] != 14695981039346656037ull) n_fail++;
    if (!same && n_bad++ < 8) { puts_("GPU-DIFF "); hex(k, 5); hex(r[0], 1); hex(r[1], 1); hex(uc[0], 4); hex(uc[1], 4); putc_('\n'); }
  }
  puts_("CASES "); hex(n_cases, 5); puts_("OK "); hex(n_ok, 5); puts_("MARKED "); hex(n_fail, 5);
  puts_("DIFFS "); hex(n_bad, 5); putc_('\n'); puts_("DONE\n");
}
