# ADR-0233 — A launcher opens a window, and a close control closes it

Date: 2026-09-25

## Status

Accepted. Closes the `:launch-close` floor of the ADR-0226 ladder.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-launch`
(`AIUEOS_GUEST_BROWSER=1`, `AIUEOS_QEMU_TIMEOUT=840`) prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_LAUNCH_OK`: after ADR-0232's caret (window 2
focused, stack [1 2]), the shell registers apps 1 2 3 and the host sends
eight virtio-tablet batches, each after the previous frame line -- a press on
launcher button 3 at (258, 14), release, a press on window 3's close control
at (584, 94), release, the launcher again, release, a press on window 2's
close control at (820, 186), release. Serial: eight
`AIUEOS_GUEST_BROWSER_LAUNCH_FRAME n=<1..8> ...` lines and
`AIUEOS_GUEST_BROWSER_LAUNCH_OK events=8 answers=30203030 windows=2 stack=1,3 focus=3 chain=cff6ae89 ops=85 text-px=776 hash=9e714452`.

Not: a second window of an app whose window is open
(`:one-window-per-app`), a desktop with no window (`:the-last-window-stays`),
or apps beyond the four window slots (`:no-app-registry-beyond-the-slots`).

## Decision

1. **What launch and close do is browser.surface's; where they are is the
   kernel's.** kotoba-lang/browser has the actions -- `launch-app` (open-window
   with the app's title and document at its default rect, or open-window's
   `[80 80 520 360]`; on top; focused) and `close-window` (the window leaves
   `:surface/windows`; if it had the focus, the focus goes to the last
   remaining window) -- but no geometry for them: its launcher is a DOM row
   cssom lays out, and its `window-node` has no close control at all. The
   kernel has no flow layout (`:no-flow-layout`), so it places them itself,
   and says so: the launcher row is (0, 0, vw, 28), button k is
   (6 + 102(k-1), 2, 96, 24), and a window's close control is
   (x + w - 24, y + 6, 16, 16), only on windows at least 40 wide.
2. **The app register is word 31.** It was the one word of the 128-byte
   reducer state nothing read. Bit k-1 set = app k registered; app k's title
   and document are window slot k's title and body, so a launched app's
   window id is its slot and nothing is copied. With word 31 = 0 -- every
   earlier gate and every earlier contract vector -- nothing below is drawn
   or hit: no frame before this gate changed, and none was re-pinned.
