#include <stdint.h>
#include "../include/boot_info.h"
#include "inference_status.h"

/* Release builds generate this header from os/aiueos/VERSION and the clean
   source commit.  Host-only framebuffer tests intentionally use the explicit
   fallback, so the renderer remains independently compilable. */
#if defined(__has_include)
#if __has_include("aiueos-build-identity.h")
#include "aiueos-build-identity.h"
#endif
#endif
#ifndef AIUEOS_BUILD_VERSION
#define AIUEOS_BUILD_VERSION "UNVERSIONED"
#endif
#ifndef AIUEOS_BUILD_SOURCE_HASH
#define AIUEOS_BUILD_SOURCE_HASH "UNVERIFIED"
#endif
#ifndef AIUEOS_BUILD_DIRTY_SUFFIX
#define AIUEOS_BUILD_DIRTY_SUFFIX "-DIRTY"
#endif

extern int aiueos_map_framebuffer(uint64_t address, uint64_t length);

#ifdef AIUEOS_PHYSICAL_QUALIFICATION
extern int aiueos_qualification_progress(uint32_t code);
#define FRAMEBUFFER_PROGRESS(code) aiueos_qualification_progress(code)
#else
#define FRAMEBUFFER_PROGRESS(code) ((void)0)
#endif

/* Browser desktop output ABI. surface_id is an opaque kernel-owned handle;
   physical framebuffer addresses are intentionally absent from the contract. */
struct aiueos_desktop_surface {
  uint32_t abi_version, byte_size;
  uint64_t surface_id, generation, content_hash;
  uint32_t width, height, stride, pixel_format;
  uint32_t damage_x, damage_y, damage_width, damage_height;
} __attribute__((packed));
static struct aiueos_desktop_surface desktop_surface;
static int desktop_surface_ready;
static volatile uint32_t *desktop_surface_pixels;
static int inference_screen_initialized;
/* ADR-0242: the last draw list aiueos_desktop_present_ops2 painted, the
   generation it made and the one it painted over, the generation last sent
   to the display, and the shadow Kotoba browser-damage keeps the previous
   list in (its layout is the object's header). */
static const uint32_t *desktop_list_ops;
static uint64_t desktop_list_count, desktop_list_generation, desktop_list_base_generation;
static uint64_t desktop_shown_generation;
static uint32_t desktop_shadow[2048] __attribute__((section(".high_bss"), aligned(16))); /* .high_bss: the low layout is at its aperture limit (ADR-0222) */
static uint32_t desktop_damage_last[4], desktop_damage_counts[5];
static uint64_t desktop_damage_bytes;
int aiueos_desktop_surface_ready(void) { return desktop_surface_ready; }
const struct aiueos_desktop_surface *aiueos_desktop_surface(void) {
  return desktop_surface_ready ? &desktop_surface : 0;
}
int aiueos_desktop_surface_copy(uint64_t generation, uint32_t x, uint32_t y,
    uint32_t width, uint32_t height, uint32_t *destination, uint64_t capacity) {
  if (!desktop_surface_ready || !destination || generation != desktop_surface.generation ||
      !width || !height || x >= desktop_surface.width || y >= desktop_surface.height ||
      width > desktop_surface.width - x || height > desktop_surface.height - y ||
      (uint64_t)width * height > capacity / sizeof(uint32_t)) return 0;
  for (uint32_t row = 0; row < height; row++)
    for (uint32_t column = 0; column < width; column++)
      destination[(uint64_t)row * width + column] =
        desktop_surface_pixels[(uint64_t)(y + row) * desktop_surface.stride + x + column];
  return 1;
}
/* A2 (JUN-142 / scorecard row A2): the desktop presents at ITS OWN size --
   the boot GOP framebuffer -- and the host frontend scales that image into
   whatever window the user gives it, so a host resize is no longer a bind
   failure. What this check still requires is that GET_DISPLAY_INFO answered
   at all: "the display exists and reports a size" is the condition it was
   written for, and the exact-equality form was over-reading it.

   Measured 2026-10-26 with `-display cocoa,zoom-to-fit=on`: the window
   shrank to 361x389 before this point, GET_DISPLAY_INFO reported 577x361
   against a 1280x800 surface, and the equality form stopped the boot with
   AIUEOS_VIRTIO_GPU_FAIL surface-binding-scanout-w=577 scanout-h=361 ->
   AIUEOS_EVIDENCE_STOP -- a display change the machine was supposed to
   survive. */
int aiueos_desktop_surface_bind_scanout(uint32_t width, uint32_t height) {
  return desktop_surface_ready && width && height;
}

static uint32_t pixel(uint32_t rgb, uint32_t format);
static void rectangle(volatile uint32_t *fb, uint32_t stride, uint32_t format,
                      uint32_t x, uint32_t y, uint32_t w, uint32_t h,
                      uint32_t color);
static uint64_t sample_hash(volatile uint32_t *fb, uint32_t width,
                            uint32_t height, uint32_t stride);

/* Physical qualification UI.  The normal desktop remains unchanged; this
   deliberately tiny built-in font is used only by the read-only K16 USB
   profile after the kernel owns the GOP aperture.  A photographed screen is
   useful evidence on machines without an exposed serial port. */
