# ADR-0251 — A maximize control, and F11

Date: 2026-10-23

## Status

Accepted. Closes the `:maximize-control` floor of the ADR-0226 ladder (UIUX),
split from `:window-maximize` (ADR-0250).

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-maximize-control`
prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_MAXIMIZE_CONTROL_OK`: the double-press
gate is green on the same serial and the four `AIUEOS_GUEST_BROWSER_MAX`
lines 27..30 equal the frame model's, the first window being the work area
(0, 28, 1280, 720) and the one after F11 the rect it had before the press.

Not, and stated here rather than at the end: a control on windows narrower than
160 or without a launcher, a ring target for the control, the pixels.

## Decision

- **Kotoba draws and decides.** `browser-frame2.kotoba` `max-control` draws a
  16 x 16 face (hot under the pointer) and U+25A1 left of the close control, on
  a window with a launcher at least 160 wide; its title is clipped 20 px
  earlier there. `browser-reduce.kotoba` `in-max` takes a press inside it, with
  the whole surface, as the maximize toggle (ADR-0250's `toggle-max`).
- **F11 is the same press.** `browser-ime.kotoba` answers F11 with the pointer
  press at the focused window's control centre (65536 + 2048 x + y), exactly
  as it answers Enter and Escape (ADR-0249); C hands it to browser-reduce as a
  pointer/down. The keyboard has no second set of rules.
- **The icon is not the ink.** U+25A1 is drawn in #595959 (#404040 in the
  high-contrast palette), so the ink census of every frame is unchanged and the
  re-derivation of the pins is ops counts only.
- **Re-green again.** Every frame with a launcher gained two ops per such
  window; the model re-derived every `ops=` (strings, arrays, scalars, the
  classifier's rows, the tests' rows) and the whole chain was re-run: every
  gate that reads the serial is exit 0 on the new boot.
- A bug the first run found: the key-answered press was handed to browser-reduce
  with the 128-byte state; the maximize toggle needs the whole surface (8192).
  The pointer's path and the keyboard's now pass the same argument.
- Objects rebuilt with amu 74ca4aa6 and attested, digests synced (stale=0); not
  Amu-selfhost objects (ADR 0373).
