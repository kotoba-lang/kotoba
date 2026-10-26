# ADR-0231 — One running loop drives the guest desktop

Date: 2026-09-25

## Status

Accepted. Closes the `:event-loop` floor of the ADR-0226 ladder.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-event-loop`
(`AIUEOS_GUEST_BROWSER=1`, `AIUEOS_QEMU_TIMEOUT=600`) prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_EVENT_LOOP_OK`: after ADR-0230's resize, one
loop polls the virtio-tablet and the virtio-keyboard in turn and takes, in
this order and each only after the previous event's frame line, `k` `a`
Enter (into window 1), a tablet press on window 2's titlebar at (150, 85), a
move to (250, 185), a release, and `n` `i` Enter (into window 2) -- and
presents a frame after every one of the nine. Serial: nine
`AIUEOS_GUEST_BROWSER_LOOP_FRAME n=<1..9> ...` lines and
`AIUEOS_GUEST_BROWSER_LOOP_OK events=9 frames=9 answers=001220001 focus=2 at=196,172 capture=0 chain=f999ccaa ops=69 text-px=890 hash=6bd523d7 idle-min=<n>`
with `n > 0`.

Not: an unbounded loop. It ends after nine events, or after 60,000 empty
rounds (`:fixed-event-count` -- a desktop that runs until shutdown needs a
reason to stop that is not a count). Not a caret (`:no-caret`, the `:caret`
floor). Frames are drawn whole, not damaged regions.

## Decision

1. **The loop is mechanism, so it is C.** Every earlier gate read a fixed
   sequence from ONE device and drew once at its end
   (`:no-redraw-per-move`). The loop in `os/aiueos/kernel/main.c` polls
   `aiueos_tablet_next` and `aiueos_keyboard_next_press` with a 1,024-poll
   budget each, alternately, and hands whatever arrives to its reducer:
   a pointer batch to `kotoba_aiueos_browser_reduce`, a key press to
   `kotoba_aiueos_browser_key`. Routing by device is not a decision about
   the surface; what the event does is still the Kotoba objects', unchanged.
   No object, contract, kotoba-native row or amu pin changes in this ADR.
2. **A frame after each event.** `kotoba_aiueos_browser_frame2` and
   `aiueos_desktop_present_ops2` run after every event, then the census of
   #111111 and `aiueos_desktop_show`. The nine census hashes are folded,
   in order, into an FNV-1a chain (each hash as four little-endian bytes).
3. **Expected values come from the model, not the kernel.**
   `os/aiueos/scripts/browser-frame-model.cljk` now pins ADR-0230's resize
   frame and lays out the nine loop frames (composition `k`, か, committed か;
   window 2 focused and raised; moved to (196, 172); `n`, に, committed に),
   giving ops 69 69 68 68 68 68 70 70 69, the final census 890 px /
   6bd523d7, and chain f999ccaa. The answers 0 0 1 2 2 0 0 0 1 are the
   objects' documented contracts: a key answers what it committed, a pointer
   answers a window id (browser-reduce-v1 `:dragging-window-2-leaves-window-1`).
4. **The order is the host's.** Two rings are polled; if both held an event,
   the poll order would decide. The QMP injector sends event k+1 only after
   the serial shows `LOOP_FRAME n=k` and it has screendumped that frame, half
   a second later. So the nine events take several seconds and every frame is
   on the display when it is dumped.
5. **"Running" is measured.** `idle-min` is the fewest empty poll rounds
   between two events. The classifier refuses `idle-min=0`
   (`:loop-not-waiting`): an event that was already queued when the loop
   polled would prove a batch, not a loop.
6. **Wall clock.** The browser profile's resize alone ended at T+351 s of the
   360 s default (first run, 2026-09-25: `GUEST-NO-EXIT ... ended by: the wall
   clock`), so this profile sets `AIUEOS_QEMU_TIMEOUT=600`. The earlier
   browser profiles keep 360.

![window 2 focused and dragged to (196, 172) in front of window 1, frame 5 of the loop (display, half size)](../../docs/assets/guest-browser-event-loop.png)

## Measurement

**2026-09-25, this Mac, QEMU tcg + OVMF.**

- `guest-browser-event-loop` (third run): `AIUEOS_COMPOSITOR_GUEST_BROWSER_EVENT_LOOP_OK`,
  leftover `[:no-caret :fixed-event-count]`; serial, after the unchanged
  `RESIZE_OK`:
  `AIUEOS_GUEST_BROWSER_LOOP_OK events=9 frames=9 answers=001220001 focus=2 at=196,172 capture=0 chain=f999ccaa ops=69 text-px=890 hash=6bd523d7 idle-min=121`.
  The nine `LOOP_FRAME` lines carry exactly the model's per-frame censuses:
  1958/f7326f2e, 1982/2bd786ab, 1966/b8ef023b, 742/0732c1f9, 864/e9878e25,
  864/e9878e25, 891/66c3ef73, 906/69b35327, 890/6bd523d7.
- Display: the screendumps `guest-browser-loop-1.ppm` .. `-8.ppm` and
  `guest-browser-loop.ppm` count 1958, 1982, 1966, 742, 864, 864, 891, 906
  and 890 #111111 px -- the memory census, frame by frame (6 colours each,
  4 on frame 4 where window 2 covers window 1 whole).
- Seen red, twice:
  - The second run expected the pointer answers to be 1 (as in the drag) and
    got the window id 2: `AIUEOS_GUEST_BROWSER_LOOP leftover=census-miss off=2 frames=9 chain=f999ccaa`
    -- every frame matched, the answers did not, and the gate refused.
  - No frame after a pointer move (the old `:no-redraw-per-move`, made by
    passing 0 for the move's frame): `AIUEOS_GUEST_BROWSER_LOOP leftover=census-miss off=1 frames=8 chain=be3ab3c5`,
    classifier `:census-miss`, exit 1.
- The first run never reached the loop: the 360 s wall clock ended the boot
  at T+351 s, one line after `RESIZE_OK` (hence decision 6).
- Frame model: all eight pinned scenes reproduced (the resize frame is now
  pinned). Classifier tests 12 / 167.