static const uint8_t *qualification_glyph(char c) {
  static const uint8_t blank[5] = {0,0,0,0,0};
  static const uint8_t a[5] = {0x7e,0x11,0x11,0x11,0x7e};
  static const uint8_t b[5] = {0x7f,0x49,0x49,0x49,0x36};
  static const uint8_t c_[5] = {0x3e,0x41,0x41,0x41,0x22};
  static const uint8_t d[5] = {0x7f,0x41,0x41,0x22,0x1c};
  static const uint8_t e[5] = {0x7f,0x49,0x49,0x49,0x41};
  static const uint8_t f[5] = {0x7f,0x09,0x09,0x09,0x01};
  static const uint8_t g[5] = {0x3e,0x41,0x49,0x49,0x7a};
  static const uint8_t h[5] = {0x7f,0x08,0x08,0x08,0x7f};
  static const uint8_t i[5] = {0x41,0x41,0x7f,0x41,0x41};
  static const uint8_t j[5] = {0x20,0x40,0x41,0x3f,0x01};
  static const uint8_t k[5] = {0x7f,0x08,0x14,0x22,0x41};
  static const uint8_t l[5] = {0x7f,0x40,0x40,0x40,0x40};
  static const uint8_t m[5] = {0x7f,0x02,0x0c,0x02,0x7f};
  static const uint8_t n[5] = {0x7f,0x04,0x08,0x10,0x7f};
  static const uint8_t o[5] = {0x3e,0x41,0x41,0x41,0x3e};
  static const uint8_t p[5] = {0x7f,0x09,0x09,0x09,0x06};
  static const uint8_t q[5] = {0x3e,0x41,0x51,0x21,0x5e};
  static const uint8_t r[5] = {0x7f,0x09,0x19,0x29,0x46};
  static const uint8_t s[5] = {0x46,0x49,0x49,0x49,0x31};
  static const uint8_t t[5] = {0x01,0x01,0x7f,0x01,0x01};
  static const uint8_t u[5] = {0x3f,0x40,0x40,0x40,0x3f};
  static const uint8_t v[5] = {0x1f,0x20,0x40,0x20,0x1f};
  static const uint8_t w[5] = {0x7f,0x20,0x18,0x20,0x7f};
  static const uint8_t x[5] = {0x63,0x14,0x08,0x14,0x63};
  static const uint8_t y[5] = {0x07,0x08,0x70,0x08,0x07};
  static const uint8_t z[5] = {0x61,0x51,0x49,0x45,0x43};
  static const uint8_t zero[5] = {0x3e,0x51,0x49,0x45,0x3e};
  static const uint8_t one[5] = {0x00,0x42,0x7f,0x40,0x00};
  static const uint8_t two[5] = {0x62,0x51,0x49,0x49,0x46};
  static const uint8_t three[5] = {0x22,0x41,0x49,0x49,0x36};
  static const uint8_t four[5] = {0x18,0x14,0x12,0x7f,0x10};
  static const uint8_t five[5] = {0x2f,0x49,0x49,0x49,0x31};
  static const uint8_t six[5] = {0x3c,0x4a,0x49,0x49,0x30};
  static const uint8_t seven[5] = {0x01,0x71,0x09,0x05,0x03};
  static const uint8_t eight[5] = {0x36,0x49,0x49,0x49,0x36};
  static const uint8_t nine[5] = {0x06,0x49,0x49,0x29,0x1e};
  static const uint8_t dot[5] = {0x00,0x60,0x60,0x00,0x00};
  static const uint8_t colon[5] = {0x00,0x36,0x36,0x00,0x00};
  static const uint8_t dash[5] = {0x08,0x08,0x08,0x08,0x08};
  static const uint8_t slash[5] = {0x60,0x18,0x06,0x01,0x00};
  if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A');
  switch (c) {
    case 'A': return a; case 'B': return b; case 'C': return c_;
    case 'D': return d; case 'E': return e; case 'F': return f;
    case 'G': return g; case 'H': return h; case 'I': return i;
    case 'J': return j; case 'K': return k; case 'L': return l;
    case 'M': return m; case 'N': return n; case 'O': return o;
    case 'P': return p; case 'Q': return q; case 'R': return r;
    case 'S': return s; case 'T': return t; case 'U': return u;
    case 'V': return v; case 'W': return w; case 'X': return x;
    case 'Y': return y; case 'Z': return z;
    case '0': return zero; case '1': return one; case '2': return two;
    case '3': return three; case '4': return four; case '5': return five;
    case '6': return six; case '7': return seven; case '8': return eight;
    case '9': return nine; case '.': return dot; case ':': return colon;
    case '-': return dash; case '/': return slash;
    default: return blank;
  }
}

static void qualification_text(const char *text, uint32_t x, uint32_t y,
                               uint32_t scale, uint32_t color) {
  if (!text) return;
  while (*text) {
    const uint8_t *glyph = qualification_glyph(*text++);
    for (uint32_t column = 0; column < 5; column++)
      for (uint32_t row = 0; row < 7; row++)
        if (glyph[column] & (1U << row))
          rectangle(desktop_surface_pixels, desktop_surface.stride,
                    desktop_surface.pixel_format,
                    x + column * scale, y + row * scale, scale, scale, color);
    x += 6 * scale;
  }
}

static uint32_t qualification_text_width(const char *text, uint32_t scale) {
  uint32_t length = 0;
  if (!text) return 0;
  while (text[length] && length <= AIUEOS_INFERENCE_STATUS_TEXT_MAX) length++;
  return length * 6U * scale;
}

/* This is deliberately a source/build identity, not the SHA-256 of the EFI
   that contains it: embedding an artifact's own digest would be
   self-referential.  The complete EFI SHA-256 remains in the signed build
   receipt, keyed by this version and source hash. */
static void framebuffer_build_identity(uint32_t x, uint32_t y,
                                       uint32_t scale) {
  qualification_text("AIUEOS " AIUEOS_BUILD_VERSION
                     " SOURCE " AIUEOS_BUILD_SOURCE_HASH
                     AIUEOS_BUILD_DIRTY_SUFFIX,
                     x, y, scale, 0x94a3b8U);
}

static uint32_t inference_u64(uint64_t value, char *out, uint32_t capacity) {
  char reverse[20]; uint32_t count = 0, written = 0;
  if (!out || !capacity) return 0;
  do { reverse[count++] = (char)('0' + value % 10U); value /= 10U; }
  while (value && count < sizeof(reverse));
  if (count + 1U > capacity) return 0;
  while (count) out[written++] = reverse[--count];
  out[written] = 0;
  return written;
}

static void inference_number(uint64_t value, uint32_t x, uint32_t y,
                             uint32_t scale, uint32_t color) {
  char number[21];
  if (inference_u64(value, number, sizeof(number)))
    qualification_text(number, x, y, scale, color);
}

static void inference_na(uint32_t x, uint32_t y, uint32_t scale,
                         uint32_t color) {
  qualification_text("N/A", x, y, scale, color);
}

static void inference_millis(uint64_t nanoseconds, uint32_t x, uint32_t y,
                             uint32_t scale, uint32_t color) {
  if (nanoseconds == AIUEOS_INFERENCE_UNMEASURED) {
    inference_na(x, y, scale, color); return;
  }
  inference_number(nanoseconds / 1000000ULL, x, y, scale, color);
}

