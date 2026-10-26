# ADR-0223 — The browser surface is the guest desktop: frame and pointer on KERNEL.ELF

Date: 2026-09-24

## Status

Accepted for two **discriminating guest slices** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` Desktop leftover, under
kotoba-lang/browser ADR 0002 ("Browser UI is the aiueos desktop").

- **Frame is green only when**
  `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-frame`
  prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_FRAME_OK`: KERNEL.ELF serial has
  `AIUEOS_GUEST_BROWSER_FRAME_OK ops=5 overlap=d8e7ff win1-title=dde2ea surface=WxH`.
- **Pointer is green only when** `... guest-browser-input` prints
  `AIUEOS_COMPOSITOR_GUEST_BROWSER_INPUT_OK`: the same boot also has
  `AIUEOS_GUEST_BROWSER_INPUT_OK eventq-used=1 kind=pointer-down px=.. py=.. hit=1 front=1 overlap=ffffff win1-title=d8e7ff`.

Hosted `browser.desktop-backend` frames (JS/JVM), hosted `kbb -M:compositor wm`
serial and the synthetic keyboard fill do **not** count.

Not executable, and stated here rather than at the end:

- **This is not kotoba-lang/browser running on the kernel.** The browser
  repository is `.cljk` (DOM, cssom layout, text edit); none of it compiles
  to `x86_64-aiueos-kernel-v1`. What runs here are two Kotoba objects that
  mirror three of its decisions, each named in the object header:
  `:surface/windows` order is z-order (browser.surface/focus-window), a
  pointer/down hits the topmost window with an inclusive point-in-rect and
  focuses AND raises it (browser.input/window-at + focus-window), and the
  window colours and 28 px titlebar (browser.surface/window-node,
  browser.input/titlebar-height). Migrating the browser component itself is
  a separate, whole-component job.
- **No text.** Titles, the launcher row and document bodies are not drawn.
  Named leftover `:no-text-raster` (no font in the kernel).
- **No drag, resize, text edit or IME through this path.** Named leftovers
  `:no-pointer-capture`, `:no-text-edit`.
- **Not P5.** QEMU ≠ P5; the tablet press is injected over QMP
  (`input-send-event`), which is a real virtio-tablet used-ring event but not
  a laptop HID.
- **Not a new compositor repo.** The decisions live in `os/aiueos/kotoba/`
  beside `wm-hit` and `session-restore`.

**Correction (ADR-0224).** The frames measured here were drawn into the GOP
framebuffer after virtio-gpu had taken the display, so they were in memory
and not on screen; the gates read memory and stay correct. ADR-0224 puts the
desktop on virtio-gpu scanout 0.

## Context

kotoba-lang/browser ADR 0002 decided that the browser guest owns windows,
z-order, focus and the retained draw list, and that an OS backend only
presents frames (`:frame/present`), delivers canonical input (`:input/events`)
and services brokered effects. `apps/session/kotoba-browser.edn` names
`:kotoba-lang/browser` as the aiueos UI engine with
`:native-runtime {:state :pending-native-browser-guest}`. Guest gates up to
ADR-0098 painted two fixed rects in C from a Kotoba front id; nothing on
KERNEL.ELF produced a draw list, and nothing turned a pointer into a surface
action.

## Decision

1. Two kernel objects, one export each (no cross-object calls, ADR-0030):
   - `browser-frame.kotoba` → `kotoba_aiueos_browser_frame(state, 128, ops, ops-bytes)`
     writes the retained list: workspace, then body + titlebar per window in
     stack order; returns `1 + 2n` or a negative reason.
   - `browser-reduce.kotoba` → `kotoba_aiueos_browser_reduce(state, 128, kind, a, b)`
     applies one event in place: kind 1 pointer/down (hit, focus, raise;
     0 on a miss), kind 2 key (goes to the focused window, moves nothing).
   State is 128 bytes of u32 words (abi, n ≤ 4, focus, viewport, then
   `id x y w h` per window, bottom first). Word types and at most five
   parameters are temporary native constraints, written in both headers with
   their removal condition.
