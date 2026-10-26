# ADR-0246 — The control under the pointer is drawn hot

Date: 2026-10-23

## Status

Accepted. Closes the `:hover` floor of the ADR-0226 ladder (UIUX).

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-hover`
(scroll boot) prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_HOVER_OK`: the scroll gate
is green on the same serial and the thirty-four `AIUEOS_GUEST_BROWSER_HOT`
lines equal the model's `hot-frame` lines.

Not, and stated here rather than at the end: the pixels (an op count, not the
display), hover on the dock or on window bodies, a transition, a tooltip, a
focus ring.

## Context

Launcher buttons and close controls gave no sign that they take a click. The
pointer's position was already in the surface (words 2046/2047, ADR-0236) and
already drawn; nothing read it to colour a control.

## Decision

`os/aiueos/kotoba/browser-frame2.kotoba` gains `hot` (pointer inside a
control's rectangle, 1 or 0) and `button` / `close-control` colour a hot
control #d9d9d9 instead of #e6e6e6. Only a colour changes: the op count, the
ink census and every earlier pin are untouched, which the damage gate, re-run on the rebuilt object, shows: it still
prints `ops=203 text-px=2330 hash=5581e21a bytes=1870144` and requires every
earlier classifier to be green on the same serial. The object is rebuilt with
amu 74ca4aa6 (`reproduce-kotoba-objects.cljk --attest`), the shells' pins are
synced (`sync-kernel-object-digests.cljk`, stale=0).

The kernel prints, beside the cursor, focus and scroll frames, how many
rects of the list it just painted are in the hover colour. The expected counts
come from the independent frame model, which learned the same rule and the
kernel's launcher colours.

## Not a selfhost object

The object is built by `kotoba-compiler/1` through the amu launcher, like the
other 111. Rebuilding it with Amu selfhost waits on ADR 0373 (amu).