static void inference_rate(uint32_t tokens, uint64_t nanoseconds,
                           uint32_t x, uint32_t y, uint32_t scale,
                           uint32_t color) {
  uint64_t rate = aiueos_inference_milli_tokens_per_second(tokens, nanoseconds);
  if (rate == AIUEOS_INFERENCE_UNMEASURED) {
    inference_na(x, y, scale, color); return;
  }
  char whole[21];
  uint32_t whole_length = inference_u64(rate / 1000ULL, whole, sizeof(whole));
  qualification_text(whole, x, y, scale, color);
  x += whole_length * 6U * scale;
  qualification_text(".", x, y, scale, color); x += 6U * scale;
  char decimal[4] = {(char)('0' + (rate / 100ULL) % 10ULL),
                     (char)('0' + (rate / 10ULL) % 10ULL),
                     (char)('0' + rate % 10ULL), 0};
  qualification_text(decimal, x, y, scale, color);
}

static const char *inference_phase(enum aiueos_inference_phase phase) {
  switch (phase) {
    case AIUEOS_INFERENCE_ADMISSION: return "ADMISSION";
    case AIUEOS_INFERENCE_LOADING: return "LOADING";
    case AIUEOS_INFERENCE_PREFILL: return "PREFILL";
    case AIUEOS_INFERENCE_DECODING: return "DECODING";
    case AIUEOS_INFERENCE_COMPLETE: return "COMPLETE";
    case AIUEOS_INFERENCE_BLOCKED: return "BLOCKED";
    case AIUEOS_INFERENCE_ERROR: return "ERROR";
    default: return "INVALID";
  }
}

static void framebuffer_commit_region(uint32_t x, uint32_t y,
                                      uint32_t width, uint32_t height) {
  desktop_surface.generation += 1;
  desktop_surface.content_hash =
    sample_hash(desktop_surface_pixels, desktop_surface.width,
                desktop_surface.height, desktop_surface.stride);
  desktop_surface.damage_x = x; desktop_surface.damage_y = y;
  desktop_surface.damage_width = width;
  desktop_surface.damage_height = height;
}

static void framebuffer_commit_full(void) {
  framebuffer_commit_region(0, 0, desktop_surface.width,
                             desktop_surface.height);
}

int aiueos_framebuffer_inference_screen(
    const struct aiueos_inference_status *status) {
  if (!desktop_surface_ready || !aiueos_inference_status_valid(status)) return 0;
  uint32_t scale = desktop_surface.width >= 1280 ? 4U :
                   desktop_surface.width >= 800 ? 3U : 2U;
  uint32_t margin = desktop_surface.width / 18U;
  uint32_t value_x = desktop_surface.width / 2U;
  uint32_t y = margin + 12U * scale;
  uint32_t value_y = y + 10U * scale;
  uint32_t row = 10U * scale;
  uint32_t accent = 0x3b82f6U;
  if (status->phase == AIUEOS_INFERENCE_COMPLETE) accent = 0x35d07fU;
  if (status->phase == AIUEOS_INFERENCE_BLOCKED ||
      status->phase == AIUEOS_INFERENCE_ERROR) accent = 0xff6b6bU;
  int full_redraw = !inference_screen_initialized;
  if (full_redraw) {
    rectangle(desktop_surface_pixels, desktop_surface.stride,
              desktop_surface.pixel_format, 0, 0, desktop_surface.width,
              desktop_surface.height, 0x0b1220U);
  } else {
    /* The GOP aperture is the live scanout.  Clearing it wholesale exposed a
       dark frame on every ADMISSION/ERROR and every model-layer callback.
       Keep the static labels intact and erase only the changing value pane. */
    rectangle(desktop_surface_pixels, desktop_surface.stride,
              desktop_surface.pixel_format, value_x, value_y,
              desktop_surface.width - margin - value_x,
              10U * row, 0x0b1220U);
  }
  rectangle(desktop_surface_pixels, desktop_surface.stride,
            desktop_surface.pixel_format, margin, margin,
            desktop_surface.width - 2U * margin, 3U * scale, accent);
  if (full_redraw) {
    uint32_t identity_scale = desktop_surface.width >= 1280 ? 3U : 2U;
    framebuffer_build_identity(margin, margin + 5U * scale, identity_scale);
  }
  if (full_redraw)
    qualification_text("AIUEOS INFERENCE", margin, y, scale, 0xf4f7f9U);
  y += row;
  if (full_redraw)
    qualification_text(status->model, margin, y, scale, 0xf4f7f9U);
  qualification_text(status->quant, value_x, y, scale, 0x94a3b8U);
  y += row;
  if (full_redraw)
    qualification_text("STATE", margin, y, scale, 0x94a3b8U);
  qualification_text(inference_phase(status->phase), value_x, y, scale, accent);
  y += row;
  if (full_redraw)
    qualification_text("DETAIL", margin, y, scale, 0x94a3b8U);
  qualification_text(status->detail ? status->detail : "N/A",
                     value_x, y, scale, 0xf4f7f9U);
  y += row;
  if (full_redraw)
    qualification_text("LOAD MS", margin, y, scale, 0x94a3b8U);
  inference_millis(status->load_ns, value_x, y, scale, 0xf4f7f9U);
  y += row;
  if (full_redraw)
    qualification_text("PREFILL TOK/S", margin, y, scale, 0x94a3b8U);
  inference_rate(status->prompt_tokens, status->prefill_ns,
                 value_x, y, scale, 0xf4f7f9U);
  y += row;
  if (full_redraw)
    qualification_text("DECODE TOK/S", margin, y, scale, 0x94a3b8U);
  inference_rate(status->decode_tokens, status->decode_ns,
                 value_x, y, scale, 0xf4f7f9U);
  y += row;
  if (full_redraw)
    qualification_text("TOKENS", margin, y, scale, 0x94a3b8U);
  inference_number(status->generated_tokens, value_x, y, scale, 0xf4f7f9U);
  if (status->target_tokens) {
    uint32_t offset = qualification_text_width("00000000", scale);
    qualification_text("/", value_x + offset, y, scale, 0x94a3b8U);
    inference_number(status->target_tokens, value_x + offset + 6U * scale,
                     y, scale, 0xf4f7f9U);
  }
  y += row;
  if (full_redraw)
    qualification_text("RESIDENT MIB", margin, y, scale, 0x94a3b8U);
  if (status->resident_bytes == AIUEOS_INFERENCE_UNMEASURED)
    inference_na(value_x, y, scale, 0xf4f7f9U);
  else
    inference_number(status->resident_bytes / (1024ULL * 1024ULL),
                     value_x, y, scale, 0xf4f7f9U);
  y += row;
  if (full_redraw)
    qualification_text("TTFT MS", margin, y, scale, 0x94a3b8U);
  inference_millis(status->time_to_first_token_ns,
                   value_x, y, scale, 0xf4f7f9U);
  y += row;
  if (full_redraw)
    qualification_text("CYCLES", margin, y, scale, 0x94a3b8U);
  if (status->compute_cycles) inference_number(status->compute_cycles,
                                               value_x, y, scale, 0xf4f7f9U);
  else inference_na(value_x, y, scale, 0xf4f7f9U);

  uint32_t bar_y = desktop_surface.height - margin - 6U * scale;
  uint32_t bar_width = desktop_surface.width - 2U * margin;
  rectangle(desktop_surface_pixels, desktop_surface.stride,
            desktop_surface.pixel_format, margin, bar_y, bar_width,
            6U * scale, 0x1e293bU);
  uint32_t fill = 0;
  if (status->target_tokens)
    fill = (uint32_t)(((uint64_t)bar_width * status->generated_tokens) /
                      status->target_tokens);
  else if (status->phase == AIUEOS_INFERENCE_COMPLETE) fill = bar_width;
  else if (status->phase >= AIUEOS_INFERENCE_LOADING &&
           status->phase <= AIUEOS_INFERENCE_DECODING)
    fill = bar_width * (uint32_t)status->phase / 5U;
  if (fill) rectangle(desktop_surface_pixels, desktop_surface.stride,
                      desktop_surface.pixel_format, margin, bar_y, fill,
                      6U * scale, accent);
  inference_screen_initialized = 1;
  if (full_redraw) framebuffer_commit_full();
  else framebuffer_commit_region(
    margin, margin, desktop_surface.width - 2U * margin,
    bar_y + 6U * scale - margin);
  return 1;
}

