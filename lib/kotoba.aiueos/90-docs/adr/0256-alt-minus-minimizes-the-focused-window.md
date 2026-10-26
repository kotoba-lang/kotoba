# ADR-0256 — Alt+- minimizes the focused window

Date: 2026-10-23

## Status

Accepted. Extends the `:minimize` floor (ADR-0254, ADR-0255; same gate `guest-browser-minimize`, now
sixteen events); it adds no floor. Removes "no keyboard minimize" from the leftovers; scorecard C5
stays `:partial`.

**Green only when** `guest-browser-minimize` prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_MINIMIZE_OK`:
besides the earlier events, `AIUEOS_GUEST_BROWSER_MAX n=45..50` and `AIUEOS_GUEST_BROWSER_MIN n=45..50`
equal the frame model's.

Not: other shortcuts (the reference has a few more), minimizing a window with no control (a window under
200 wide, or the only visible one), the pixels.

## Decision

The keyboard and the pointer are one action path (ADR-0248): Kotoba's key object answers the
press a pointer would make and C hands it to browser-reduce. `browser-ime.kotoba` `min-key-ok` is true
when Alt is held, the key is `-` (evdev 12), there is an app register, the focused window is at least 200
wide and two or more windows are visible -- exactly when the control exists -- and the answer is the press at
the control's centre, 65536 + 2048 (x + w - 56) + (y + 14); browser-reduce does the rest (ADR-0254). When the
control does not exist the key is not taken, and `-` is typed as it was.

## Measured

Events 45..50: Alt down (no change), `-` down (answer 999570, reduce 4, window 1 minimized, focus 4, 140 ops),
`-` up, Alt up (no change), then a press on the tray button at (60, 780) and its release (window 1 back, 192
ops). The gate reads the draw list; the pointer stays at (60, 780) throughout, so the keyboard alone moved the state.
