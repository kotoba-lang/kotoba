# ADR-0253 — A hot control is drawn pressed while the button is down

Date: 2026-10-23

## Status

Accepted. Closes the `:pressed-state` floor (ladder: 31 floors, 29 gated). Row C10
("interaction states and feedback") of the ChromeOS-grade scorecard
(docs/chromeos-scorecard.md) gains its pressed state.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-pressed-state`
prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_PRESSED_STATE_OK`: the cursor-shape gate is green on the
same serial and `AIUEOS_GUEST_BROWSER_MAX n=33, 34` and `AIUEOS_GUEST_BROWSER_PRESS n=33, 34`
equal the frame model's.

Not, and stated here rather than at the end: a disabled state, tooltips, a pressed
state on the dock, or the pixels (colours in the draw list).

## Decision

The pointer's button state is a fact C owns, so C writes it: surface word 2033 is 1 on a
tablet press and 0 on a release (the word the op capacity change of ADR-0248 freed).
`browser-frame2.kotoba` `ctl-rgb` draws a hot control (ADR-0246) #bfbfbf while the word is
1 -- #e6b800 in the high-contrast palette, black on which is 11:1 -- and the hot colour
otherwise; the launcher buttons, the close control and the maximize control all use it.
The kernel prints how many rects of the list it painted are in the pressed and the hot
colour; the frame model is the second statement.

Earlier frames are unchanged: no earlier stage has the button down over a control that
is still under the pointer afterwards (a press on the maximize control moves the control
away in the same event), which the unchanged gates show.
