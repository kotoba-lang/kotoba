# ADR-0252 — The pointer is a resize cursor over the handle

Date: 2026-10-23

## Status

Accepted. Closes the `:cursor-shape` floor, added to the ADR-0226 ladder in the
same change (30 floors; 28 gated).

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-cursor-shape`
prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_CURSOR_SHAPE_OK`: the maximize-control gate
is green on the same serial, `AIUEOS_GUEST_BROWSER_MAX n=31, 32` equal the frame
model's, and the arrow at (380, 142) after the handle equals frame 19 in ops,
ink pixels and hash.

Not, and stated here rather than at the end: other cursor shapes (text, hand,
move), the pixels, a hotspot tuned per shape.

## Context

The pointer was one arrow (ADR-0236) wherever it was. A window's resize
handle -- the last 16 px of both axes, which browser-reduce already tests -- gave
no sign that it could be dragged. The ladder's UIUX floors stopped at what a
keyboard and a pointer can do; this is the first of the "feedback" kind the
ADR-0226 scorecard note lists as missing.

## Decision

`browser-frame2.kotoba` decides from the surface alone, with browser-reduce's
own rule: the topmost window containing the pointer (inclusive bounds), and the
pointer in the last 16 px of both its axes. Over it, with 6 px of room on every
side, the pointer is a 2 x 2 diagonal with an L at each end in the ink (14 ops)
instead of the arrow (21). The frame model learned the same rule and the kernel
prints what it paints; the gate also requires that the arrow comes back
byte-for-byte (the same ops, ink pixels and hash as the frame with the same
pointer position before it moved).

The ink census of every earlier stage is untouched: none of their pointer
positions is on a handle, which the model's pinned scenes and the unchanged
gates show.

## What was not done

The scorecard the owner has not fixed (JUN-90) would say what 100% is. The
missing items are listed in the floors file's comment, not claimed.