void aiueos_framebuffer_qualification_screen(const char *line1,
                                             const char *line2,
                                             const char *line3,
                                             int success) {
  if (!desktop_surface_ready) return;
  inference_screen_initialized = 0;
  uint32_t scale = desktop_surface.width >= 1280 ? 6 : 4;
  uint32_t margin = desktop_surface.width / 18;
  uint32_t top = desktop_surface.height / 5;
  uint32_t background = success ? 0x083f2e : 0x681c28;
  uint32_t accent = success ? 0x35d07f : 0xff6b6b;
  rectangle(desktop_surface_pixels, desktop_surface.stride,
            desktop_surface.pixel_format, 0, 0, desktop_surface.width,
            desktop_surface.height, background);
  rectangle(desktop_surface_pixels, desktop_surface.stride,
            desktop_surface.pixel_format, margin, margin,
            desktop_surface.width - 2 * margin, scale * 2, accent);
  {
    uint32_t identity_scale = desktop_surface.width >= 1280 ? 3U : 2U;
    framebuffer_build_identity(margin, margin + 4U * scale, identity_scale);
  }
  qualification_text(line1, margin, top, scale, 0xf4f7f9);
  qualification_text(line2, margin, top + 12 * scale, scale, 0xf4f7f9);
  qualification_text(line3, margin, top + 24 * scale, scale, accent);
  framebuffer_commit_full();
}

/* Boot-desktop WM rects (ADR-0091 hit geometry). C fills and samples;
   Kotoba names which id is front. RGB survives format-0 vs BGR swap as
   distinct stored values. */
#define AIUEOS_WM_WIN1_X 32U
#define AIUEOS_WM_WIN1_Y 32U
#define AIUEOS_WM_WIN1_W 720U
#define AIUEOS_WM_WIN1_H 540U
#define AIUEOS_WM_WIN1_RGB 0x00aa2222U
#define AIUEOS_WM_WIN2_X 96U
#define AIUEOS_WM_WIN2_Y 72U
#define AIUEOS_WM_WIN2_W 640U
#define AIUEOS_WM_WIN2_H 480U
#define AIUEOS_WM_WIN2_RGB 0x0022aa55U

static int wm_rect_fits(uint32_t x, uint32_t y, uint32_t w, uint32_t h) {
  return desktop_surface_ready && w && h &&
    x < desktop_surface.width && y < desktop_surface.height &&
    w <= desktop_surface.width - x && h <= desktop_surface.height - y;
}

int aiueos_desktop_wm_rects_fit(void) {
  return wm_rect_fits(AIUEOS_WM_WIN1_X, AIUEOS_WM_WIN1_Y,
                      AIUEOS_WM_WIN1_W, AIUEOS_WM_WIN1_H) &&
    wm_rect_fits(AIUEOS_WM_WIN2_X, AIUEOS_WM_WIN2_Y,
                 AIUEOS_WM_WIN2_W, AIUEOS_WM_WIN2_H);
}

uint32_t aiueos_desktop_wm_stored_color(uint64_t window_id) {
  uint32_t rgb = 0;
  if (window_id == 1) rgb = AIUEOS_WM_WIN1_RGB;
  else if (window_id == 2) rgb = AIUEOS_WM_WIN2_RGB;
  else return 0;
  if (!desktop_surface_ready) return 0;
  return pixel(rgb, desktop_surface.pixel_format);
}

static void paint_wm_window(uint64_t window_id) {
  if (window_id == 1)
    rectangle(desktop_surface_pixels, desktop_surface.stride,
              desktop_surface.pixel_format, AIUEOS_WM_WIN1_X, AIUEOS_WM_WIN1_Y,
              AIUEOS_WM_WIN1_W, AIUEOS_WM_WIN1_H, AIUEOS_WM_WIN1_RGB);
  else if (window_id == 2)
    rectangle(desktop_surface_pixels, desktop_surface.stride,
              desktop_surface.pixel_format, AIUEOS_WM_WIN2_X, AIUEOS_WM_WIN2_Y,
              AIUEOS_WM_WIN2_W, AIUEOS_WM_WIN2_H, AIUEOS_WM_WIN2_RGB);
}

int aiueos_desktop_wm_paint(uint64_t front) {
  uint64_t back;
  if (!aiueos_desktop_wm_rects_fit()) return 0;
  if (front != 1 && front != 2) return 0;
  back = (front == 2) ? 1 : 2;
  paint_wm_window(back);
  paint_wm_window(front);
  desktop_surface.generation += 1;
  desktop_surface.content_hash =
    sample_hash(desktop_surface_pixels, desktop_surface.width,
                desktop_surface.height, desktop_surface.stride);
  desktop_surface.damage_x = AIUEOS_WM_WIN1_X;
  desktop_surface.damage_y = AIUEOS_WM_WIN1_Y;
  desktop_surface.damage_width = AIUEOS_WM_WIN1_W;
  desktop_surface.damage_height = AIUEOS_WM_WIN1_H;
  return 1;
}