2. kotoba-native `kernel-object-entries` rows `aiueos-browser-frame` (arity 4)
   and `aiueos-browser-reduce` (arity 5), both twins, default fuel tier 1024.
3. C is mechanism only: `aiueos_desktop_present_ops` paints the list in list
   order and refuses the whole frame on an unknown op or an off-surface rect;
   `aiueos_desktop_sample_rgb` reads back 0xRRGGBB. The virtio-input driver
   tells a tablet from a keyboard by the EV_BITS/EV_ABS config bitmap,
   recycles descriptors, and records ABS_X/ABS_Y at the BTN_LEFT press; C
   scales 0..32767 to surface pixels. C never picks a window, an order or a
   colour.
4. `smoke-qemu-uefi.sh`: `AIUEOS_GUEST_BROWSER=1` is guest-input plus
   `-device virtio-tablet-pci` and a QMP press at absolute (1536, 2048) —
   inside window 1 and outside window 2 on any surface the boot-desktop fits.
   No new `.sh`.
5. KIR-oracle contracts `browser-frame-v1` and `browser-reduce-v1`
   (`verify-admissions.cljk`, region builder): every success vector asserts
   the whole op list or the whole state after the event.

## Consequences

The desktop draw list and the pointer decision now exist on KERNEL.ELF, in
browser's own vocabulary. Leftover after both gates: `:no-text-raster`,
`:no-pointer-capture`, `:no-text-edit`, `:native-compositor-absent` (native
component runtime), browser component migration, P5. The Chrome OS-shaped
desktop goal is **not complete**.

## Measurement

**2026-09-24, this Mac, QEMU tcg + OVMF.**

- KIR oracle, fuel 1024: `browser-frame-v1` 14 vectors, 4 memory
  assertions, reasons -5..-1 and counts 3/5/9 observed; `browser-reduce-v1`
  14 vectors, 7 memory assertions, reasons -5 -3 -2 -1 and results 0/1/2.
- Seen red for the named reason: raise dropped → memory mismatch on
  `pointer-down-on-window-1-only-raises-it`; bottom-first hit → vector
  mismatch on `pointer-down-on-the-overlap-hits-the-front`; every window
  coloured focused → memory mismatch on `boot-two-windows-front-2`.
- Fuel bisected in the oracle: frame traps at 128 (four windows) and passes
  at 256; reduce traps at 64 and passes at 128. The default tier 1024 is 4x
  and 8x those.
- `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-input`
  printed `AIUEOS_COMPOSITOR_GUEST_BROWSER_INPUT_OK`, leftover
  `[:no-pointer-capture :no-text-raster]`. Serial of the same boot:

      AIUEOS_GUEST_BROWSER_TABLET tablets=1 press=1 used=3 abs=2 key=1
      AIUEOS_GUEST_INPUT_OK eventq-used=1 synthetic=0
      AIUEOS_GUEST_BROWSER_FRAME_OK ops=5 overlap=d8e7ff win1-title=dde2ea surface=1280x800
      AIUEOS_GUEST_BROWSER_INPUT_OK eventq-used=1 kind=pointer-down px=60 py=50 hit=1 front=1 overlap=ffffff win1-title=d8e7ff

  The same boot still carries guest-input / IME / WM / broker / session /
  paint / gpu-two green.
- Seen red on QEMU before it went green, for the named reason each time:
  `:no-pointer-event` with `used=0` (the tablet was found, nothing arrived).
  Two causes, fixed in the injector, not the guest: the 90 s send window
  closed before the tablet was up, and x + y + press + release + SYN is five
  events, one more than the four buffers the driver posts, so QEMU dropped
  every batch whole. The press now goes as x + y + press, the release alone.
- Objects: browser-frame.o `d828fde6…` (4,416 B), browser-reduce.o
  `af0fa4f5…` (3,672 B), byte-identical from amu with kotoba-native 989316b.
