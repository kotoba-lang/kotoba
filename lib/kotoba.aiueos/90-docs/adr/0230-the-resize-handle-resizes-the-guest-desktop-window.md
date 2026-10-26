# ADR-0230 — The resize handle resizes the guest desktop's window

Date: 2026-09-24

## Status

Accepted. Closes the `:resize` floor of the ADR-0226 ladder.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-resize`
(`AIUEOS_GUEST_BROWSER=1`) prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_RESIZE_OK`:
after ADR-0229's drag (window 1 at (272, 132), 720 x 540), the host presses
the virtio-tablet at (984, 664) -- inside window 1's 16 px resize handle --
moves to (784, 564), (300, 200) and (504, 324), releases, and moves once
more to (900, 700). After the second move window 1 is 120 x 80 (the travel
would make it 36 x 76: clamped); after the third it is 240 x 200; its origin
never moves, and the move after the release changes nothing. Serial:
`AIUEOS_GUEST_BROWSER_RESIZE_OK events=6 answers=111100 clamp=120x80 size=240x200 at=272,132 capture=0 ops=67 text-px=1931 hash=36069e52`.

Not: a frame per move (`:no-redraw-per-move` -- one frame after the
gesture; the `:event-loop` floor), a resize from any edge but the
bottom-right handle (browser.input has only that one), or a maximum size.

## Decision

1. **The capture is a Kotoba decision** (`browser-reduce.kotoba`), with
   kotoba-lang/browser `browser.input/actions-for-event` as the rule: a
   pointer/down that hits a window inside its resize handle (the last 16 px
   of both axes, inclusive -- checked before the titlebar) captures
   `:resize` with the press point and the window's size at the press.
   pointer/move under a resize is `:window/resize` to
   (max 120 (w0 + px - x0)) x (max 80 (h0 + py - y0)) --
   `browser.surface/resize-window`, which keeps the origin and neither
   focuses nor raises. pointer/up clears it, as for a drag.
2. **State.** Words 25..30 of the 128-byte state: 25 kind (2 resize), 26
   window id, 27 28 the press point, 29 30 the size at the press. 29 and 30
   were spare (ADR-0229 used 25..28); every capture write now sets all six,
   so a drag leaves 29 30 at 0. `-4` now refuses a capture that is not none,
   or a drag or resize of a present window.
3. **Signed travel.** The travel is computed in the object's signed
   arithmetic, so a pointer that goes further left or up than the window is
   wide or tall clamps to 120 x 80 rather than wrapping to a huge u32
   (vector `:travel-past-the-size-clamps-not-wraps`).
4. **Expected answers come from the oracle.**
   `os/aiueos/scripts/browser-reduce-oracle.cljk` now encodes the resize
   capture and prints 40 success vectors (19 new). Two earlier vectors
   changed their expected state because a handle press now captures:
   `:pointer-down-on-the-inclusive-far-corner` and
   `:a-resize-handle-press-clears-the-capture` (the name is kept; the
   oracle's answer is that it replaces the drag with a resize). The
   hand-written `:capture-kind-2-is-refused` became
   `:capture-kind-3-is-refused`, and `:a-resize-of-no-window-is-refused`
   was added.
5. **C decides nothing.** RESIZE_GO drains the tablet ring, then C hands six
   scaled events to `kotoba_aiueos_browser_reduce`, compares the answers with
   the vectors' 1 1 1 1 0 0, and reads window 1's size after the third event
   and after the last. The frame census comes from
   `os/aiueos/scripts/browser-frame-model.cljk` (scene `resize`), which
   also pins the drag frame now.

![window 1 resized to 240 x 200 in front of window 2 (display, half size)](../../docs/assets/guest-browser-resize.png)

## Measurement

**2026-09-24, this Mac, QEMU tcg + OVMF.**

Begun by the fourth `cloud.itonami.bot.aiueos-desktop` iteration (12:49Z),
which stopped at the account's weekly limit with everything written but the
gate run and the landing; finished from its worktree by hand.

- `guest-browser-resize` (first run): `AIUEOS_COMPOSITOR_GUEST_BROWSER_RESIZE_OK`;
  serial `AIUEOS_GUEST_BROWSER_RESIZE_OK events=6 answers=111100 clamp=120x80 size=240x200 at=272,132 capture=0 ops=67 text-px=1931 hash=36069e52`,
  after the unchanged `DRAG_OK`. The display screendump
  (`guest-browser-resize.ppm`) counts 1,931 #111111 px and shows window 1 at
  240 x 200 with its body re-wrapped.
- Frame model: all seven earlier scenes reproduced; `resize` 67 ops, 1,931 px,
  36069e52.
- KIR oracle `browser-reduce-v1`: 50 vectors, 40 memory assertions, reasons
  -6..-1 and 0 1 2 observed. Seen red: the 120 floor removed →
  `width-119-clamps-to-120`.
- `browser-reduce.o` compiles byte-identical from amu main ca3d5aa9
  (reproduce match=1); digests stale=0. Classifier tests 11 / 155.