/* Guest browser desktop frame (ADR-0223). Present a retained draw list that
   `kotoba_aiueos_browser_frame` wrote: 24-byte ops of kind 1 (rect), painted
   in list order, which is the guest's z-order. C decides nothing here -- no
   reorder, no colour, no skipping. An op kind it does not know, or a rect
   that leaves the surface, refuses the whole frame (atomic replacement,
   browser.desktop-backend `:frame/present`) rather than painting part of it. */
uint32_t aiueos_desktop_width(void) { return desktop_surface_ready ? desktop_surface.width : 0; }
uint32_t aiueos_desktop_height(void) { return desktop_surface_ready ? desktop_surface.height : 0; }

int aiueos_desktop_present_ops(const uint32_t *ops, uint64_t count) {
  if (!desktop_surface_ready || !ops || count == 0 || count > 64) return 0;
  for (uint64_t i = 0; i < count; i++) {
    const uint32_t *op = ops + i * 6;
    if (op[0] != 1 || !wm_rect_fits(op[1], op[2], op[3], op[4])) return 0;
  }
  for (uint64_t i = 0; i < count; i++) {
    const uint32_t *op = ops + i * 6;
    rectangle(desktop_surface_pixels, desktop_surface.stride,
              desktop_surface.pixel_format, op[1], op[2], op[3], op[4], op[5]);
  }
  desktop_surface.generation += 1;
  desktop_surface.content_hash =
    sample_hash(desktop_surface_pixels, desktop_surface.width,
                desktop_surface.height, desktop_surface.stride);
  desktop_surface.damage_x = 0;
  desktop_surface.damage_y = 0;
  desktop_surface.damage_width = desktop_surface.width;
  desktop_surface.damage_height = desktop_surface.height;
  return 1;
}

/* Guest browser desktop frame with text (ADR-0224). The list
   `kotoba_aiueos_browser_frame2` wrote: kind 1 rect as above, kind 2 glyph
   (x, y, glyph index, width 8|16, rgb) whose 16 rows are read from the
   aiueos-font/v1 blob. Painted in list order; the whole frame is refused if
   any op is unknown, off the surface, or names a glyph the font lacks. */
