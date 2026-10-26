# ADR-0250 — A double press on a titlebar maximizes and restores

Date: 2026-10-23

## Status

Accepted. Closes the `:window-maximize` floor of the ADR-0226 ladder (UIUX).
The floor is split in the same change: the visible maximize control and a
keyboard shortcut are `:maximize-control`, open.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-window-maximize`
prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_WINDOW_MAXIMIZE_OK`: the eight
`AIUEOS_GUEST_BROWSER_MAX` lines equal the frame model's `max-frame` lines, the
maximized rect is the work area (0, 28, 1280, 720) and the rect after the
restore is the rect before the maximize.

Not, and stated here rather than at the end: a time threshold, a maximize
control, a keyboard shortcut, a window opened with no launcher, the pixels.

## Decision

- **Kotoba decides.** In `browser-reduce.kotoba` a press on a window's titlebar
  (not its resize handle, not its close control) that follows another press on
  the same window's titlebar by at most three input events is a double press:
  the window's rect is saved in surface words 2010 + 4 (id - 1) and replaced by
  the work area (0, 28, vw, vh - 80), or, if a rect is saved, put back. The
  saved rect's width is 0 while the window is not maximized, so the saved rect
  is its own flag. Only the launcher branch and only with the whole surface
  (state size 8192) detect it; every earlier stage calls reduce with 128 and
  behaves exactly as before.
- **C reports, it does not decide.** C counts the tablet's events in word 2029
  and passes the source and position through. The double press has no clock: it
  is the order of events, which makes the gate deterministic under QEMU's
  timing and is a weaker claim than a double click in a toolkit.
- **The restore is exact** (the gate compares the rects before and after) and
  the model is the second statement of every frame.
- Objects rebuilt with amu 74ca4aa6 and attested, digests synced (stale=0); not
  Amu-selfhost objects (ADR 0373).

## Why the control is not here

Drawing a maximize control in every titlebar adds ops to every window with a
launcher: every pinned ops count and census in every stage moves again. That
is the re-green of ADR-0226's measurement, and it is its own job.
