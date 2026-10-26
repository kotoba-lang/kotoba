# ADR-0247 — F10 switches the desktop to a high-contrast palette

Date: 2026-10-23

## Status

Accepted. Closes the `:high-contrast` floor of the ADR-0226 ladder (UIUX).

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-high-contrast`
prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_HIGH_CONTRAST_OK`: the damage stage's OK
line, the stage's `AIUEOS_GUEST_BROWSER_UIUX_OK` and four
`AIUEOS_GUEST_BROWSER_HC` lines equal to the frame model's, with the ink's WCAG
contrast against the background, the white body and every bar at least 7:1 in
the frames where the palette is on.

Not, and stated here rather than at the end: the pixels (colours in the draw
list), the dock (it keeps its colours), persistence across boots, a
system-wide setting, or "the first AAA": the default palette is already above
7:1 (#333333 on #cccccc is 7.9:1). What this adds is a larger margin, a black
ink and a way to ask for it from the keyboard.

## Context

The floor read "a keyboard toggle switches the desktop between the default and
a high-contrast palette (text/background contrast >= 7:1), chosen by Kotoba,
with the choice kept across frames". The hosted shell follows design tokens;
the kernel desktop had one fixed palette.

## Decision

- **Kotoba decides.** `browser-ime.kotoba` `press` takes F10 (evdev 68, key
  down) as `hc-toggle`: it flips surface word 2039, the surface's last
  unassigned word, and answers 0. `browser-frame2.kotoba` reads the word in
  `hc`, `ink`, `bg-rgb`, `face-rgb`, `hot-rgb`, `shadow-rgb` and `title-rgb`.
  The choice lives in the surface, so it is kept across frames.
- **A new stage after the damage stage** (`browser_uiux_stage`, C): four key
  events, a frame for each, and for each frame what the kernel reads out of the
  draw list it painted. The host injects the events one at a time after the
  kernel's line for the one before. The stage is the place the other UIUX
  floors' keyboard events will join.
- **The contrast is arithmetic, not a list.** The classifier computes the WCAG 2
  ratio from the printed colours; a palette whose ratio is below 7:1 is red
  whatever the list says, and the frame model is the second, independent
  statement of the colours.
- Both objects are rebuilt with amu 74ca4aa6 (`reproduce-kotoba-objects.cljk
  --attest`) and the shells' pins synced (stale=0). They are not Amu-selfhost
  objects (ADR 0373).
