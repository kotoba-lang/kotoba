# ADR-0257 — The close control of the only visible window is disabled

Date: 2026-10-23

## Status

Accepted. Extends the `:minimize` gate (ten more events, `guest-browser-minimize` now 26 events after
the launcher press); it adds no floor. Row C10 ("interaction states and feedback") of the ChromeOS-grade
scorecard gains a disabled state in its QEMU-level evidence; it stays `:partial` (no tooltips).

**Green only when** `guest-browser-minimize` prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_MINIMIZE_OK`: besides
the earlier events, `AIUEOS_GUEST_BROWSER_MAX n=51..60` and `AIUEOS_GUEST_BROWSER_MIN n=35..60` (now with
`dis=`) equal the frame model's.

Not: disabled launcher buttons, a disabled maximize control, tooltips, a reason shown to the user.

## Decision

browser-reduce refuses to close a window when no other window would stay visible (-8; ADR-0233, ADR-0254),
and the control still looked live. `browser-frame2.kotoba` now draws the close control of a window
whose stack has fewer than two visible windows as disabled: the plain face (never hot, never pressed, even
under the pointer) and a glyph in #9e9e9e (#707070 in the high-contrast palette) instead of the ink. The
frame model states the same rule independently. No earlier frame has a single visible window with a
launcher, so no earlier pin moved (the model's old and new output differ only in the new events).

## Measured

Events 51..60: window 1 and then window 4 (its own control at (544, 94)) are minimized, window 3 is alone
and its close control is disabled (`dis=1`, the glyph count in the disabled colour); a press on it at (584, 94)
is refused (`reduce=refused`, frame unchanged but for the pointer); two presses on the tray button (60, 780)
restore window 1 and window 4 (`dis=0`).

## Still open

Tooltips, a disabled look for other controls, and the pixels (the gate reads the draw list).
