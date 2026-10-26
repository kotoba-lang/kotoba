# ADR-0248 — F6 moves a focus ring over the launcher

Date: 2026-10-23

## Status

Accepted. Closes the `:focus-ring` floor of the ADR-0226 ladder (UIUX). The
floor's goal is corrected in the same change (below).

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-focus-ring`
prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_FOCUS_RING_OK`: the keyboard stage's
`AIUEOS_GUEST_BROWSER_KEYS_OK` and the fourteen `AIUEOS_GUEST_BROWSER_KEY` lines
equal the frame model's `key-frame` lines in ring, ring rect count, position,
colours and census, and the contrast of the ring colour against the launcher
bar and the button, computed by the classifier from the printed colours, is at
least 3:1.

Not, and stated here rather than at the end: Tab, the ring on window bodies or
the dock, the close control as a ring target in a boot (target 5 exists in
Kotoba and the gate's boot does not move onto it), the pixels.

## Context

The floor said "Tab / Shift+Tab move it in document order". Tab is taken: Alt+Tab
is the window switcher (ADR-0237) and a lone Tab is the input method's, whose
pins (the last two focus-cycle frames) must not change. F6 -- the browsers' key
for moving focus between the parts of a page -- is free.

## Decision

- **Kotoba decides.** `browser-ime.kotoba` `ring-move` moves surface word 2032
  forward through the targets that exist (button k when app k is registered;
  the focused window's close control when the window is at least 40 wide and
  there is an app register) and then off, or backward when Shift (word 2035) is
  held. It answers 0. `browser-frame2.kotoba` draws the ring, four 2 px rects
  outside the control, #1a56db (black in the high-contrast palette), after the
  control so it is over it.
- **Word 2032 is made free** by lowering the op capacity from 259 to 255 (the
  largest frame in any gate is 207 ops); words 2010..2033 are no longer ops.
- **The ring's contrast is arithmetic**: 5.5:1 against the launcher bar, 5.0:1
  against a button, 4.4:1 against a hot one; the classifier is red below 3:1
  whatever the list says.
- The keyboard stage (ADR-0247) gains the events; the model is the second,
  independent statement of every frame.
- Objects rebuilt with amu 74ca4aa6 and attested, digests synced (stale=0); not
  Amu-selfhost objects (ADR 0373).
