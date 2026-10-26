# ADR-0262 — Every shell control is reachable and activatable from the keyboard

Date: 2026-10-23

## Status

Accepted. Extends ADR-0248 (the focus ring and keyboard activation) and adds the `guest-browser-keyboard-only` gate;
no new floor. Row I8 ("Everything reachable by keyboard alone") of the ChromeOS-grade scorecard has its procedure run
end to end in the reference VM.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-keyboard-only`
prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_KEYBOARD_ONLY_OK`: the sign-out gate is green on the same serial, the
twenty-six `AIUEOS_GUEST_BROWSER_RING` lines equal the frame model's, every event is a keyboard event, the ring stood
on each control 1 .. 8, and each Enter did its action: a window opened, the top window filled the work area, a window
was minimized, the same window came back focused.

Not, and stated here rather than at the end: window contents (a document is text, with nothing to focus), moving and
resizing a window by key (no control in the shell does that), the dock's icons (they restore a minimized app, which the
tray's button of the same window already does), and the pixels.

## Decision

ADR-0248 gave the ring five targets (launcher buttons 1..4, the focused window's close control). It now has eleven:
6 is the focused window's maximize control, 7 its minimize control, and 8..11 the tray's buttons by window id. F6 and
Shift+F6 move through the targets that exist; Enter or Space presses the one the ring is on, as the pointer press at its
centre that Kotoba answers and C hands to browser-reduce, so the keyboard and the pointer stay one action path.

- `browser-ime.kotoba`: `target-ok` knows the three new kinds (`max-exists`, `min-exists`, `tray-count`); `ring-press`
  answers the maximize control's, the minimize control's (x + w - 56, y + 14) and the tray's (66 + 126 i, vh - 18)
  centres. `min-key-ok` (Alt+-) now asks `min-exists` too.
- `browser-frame2.kotoba`: a ring on the focused window's maximize and minimize controls and on the tray's buttons.
- The frame model states the same rings independently.

## Measured

Twenty-six keys: F6 F6 (ring on launcher 1, 2), Enter (window 2 opens); F6 four times (launcher 3, 4, window 2's close,
maximize); Enter (maximized: 0, 28, 1280, 720); F6 (minimize) and Enter (window 2 minimized, focus 1); F6 (the tray's
button for window 2) and Enter (restored, focused, maximized); F6 (no control further on: the ring is put away).

## Still open

A way to move and resize a window by key, a focus order inside a window once it holds controls (a form, a link), and
the pixels.
