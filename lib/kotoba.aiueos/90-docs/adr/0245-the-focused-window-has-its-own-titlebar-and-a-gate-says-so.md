# ADR-0245 — The focused window has its own titlebar, and a gate says so

Date: 2026-10-23

## Status

Accepted. Closes the `:title-active` floor of the ADR-0226 ladder (the first of
the UIUX floors added on 2026-10-22).

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-title-active`
(focus-cycle boot) prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_TITLE_ACTIVE_OK`:
the focus-cycle gate is green on the same serial and the twelve
`AIUEOS_GUEST_BROWSER_FOCUS_TITLE` lines equal the model's `title-frame` lines.

Not, and stated here rather than at the end: the pixels (the count is of ops in
the draw list, not of colours on the display), hover, an inactive body style,
contrast ratios.

## Context

`browser-frame2.kotoba` has coloured the focused window's titlebar differently
from the others since JUN-143 (`title-rgb`: #cccccc focused, #e6e6e6
otherwise). The behaviour was never asserted: the ladder floor was added as
missing and corrected to "behaviour exists, gate missing" (ADR-0226, PR 442).

## Decision

No Kotoba object changes. The kernel's focus stage (C) scans the draw list it
has just painted for rects of height 28 and counts them by `title-rgb`'s two
colours, printing the counts and the position of the first focused one. The
expected values come from the independent frame model, which counts them in
its own op list. The classifier is registered in
`src/aiueos/compositor/guest.cljk`, rides the focus-cycle boot, and is
unit-tested including four red cases.