3. **browser-frame2 draws the chrome.** With a register: the launcher row
   (#edf0f5, browser.surface `.launcher`'s background) and the registered
   apps' buttons (#e4e8ef, the theme's `:button-bg`, title at (x + 6, 6),
   one line, clipped at x + 90) right after the background, so every window
   is over them; and after each title, the close control (#e4e8ef) with
   U+00D7 centred on it in the text colour. The title then clips at
   x + w - 28 instead of x + w - 8. New reason -9: a register with a bit past
   app 4. The caret is still the last op.
4. **browser-reduce decides the press.** With a register, a press that hits
   a window (topmost first, as before) inside its close control closes it --
   no raise, no capture -- and answers the focused window id after the close.
   A press that hits no window inside a registered app's launcher button
   launches it and answers its window id. Both clear the capture (a press on
   the chrome ends a gesture, and a capture of a closed window would be
   refused as -4). Every other press is what it was.
5. **Named differences from the oracle.** A launch of an app whose window is
   open raises and focuses that window (the oracle opens a second one; a slot
   holds one). A close of the last window is refused, -8 (the oracle leaves
   an empty surface; frame2 and the reducers admit 1..4 windows). A launch
   whose default rect leaves the viewport is refused, -9. A register with a
   bit past app 4 is refused, -7.
6. **Expected answers come from the oracle.**
   `os/aiueos/scripts/browser-reduce-oracle.cljk` writes the geometry above
   apart from the object and applies browser.surface's own `:app/launch`,
   `:window/close` and `:window/focus` actions; it prints the 26 new success
   vectors of browser-reduce-v1 (seed, answer, whole state after) and
   `--check` compares all 66 with the contract. The four new browser-frame2-v1
   success vectors and the gate's eight censuses come from
   `os/aiueos/scripts/browser-frame-model.cljk`, which draws the chrome from
   this ADR's rules, not from the object.
7. **C decides nothing.** At LAUNCH_GO C writes slot 3's title and body and
   word 31 (the shell registering its apps), drains the tablet ring, and then
   hands each batch to `kotoba_aiueos_browser_reduce` and presents
   `kotoba_aiueos_browser_frame2`'s list after it, as the event loop does. It
   compares answers 3 0 2 0 3 0 3 0, window counts 3 3 2 2 3 3 2 2 and op
   counts 106 106 88 88 106 106 85 85 with the vectors and the model, folds
   the censuses into a chain, and reads the final stack.
8. **No new rows.** browser-reduce passes its contract at fuel 96 and traps
   at 64 (1,024 default tier); browser-frame2 passes at 16,384 and traps at
   12,288 (tier 262,144). No kotoba-native row or amu pin changes.

![window 3 launched from the launcher over windows 1 and 2 (display)](../../docs/assets/guest-browser-launch.png)

## Measurement

**2026-09-25, this Mac, QEMU tcg + OVMF.**

- `guest-browser-launch` (first run): `AIUEOS_COMPOSITOR_GUEST_BROWSER_LAUNCH_OK`,
  leftover `[:one-window-per-app :the-last-window-stays :no-app-registry-beyond-the-slots]`.
  `LAUNCH_FRAME` 1..8: answers 3 0 2 0 3 0 3 0, windows 3 3 2 2 3 3 2 2,
  focus 3 3 2 2 3 3 3 3, ops 106 106 88 88 106 106 85 85, censuses
  786 / e7260a1d, 1183 / 575aafc8, 776 / 9e714452 -- each the model's -- and
  `AIUEOS_GUEST_BROWSER_LAUNCH_OK events=8 answers=30203030 windows=2 stack=1,3 focus=3 chain=cff6ae89 ops=85 text-px=776 hash=9e714452`.
  Every earlier guest browser line in the same boot is unchanged (TEXT_OK
  58 / 1100 / 4ab25516 through CARET_OK chain fba4ae02): the register is 0
  until LAUNCH_GO.
- Display: `guest-browser-launch-1.ppm` .. `-7.ppm` and `guest-browser-launch.ppm`
  count 786, 786, 1183, 1183, 786, 786, 776, 776 #111111 px -- the memory
  census, frame by frame; the launcher row is #edf0f5 and button 3 #e4e8ef on
  every one, and the caret-gate dump before them has neither.
- Default profile (no tablet): `guest-browser-text` green with
  `FRAME_OK ops=5` and `TEXT_OK ops=58 text-px=1100 hash=4ab25516`
  unchanged, and no LOOP, CARET or LAUNCH line.
- Contracts (verify-admissions, no JVM): browser-reduce-v1 77 vectors, 66
  memory assertions, reasons -9..-1 all observed; the oracle check
  `COMPARED 66`, exit 0. browser-frame2-v1 35 vectors, 19 memory assertions,
  reasons -9..-1; its 30 earlier vectors pass unchanged. Seen red, each on
  its named vector: a close that does not move the focus ->
  `a-close-of-the-focused-window-focuses-the-top`; the close control's right
  edge exclusive -> `the-close-control-bottom-right-is-inclusive`; a launch
  that keeps the capture -> `a-launch-clears-a-capture` (memory); a title
  not clipped before the close control ->
  `close-control-in-each-window-and-the-title-clips-before-it`; the launcher
  drawn over the windows -> `launcher-row-and-buttons-under-the-windows`.
- Fuel: browser-reduce passes at 96, traps at 64; browser-frame2 passes at
  16,384, traps at 12,288.
- Objects compiled with amu main f0a4316e: browser-reduce.o e4b1bfaf (10,088
  B), browser-frame2.o fa293e12 (11,368 B), reproduce match=2, digests
  stale=0.
- Frame model: the eight pinned scenes and the loop / caret chains reproduced;
  classifier tests 14 / 193.
