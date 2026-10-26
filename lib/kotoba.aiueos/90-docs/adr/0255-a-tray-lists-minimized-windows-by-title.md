# ADR-0255 — A tray lists minimized windows by title and restores them

Date: 2026-10-23

## Status

Accepted. Extends the `:minimize` floor (ADR-0254, same gate `guest-browser-minimize`, now ten
events); it adds no floor. Row C5 ("Minimize, and a list of open windows") of the ChromeOS-grade
scorecard stays `:partial` in the QEMU-level progress: the list below holds minimized windows only.

**Green only when** `guest-browser-minimize` prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_MINIMIZE_OK`:
besides ADR-0254's six events, `AIUEOS_GUEST_BROWSER_MAX n=41..44` and `AIUEOS_GUEST_BROWSER_MIN n=35..44`
(now with `tray=`) equal the frame model's, and the frame after the tray restore has the op count the
frame before the second minimize had.

Not, and stated here rather than at the end: a list of every open window (a visible window has no
entry), a preview, a close button in the list, an order other than window id, animation.

## Decision

While at least one window is minimized, `browser-frame2.kotoba` draws one 120 x 24 button per
minimized window, by id, at (6 + 126 i, vh - 30), bottom left (the dock is centred, so they never
meet), with the window's title (the launcher's title slot) in the ink, clipped at x + 114; the face
is hot and pressed like every control. `browser-reduce.kotoba` `tray-at` finds the button under a
press (inclusive) and restores that window as the dock icon does: bit cleared, window raised and
focused. The tray is tried after the dock and before any window, so it wins like the dock does.

With no minimized window nothing is drawn, so no frame outside the minimized states changes (the
unchanged pins of ADR-0254 show it).

## Measured

Events 41..44: window 1 is minimized again (140 ops: the frame with the tray, against 192), and a
press on the tray button at (60, 780) restores it (192 ops, focus 1, stack 341); kernel and model
agree on the tray count (`tray=1` while minimized, 0 after).

## Still open

A list that also shows the visible windows (a real window list / shelf), reordering, middle-click
close, and the draw list is read, not the pixels.
