# ADR-0261 — The UI scale is chosen by Kotoba and magnified by C

Date: 2026-10-23

## Status

Accepted. Adds the `guest-browser-ui-scale` gate; no new floor. Row I7 ("Text and UI scaling for low vision") of the
ChromeOS-grade scorecard gains its QEMU-level evidence; see the scorecard for whether it passes.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-ui-scale` prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_UI_SCALE_OK`: the sign-out gate is green on the same serial, the sixteen
`AIUEOS_GUEST_BROWSER_SCALE` lines equal the frame model's, the window is inside the logical viewport in every
frame, the scale never leaves 100..150, the ink census grows from 100 to 150, and back at 100 and restored the
window is the rect it had.

Not, and stated here rather than at the end: a scale above 150 (the default window needs a 600 x 440 viewport, so
200% cannot lay out on 1280 x 800), a scale that is kept across a reboot (ADR-0260 persists the contrast only),
smoothing (the magnification is nearest-neighbour), a fractional-DPI font, or the pixels of a panel.

## Decision

Scale is policy and magnification is mechanism, as with the lock (ADR-0258).

- `browser-ime.kotoba`: Ctrl+= and Ctrl+- (evdev 13 and 12, Alt not held) step the scale 100, 125, 150 and back;
  word 2009 holds it (0 means 100). The step is the key's answer, `200000000 + percent`, for C. After C has set the
  viewport, a value-2 key event with code 3 makes `fit-windows` move every window into it: width and height capped
  at the viewport (below the 28 px launcher row), then the origin pulled back inside.
- `kernel/framebuffer.c`: `aiueos_desktop_set_scale` and the scaled paint of `aiueos_desktop_present_ops2`. A rect
  covers [x s / 100, ceil ((x + w) s / 100)) on each axis and each set bit of a glyph is the block of the same
  rule, so no seam shows and the last logical column reaches the physical edge. At 100 the path is the old one.
- `kernel/main.c` `browser_scale_stage`: sets the logical viewport (surface words 3 and 4 = physical size over the
  scale), which the tablet's mapping and Kotoba's layout and rect checks already read.
- `browser-frame2.kotoba`: the op capacity is 254, not 255, to free words 2004..2009 (2009 is the scale).
- The frame model paints the scale the way the present does (`scale-ops`) and counts the same census.

## Measured

Sixteen keys on the clean session: maximized (0, 28, 1280, 720); 125% (viewport 1024 x 640, the window fitted to
0, 28, 1024, 612); 150% (853 x 533, 0, 28, 853, 505; 582 ink pixels become 1828); a third Ctrl+= changes nothing;
125% and 100% (the window stays where the fit left it); F11 restores 80, 80, 520, 360.

## Still open

Persisting the scale with the contrast (a record v2), a settings window to choose it, and 175/200% (a smaller
default window).
