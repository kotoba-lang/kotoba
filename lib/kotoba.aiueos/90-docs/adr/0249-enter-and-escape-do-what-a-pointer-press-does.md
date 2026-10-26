# ADR-0249 — Enter and Escape do what a pointer press does

Date: 2026-10-23

## Status

Accepted. Closes the `:keyboard-activate` floor of the ADR-0226 ladder (UIUX).
Its goal is corrected in the same change: Space shares Enter's path and is not
pressed in the gate.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-keyboard-activate`
prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_KEYBOARD_ACTIVATE_OK` (the focus-ring
boot): the key, Kotoba's answer, browser-reduce's result, the windows, focus,
stack and census of all fourteen key frames equal the frame model's.

Not, and stated here rather than at the end: Space in a boot, a menu, a
composition in progress (the input method's, as before).

## Decision

Kotoba answers Enter or Space on a ring target, and Escape for the focused
window's close control, with the pointer press it stands for -- `65536 + 2048 x
+ y`, the control's centre -- and C hands it to `kotoba_aiueos_browser_reduce`
as a pointer/down, exactly as it does for a tablet press. There is one action
path for the keyboard and the pointer; the keyboard has no second set of rules
for launching or closing. Enter and Space with a composition are the input
method's. In the boot, Enter on button 2 raises and focuses window 2
(`reduce=2`) and Escape closes it, focusing the one on top (`reduce=1`).