static uint32_t font_word(const uint8_t *font, uint64_t index) {
  const uint8_t *p = font + index * 4;
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* ADR-0261: the UI scale. Kotoba lays the desktop out in a logical viewport (surface words 3 and 4) and chooses
   the scale in percent; C only magnifies what it paints. At 100 nothing below differs from before. Above it a
   rect (x, y, w, h) covers [x s / 100, ceil ((x + w) s / 100)) on each axis and each set bit of a glyph is the
   block of the same rule -- the ceiling leaves no seam and the last logical column reaches the physical edge. */
static uint32_t desktop_ui_scale = 100;
int aiueos_desktop_set_scale(uint32_t pct) {
  if (!desktop_surface_ready || pct < 100 || pct > 200) return 0;
  desktop_ui_scale = pct;
  return 1;
}
uint32_t aiueos_desktop_scale(void) { return desktop_ui_scale; }

static void scaled_fill(uint32_t x0, uint32_t y0, uint32_t x1, uint32_t y1, uint32_t colour) {
  uint32_t s = desktop_ui_scale;
  uint32_t a = x0 * s / 100U, b = (x1 * s + 99U) / 100U;
  uint32_t c = y0 * s / 100U, d = (y1 * s + 99U) / 100U;
  if (b > desktop_surface.width) b = desktop_surface.width;
  if (d > desktop_surface.height) d = desktop_surface.height;
  for (uint32_t row = c; row < d; row++)
    for (uint32_t column = a; column < b; column++)
      desktop_surface_pixels[(uint64_t)row * desktop_surface.stride + column] = colour;
}

int aiueos_desktop_present_ops2(const uint32_t *ops, uint64_t count,
                                const uint8_t *font, uint64_t font_length) {
  uint64_t glyphs;
  if (!desktop_surface_ready || !ops || count == 0 || count > 261 ||
      !font || font_length < 16 || font_word(font, 0) != 0x46554941U) return 0;
  glyphs = font_word(font, 2);
  if (!glyphs || font_length < 16 + glyphs * 36) return 0;
  for (uint64_t i = 0; i < count; i++) {
    const uint32_t *op = ops + i * 6;
    if (op[0] == 1) {
      if (!wm_rect_fits(op[1], op[2], op[3], op[4])) return 0;
    } else if (op[0] == 2) {
      if ((op[4] != 8 && op[4] != 16) || op[3] >= glyphs ||
          !wm_rect_fits(op[1], op[2], op[4], 16)) return 0;
    } else {
      return 0;
    }
  }
  for (uint64_t i = 0; i < count; i++) {
    const uint32_t *op = ops + i * 6;
    if (op[0] == 1) {
      if (desktop_ui_scale == 100)
        rectangle(desktop_surface_pixels, desktop_surface.stride,
                  desktop_surface.pixel_format, op[1], op[2], op[3], op[4], op[5]);
      else
        scaled_fill(op[1], op[2], op[1] + op[3], op[2] + op[4],
                    pixel(op[5], desktop_surface.pixel_format));
    } else {
      const uint8_t *bits = font + 16 + glyphs * 4 + (uint64_t)op[3] * 32;
      uint32_t colour = pixel(op[5], desktop_surface.pixel_format);
      for (uint32_t row = 0; row < 16; row++) {
        uint32_t line = ((uint32_t)bits[row * 2] << 8) | bits[row * 2 + 1];
        for (uint32_t column = 0; column < op[4]; column++)
          if (line & (0x8000U >> column)) {
            if (desktop_ui_scale == 100)
              desktop_surface_pixels[(uint64_t)(op[2] + row) * desktop_surface.stride +
                                     op[1] + column] = colour;
            else
              scaled_fill(op[1] + column, op[2] + row, op[1] + column + 1, op[2] + row + 1, colour);
          }
      }
    }
  }
  desktop_list_base_generation = desktop_surface.generation;
  desktop_surface.generation += 1;
  desktop_surface.content_hash =
    sample_hash(desktop_surface_pixels, desktop_surface.width,
                desktop_surface.height, desktop_surface.stride);
  desktop_surface.damage_x = 0;
  desktop_surface.damage_y = 0;
  desktop_surface.damage_width = desktop_surface.width;
  desktop_surface.damage_height = desktop_surface.height;
  desktop_list_ops = ops;
  desktop_list_count = count;
  desktop_list_generation = desktop_surface.generation;
  return 1;
}

/* Put what is in the framebuffer on the real display (ADR-0224): see
   aiueos_gpu_present_desktop_rect in pci.c. 1 shown (or nothing to show),
   0 not (no controlq, a stride wider than the width, or a scanout of
   another size).

   ADR-0242: only the damage. When the framebuffer holds a list
   aiueos_desktop_present_ops2 painted over exactly what was last sent, Kotoba
   `kotoba_aiueos_browser_damage` compares that list with the last one it was
   handed (kept in desktop_shadow) and answers the rectangle that can have
   changed; this sends that rectangle, or nothing when it is empty. Anything
   else -- a paint that was not such a list, a show with no new list, a list
   painted over a frame that was never sent, a refusal, a failed transfer --
   sends the whole screen and makes the next list compare against nothing.
   C decides nothing about which pixels changed. */
extern int aiueos_gpu_present_desktop_rect(uint64_t address, uint32_t width, uint32_t height,
                                           uint32_t stride, uint32_t pixel_format,
                                           uint32_t x, uint32_t y, uint32_t w, uint32_t h);
/* A2: drain a host display change, re-read the geometry and drop the GPU
   desktop resource so the next present re-binds it. Returns 1 when the
   geometry changed and the caller must send a full frame. */
extern int aiueos_gpu_display_refresh(void);
extern int aiueos_gpu_geometry_changed_take(void);
extern uint32_t aiueos_dhcp_lease_seconds(void);
extern volatile uint64_t aiueos_apic_timer_ticks;
extern void aiueos_kernel_serial_marker(const char *text);

/* C9: the status area — network, power and clock — painted on the desktop
   surface on every frame and announced once per state. The clock shows the
   APIC timer ticks (the guest's running timebase); power is AC in the
   reference VM (there is no battery device to read). */
static uint32_t status_last_state; /* 0 = unseen, 1 = offline, 2 = online */
#ifdef AIUEOS_BATTERY_PROBE
/* I2: there is no battery device in the reference VM (no ACPI BAT0; QEMU's PC
   machines expose none), so the level lives in the guest and the gate drives
   it: start on AC at 100, switch to battery, drain through the scripted
   steps, warn at and below 10, and let the stage send the machine to the
   existing suspend path at critical. The receipt says the source is
   synthetic; the level reading, the warning and the sleep are real guest
   behaviour. */
static uint32_t battery_level = 100, battery_ac = 1;
void aiueos_desktop_battery_set(uint32_t ac, uint32_t level) {
  battery_ac = ac ? 1 : 0;
  battery_level = level > 100 ? 100 : level;
}
uint32_t aiueos_desktop_battery_level(void) { return battery_level; }
uint32_t aiueos_desktop_battery_ac(void) { return battery_ac; }
#endif
/* The pointer rectangle the stages last drew (ADR-0236), reported by
   aiueos_desktop_set_pointer. The bar paints AFTER the frame, so without this
   it covered the arrow: measured 2026-10-26, the cursor stage's corner point
   (1276,796) sampled 0x00202830 -- the bar's own colour -- instead of the
   tip's 0x333333, one frame failed, and the stage chain behind it (FOCUS ..
   SCALE .. SUSPEND) never ran. list -> status bar -> pointer is the order a
   desktop keeps: the bar draws, then the pointer's pixels go back on top. */
static uint32_t pointer_x = 0xffffffffU, pointer_y; /* x sentinel = none */
void aiueos_desktop_set_pointer(uint32_t x, uint32_t y) { pointer_x = x; pointer_y = y; }
/* .high_bss: the low layout is at its budget (qualification/low-region-budget.edn).
   Bounded by construction: only the 14 band rows and 16 pointer columns. */
static uint32_t saved_pointer[14 * 16] __attribute__((section(".high_bss")));
void aiueos_desktop_paint_status(void) {
  char line[64];
  uint32_t y, x;
  uint32_t online = aiueos_dhcp_lease_seconds() > 0;
  uint32_t save_r0 = 0, save_rows = 0, save_c0 = 0, save_cols = 0;
  if (!desktop_surface_ready) return;
  y = desktop_surface.height - 14;
  /* 1. lift the pointer pixels that live inside the band */
  if (pointer_x != 0xffffffffU) {
    uint32_t r0 = (pointer_y > 1U) ? pointer_y - 1U : 0U;
    uint32_t r1 = pointer_y + 17U;
    uint32_t c0 = (pointer_x > 1U) ? pointer_x - 1U : 0U;
    uint32_t c1 = pointer_x + 14U;
    if (r1 > y && r0 < y + 14U) {
      save_r0 = (r0 < y) ? y : r0;
      save_rows = ((r1 > y + 14U) ? y + 14U : r1) - save_r0;
      save_c0 = c0;
      save_cols = (c1 > desktop_surface.width ? desktop_surface.width : c1) - c0;
      if (save_cols > 16U) save_cols = 16U;
      for (uint32_t r = 0; r < save_rows; r++)
        for (uint32_t c = 0; c < save_cols; c++)
          saved_pointer[r * 16U + c] =
            desktop_surface_pixels[(save_r0 + r) * desktop_surface.stride + save_c0 + c];
    }
  }
  /* 2. the bar and its text */
  rectangle(desktop_surface_pixels, desktop_surface.stride,
            desktop_surface.pixel_format, 0, y, desktop_surface.width, 14, 0x00202830U);
  x = 4;
  qualification_text(online ? "NET ONLINE" : "NET OFFLINE", x, y + 3, 1,
                     online ? 0x0060d080U : 0x00d08060U);
  x += 6 * 11;
#ifdef AIUEOS_BATTERY_PROBE
  /* I2: the reference VM has no battery device (no ACPI BAT0, and QEMU's PC
     machines expose none), so the level is driven by the guest's own power
     state machine -- set through aiueos_desktop_battery_set. Eight glyph
     cells either way ("POWER AC" / "BAT 100%"), so the CLK column does not
     move and the band's geometry is the same shape the models know; the
     colour turns to the warning hue at and below 10. Production builds carry
     none of this: the flag is unset and the line below is the only POWER
     text that exists. */
  if (battery_ac) {
    qualification_text("POWER AC", x, y + 3, 1, 0x00c0c0c0U);
  } else {
    char bat[16];
    uint32_t lv = battery_level > 100 ? 100 : battery_level;
    bat[0] = 'B'; bat[1] = 'A'; bat[2] = 'T'; bat[3] = ' ';
    bat[4] = (char)('0' + (lv / 100) % 10);
    bat[5] = (char)('0' + (lv / 10) % 10);
    bat[6] = (char)('0' + (lv % 10));
    bat[7] = '%';
    bat[8] = 0;
    qualification_text(bat, x, y + 3, 1, lv <= 10 ? 0x00d08060U : 0x00c0c0c0U);
  }
#else
  qualification_text("POWER AC", x, y + 3, 1, 0x00c0c0c0U);
#endif
  x += 6 * 9;
  {
    uint64_t ticks = aiueos_apic_timer_ticks;
    int i = 0;
    line[i++] = 'C'; line[i++] = 'L'; line[i++] = 'K'; line[i++] = ' ';
    /* decimal ticks, bounded to 12 digits */
    char digits[16]; int n = 0;
    if (ticks == 0) digits[n++] = '0';
    while (ticks && n < 16) { digits[n++] = (char)('0' + (ticks % 10)); ticks /= 10; }
    while (n > 0) line[i++] = digits[--n];
    line[i] = 0;
    qualification_text(line, x, y + 3, 1, 0x00c0c0c0U);
  }
  {
    uint32_t state = online ? 2 : 1;
    if (state != status_last_state) {
      status_last_state = state;
      aiueos_kernel_serial_marker(online ? "AIUEOS_STATUS_AREA_OK network=online power=ac clock=running\r\n"
                                         : "AIUEOS_STATUS_AREA_OK network=offline power=ac clock=running\r\n");
    }
  }
  /* 3. the pointer goes back on top of the bar (see the note above
     aiueos_desktop_set_pointer). */
  for (uint32_t r = 0; r < save_rows; r++)
    for (uint32_t c = 0; c < save_cols; c++)
      desktop_surface_pixels[(save_r0 + r) * desktop_surface.stride + save_c0 + c] =
        saved_pointer[r * 16U + c];
}
extern void aiueos_kernel_serial_marker(const char *text);
extern int64_t kotoba_aiueos_browser_damage(uint64_t ops, uint64_t ops_bytes, uint64_t shadow,
                                            uint64_t shadow_bytes, uint64_t count);
int aiueos_desktop_show(void) {
  uint32_t x = 0, y = 0, w, h;
  int ok, listed;
  if (!desktop_surface_ready) return 0;
  /* A2: a display change re-binds the GPU resource; the frame after one is
     always whole. FRAMEBUFFER_PROGRESS(258) is the qualification channel;
     AIUEOS_GPU_DISPLAY_CHANGE_OK is the evidence marker (production). */
  /* refresh() first (it throttles its own device read), then the latch: the
     idle loop may have polled the same change already, and the marker must
     still fire -- once. */
  if (aiueos_gpu_display_refresh() | aiueos_gpu_geometry_changed_take()) {
    desktop_shadow[0] = 0;
    FRAMEBUFFER_PROGRESS(258);
    aiueos_kernel_serial_marker("AIUEOS_GPU_DISPLAY_CHANGE_OK rebind-fullframe\r\n");
  }
  w = desktop_surface.width;
  h = desktop_surface.height;
  listed = desktop_list_ops && desktop_list_generation == desktop_surface.generation;
  if (!listed || desktop_list_base_generation != desktop_shown_generation)
    desktop_shadow[0] = 0;
  desktop_shadow[5] = desktop_surface.width;
  desktop_shadow[6] = desktop_surface.height;
  if (listed) {
    int64_t d = (int64_t)kotoba_aiueos_browser_damage(
      (uint64_t)(uintptr_t)desktop_list_ops, 261U * 24U,
      (uint64_t)(uintptr_t)desktop_shadow, sizeof(desktop_shadow), desktop_list_count);
    if (d < 0) {
      desktop_damage_counts[4]++;
      desktop_shadow[0] = 0;
    } else {
      x = desktop_shadow[1]; y = desktop_shadow[2];
      w = desktop_shadow[3]; h = desktop_shadow[4];
    }
  }
  desktop_list_ops = 0;
  desktop_damage_last[0] = x; desktop_damage_last[1] = y;
  desktop_damage_last[2] = w; desktop_damage_last[3] = h;
  desktop_damage_counts[0]++;
  if (!w || !h) {
    desktop_damage_counts[2]++;
    desktop_shown_generation = desktop_surface.generation;
    return 1;
  }
  aiueos_desktop_paint_status();
  ok = aiueos_gpu_present_desktop_rect((uint64_t)(uintptr_t)desktop_surface_pixels,
                                       desktop_surface.width, desktop_surface.height,
                                       desktop_surface.stride, desktop_surface.pixel_format,
                                       x, y, w, h);
  if (!ok) {
    /* The blank-frame flake (JUN-142) had a silent present refusal: the
       flow computed and held, the screendump came back uniform, and
       nothing said the desktop never reached the GPU. Say it once.
       Measured 2026-10-20. */
    static int present_refusal_said;
    if (!present_refusal_said) {
      present_refusal_said = 1;
      /* 249: a desktop present refusal (JUN-142 diagnosis). This file's
         evidence channel is the qualification progress code, not serial. */
      FRAMEBUFFER_PROGRESS(249);
    }
    desktop_shadow[0] = 0;
    return 0;
  }
  desktop_damage_counts[(w == desktop_surface.width && h == desktop_surface.height) ? 3 : 1]++;
  desktop_damage_bytes += (uint64_t)w * h * 4U;
  desktop_shown_generation = desktop_surface.generation;
  return 1;
}

/* The whole screen, whatever changed (ADR-0242): what a damage present is
   compared with. The list the shadow holds is still the framebuffer's, so
   the shadow is kept. */
int aiueos_desktop_show_full(void) {
  if (!desktop_surface_ready) return 0;
  return aiueos_gpu_present_desktop_rect((uint64_t)(uintptr_t)desktop_surface_pixels,
                                         desktop_surface.width, desktop_surface.height,
                                         desktop_surface.stride, desktop_surface.pixel_format,
                                         0, 0, desktop_surface.width, desktop_surface.height);
}

/* The last show's rectangle (x y w h; w 0 when nothing was sent), and since
   boot: shows, partial sends, empty shows, whole-screen sends, refusals, and
   the bytes sent. */
void aiueos_desktop_damage_last(uint32_t *out) {
  for (int i = 0; i < 4; i++) out[i] = desktop_damage_last[i];
}
void aiueos_desktop_damage_counts(uint32_t *out, uint64_t *bytes) {
  for (int i = 0; i < 5; i++) out[i] = desktop_damage_counts[i];
  *bytes = desktop_damage_bytes;
}

/* FNV-1a over the positions of every pixel of one colour, in raster order
   (each position as the four little-endian bytes of y * 65536 + x), and how
   many there were. What a gate compares against a model of the same frame. */
uint32_t aiueos_desktop_colour_census(uint32_t rgb, uint32_t *count_out) {
  uint32_t hash = 2166136261U, count = 0;
  if (!desktop_surface_ready) { if (count_out) *count_out = 0; return 0; }
  uint32_t want = pixel(rgb, desktop_surface.pixel_format) & 0x00ffffffU;
  for (uint32_t y = 0; y < desktop_surface.height; y++)
    for (uint32_t x = 0; x < desktop_surface.width; x++) {
      if ((desktop_surface_pixels[(uint64_t)y * desktop_surface.stride + x] & 0x00ffffffU) != want)
        continue;
      uint32_t position = y * 65536U + x;
      for (int b = 0; b < 4; b++) {
        hash ^= (position >> (8 * b)) & 0xffU;
        hash *= 16777619U;
      }
      count++;
    }
  if (count_out) *count_out = count;
  return hash;
}

/* The sampled pixel as 0xRRGGBB, whatever the scanout's byte order, so a
   gate compares it with the colour the draw list names. */
uint32_t aiueos_desktop_sample_rgb(uint32_t x, uint32_t y) {
  if (!desktop_surface_ready || x >= desktop_surface.width ||
      y >= desktop_surface.height)
    return 0xffffffffU;
  return pixel(desktop_surface_pixels[(uint64_t)y * desktop_surface.stride + x],
               desktop_surface.pixel_format) & 0x00ffffffU;
}

uint32_t aiueos_desktop_sample_pixel(uint32_t x, uint32_t y) {
  if (!desktop_surface_ready || x >= desktop_surface.width ||
      y >= desktop_surface.height)
    return 0;
  return desktop_surface_pixels[(uint64_t)y * desktop_surface.stride + x];
}

static uint32_t pixel(uint32_t rgb, uint32_t format) {
  if (format == 0) return rgb;
  return ((rgb & 0xffU) << 16) | (rgb & 0xff00U) | ((rgb >> 16) & 0xffU);
}

static void rectangle(volatile uint32_t *fb, uint32_t stride, uint32_t format,
                      uint32_t x, uint32_t y, uint32_t w, uint32_t h,
                      uint32_t color) {
  color = pixel(color, format);
  for (uint32_t row = y; row < y + h; row++)
    for (uint32_t column = x; column < x + w; column++)
      fb[(uint64_t)row * stride + column] = color;
}

static uint64_t sample_hash(volatile uint32_t *fb, uint32_t width,
                            uint32_t height, uint32_t stride) {
  uint64_t hash = 1469598103934665603ULL;
  uint32_t step_x = width / 16; if (!step_x) step_x = 1;
  uint32_t step_y = height / 16; if (!step_y) step_y = 1;
  for (uint32_t y = 0; y < height; y += step_y)
    for (uint32_t x = 0; x < width; x += step_x) {
      hash ^= fb[(uint64_t)y * stride + x];
      hash *= 1099511628211ULL;
    }
  return hash;
}

int aiueos_framebuffer_initialize(const struct aiueos_boot_info *boot) {
  desktop_surface_ready = 0;
  inference_screen_initialized = 0;
  FRAMEBUFFER_PROGRESS(250);
  if (!boot || !boot->framebuffer_base || !boot->framebuffer_size ||
      boot->framebuffer_width < 320 || boot->framebuffer_height < 200 ||
      boot->framebuffer_stride < boot->framebuffer_width ||
      boot->framebuffer_format > 1 ||
      (uint64_t)boot->framebuffer_stride * boot->framebuffer_height >
        boot->framebuffer_size / 4)
    return 0;
  FRAMEBUFFER_PROGRESS(251);
  if (!aiueos_map_framebuffer(boot->framebuffer_base, boot->framebuffer_size))
    return 0;
  FRAMEBUFFER_PROGRESS(252);

  volatile uint32_t *fb = (volatile uint32_t *)(uintptr_t)boot->framebuffer_base;
  desktop_surface_pixels = fb;
  rectangle(fb, boot->framebuffer_stride, boot->framebuffer_format, 0, 0,
            boot->framebuffer_width, boot->framebuffer_height, 0x101827);
  FRAMEBUFFER_PROGRESS(253);
  uint32_t margin = boot->framebuffer_width / 16;
  uint32_t top = boot->framebuffer_height / 12;
  rectangle(fb, boot->framebuffer_stride, boot->framebuffer_format,
            margin, top, boot->framebuffer_width - 2 * margin,
            boot->framebuffer_height / 10, 0x2557a7);
  rectangle(fb, boot->framebuffer_stride, boot->framebuffer_format,
            margin, top + boot->framebuffer_height / 7,
            (boot->framebuffer_width - 3 * margin) / 2,
            boot->framebuffer_height * 2 / 3, 0xf2f5f9);
  rectangle(fb, boot->framebuffer_stride, boot->framebuffer_format,
            boot->framebuffer_width / 2 + margin / 2,
            top + boot->framebuffer_height / 7,
            (boot->framebuffer_width - 3 * margin) / 2,
            boot->framebuffer_height * 2 / 3, 0x35b779);
  FRAMEBUFFER_PROGRESS(254);
  uint64_t first = sample_hash(fb, boot->framebuffer_width,
                               boot->framebuffer_height, boot->framebuffer_stride);
  FRAMEBUFFER_PROGRESS(255);
  uint64_t second = sample_hash(fb, boot->framebuffer_width,
                                boot->framebuffer_height, boot->framebuffer_stride);
  FRAMEBUFFER_PROGRESS(256);
  if (!first || first != second) return 0;
  desktop_surface = (struct aiueos_desktop_surface){
    1, sizeof(desktop_surface), 1, 1, first,
    boot->framebuffer_width, boot->framebuffer_height, boot->framebuffer_stride,
    boot->framebuffer_format, 0, 0, boot->framebuffer_width, boot->framebuffer_height};
  desktop_surface_ready = 1;
  FRAMEBUFFER_PROGRESS(257);
  return 1;
}
