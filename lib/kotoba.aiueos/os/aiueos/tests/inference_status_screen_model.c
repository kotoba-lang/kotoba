#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "../kernel/inference_status.h"

#define WIDTH 800U
#define HEIGHT 600U
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"check failed: %s\n",#x); return 1; } } while(0)

struct aiueos_boot_info {
  uint64_t magic, version;
  void *memory_map; uint64_t memory_map_size, descriptor_size, descriptor_version;
  void *acpi_rsdp;
  uint64_t framebuffer_base, framebuffer_size;
  uint32_t framebuffer_width, framebuffer_height, framebuffer_stride, framebuffer_format;
};
struct aiueos_desktop_surface {
  uint32_t abi_version, byte_size;
  uint64_t surface_id, generation, content_hash;
  uint32_t width, height, stride, pixel_format;
  uint32_t damage_x, damage_y, damage_width, damage_height;
} __attribute__((packed));

static uint32_t pixels[WIDTH * HEIGHT];

/* HOST STAND-INS (ADR-0219). The two decisions the screen consults are
   Kotoba kernel objects on the target (inference-status-valid.kotoba,
   inference-milli-tokens-per-second.kotoba) and cannot be linked into a
   macOS/arm64 host binary. This harness tests the RENDERER; the decisions
   are verified by contracts/inference-status-valid-v1.edn and
   contracts/inference-milli-tokens-per-second-v1.edn, which carry every
   verdict this file used to assert (the two invalid statuses and the two
   rates below are vectors there). The stand-ins admit every record and
   compute the rate the C's way, so the screens render exactly as before. */
int64_t kotoba_aiueos_inference_status_valid(uint8_t *record, int64_t length) {
  (void)record; return length == AIUEOS_INFERENCE_STATUS_RECORD_BYTES ? 1 : 0;
}
int64_t kotoba_aiueos_inference_milli_tokens_per_second(int64_t tokens,
                                                        int64_t elapsed_ns) {
  uint64_t t = (uint64_t)tokens, e = (uint64_t)elapsed_ns;
  if (!t || !e || e == UINT64_MAX || t > AIUEOS_INFERENCE_TOKEN_MAX)
    return (int64_t)UINT64_MAX;
  return (int64_t)(uint64_t)(((unsigned __int128)t * 1000000000000ULL) / e);
}
int aiueos_map_framebuffer(uint64_t address, uint64_t length) {
  return address == (uint64_t)(uintptr_t)pixels && length == sizeof(pixels);
}
int aiueos_framebuffer_initialize(const struct aiueos_boot_info *boot);
const struct aiueos_desktop_surface *aiueos_desktop_surface(void);

static int write_ppm(const char *path) {
  FILE *output = fopen(path, "wb");
  if (!output) return 0;
  fprintf(output, "P6\n%u %u\n255\n", WIDTH, HEIGHT);
  for (uint32_t i = 0; i < WIDTH * HEIGHT; i++) {
    uint8_t rgb[3] = {(uint8_t)(pixels[i] >> 16),
                      (uint8_t)(pixels[i] >> 8), (uint8_t)pixels[i]};
    if (fwrite(rgb, 1, sizeof(rgb), output) != sizeof(rgb)) {
      fclose(output); return 0;
    }
  }
  return fclose(output) == 0;
}

int main(int argc, char **argv) {
  struct aiueos_boot_info boot = {
    .framebuffer_base = (uint64_t)(uintptr_t)pixels,
    .framebuffer_size = sizeof(pixels),
    .framebuffer_width = WIDTH, .framebuffer_height = HEIGHT,
    .framebuffer_stride = WIDTH, .framebuffer_format = 0
  };
  CHECK(aiueos_framebuffer_initialize(&boot));
  const struct aiueos_desktop_surface *surface = aiueos_desktop_surface();
  CHECK(surface && surface->generation == 1 && surface->content_hash);
  uint64_t initial_hash = surface->content_hash;

  struct aiueos_inference_status blocked = {
    .abi_version = AIUEOS_INFERENCE_STATUS_ABI_VERSION,
    .byte_size = sizeof(blocked),
    .phase = AIUEOS_INFERENCE_BLOCKED,
    .model = "QWEN3.8 27B", .quant = "UD IQ3 XXS",
    .detail = "RUNTIME NOT PRESENT",
    .target_tokens = 64, .artifact_bytes = 10934860704ULL,
    .resident_bytes = AIUEOS_INFERENCE_UNMEASURED,
    .load_ns = AIUEOS_INFERENCE_UNMEASURED,
    .prefill_ns = AIUEOS_INFERENCE_UNMEASURED,
    .decode_ns = AIUEOS_INFERENCE_UNMEASURED,
    .time_to_first_token_ns = AIUEOS_INFERENCE_UNMEASURED,
    .compute_cycles = 0
  };
  CHECK(aiueos_framebuffer_inference_screen(&blocked));
  CHECK(surface->generation == 2 && surface->content_hash != initial_hash);

  struct aiueos_inference_status measured = {
    .abi_version = AIUEOS_INFERENCE_STATUS_ABI_VERSION,
    .byte_size = sizeof(measured),
    .phase = AIUEOS_INFERENCE_COMPLETE,
    .model = "QWEN3.8 27B", .quant = "UD IQ3 XXS",
    .detail = "QEMU UI TEST",
    .prompt_tokens = 128, .generated_tokens = 32, .decode_tokens = 31,
    .target_tokens = 32, .artifact_bytes = 10934860704ULL,
    .resident_bytes = 13958643712ULL,
    .load_ns = 53000000000ULL, .prefill_ns = 3200000000ULL,
    .decode_ns = 8000000000ULL, .time_to_first_token_ns = 3450000000ULL,
    .compute_cycles = 0
  };
  CHECK(aiueos_framebuffer_inference_screen(&measured));
  CHECK(surface->generation == 3 && surface->damage_x > 0 &&
        surface->damage_y > 0 && surface->damage_width < WIDTH &&
        surface->damage_height < HEIGHT);

  /* The validity decision is not asserted here any more: it is a Kotoba
     object on the target, and the stand-in above admits everything. */
  CHECK(argc < 2 || write_ppm(argv[1]));
  puts("AIUEOS_INFERENCE_STATUS_SCREEN_OK model=QWEN3.8-27B metrics=load,prefill,decode,tokens,resident phase=complete evidence=qemu-ui-test-only decision=kotoba-object-not-linked-here");
  return 0;
}
