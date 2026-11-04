# ADR-0285 — Apps beyond the four window slots: a window slot is not an app id

Date: 2026-11-04

## Status

Proposed (JUN-811, under JUN-805). Nothing in this ADR is implemented. It closes the leftover named
`:no-app-registry-beyond-the-slots` in ADR-0233 and replaces the "paged grid, pinned dock" outline in decision 2 of
ADR-0283 with concrete rules. It does not touch ADR-0282 (dapps run offline) or ADR-0284 (user-signed install).

## Context

The native desktop lists four apps and cannot list more. Measured in the source (main, 2026-11-04):

- The surface is exactly 8192 bytes (2048 words) and is fully allocated (`aiueos/browser_frame2.kotoba` header, lines
  55-125): words 0..31 state (5 header words, then `id x y w h` per window), 32+32(id-1) titles, 160+64(id-1) bodies
  (to 415), 416..479 scratch and the input method, 480..2033 draw ops (259 x 6), 2034..2047 flags, 2040..2043
  per-window scroll and the pointer. Words 416..430 are frame2's scratch and 432..479 the input method's state
  (`browser-ime.kotoba` uses 442 converting, 443 candidate index, 444 record offset, 478 overflow, 479 dictionary bytes),
  so none of those is free. The only unused words are 25..29: they are the object-route reducer's pointer-capture
  words (25 kind, 26 window, 27-29 offsets), and `desktop.kotoba` neither reads nor writes them (no `s 25`..`s 29`
  access; the desktop does not use `browser-reduce`).
- A window id is also the app id and the title/body slot (ADR-0233 decision 2: "a launched app's window id is its
  slot and nothing is copied"). The app register (word 31) has one bit per app, and a bit past app 4 is refused
  (frame2 reason -9). `desktop.kotoba` hit-tests the launcher, dock and home grid for ids 1..4, and refuses a launch
  when four windows are open.
- The browser side has no such limit: `browser.surface` lays the launcher out as a DOM row and `launch-app` opens a
  window carrying the app's title and document. The limit is a native constraint ("Temporary native constraints",
  ADR-0223), not a Browser contract.
- The desktop kernel is within a few KiB of the compiler's 2 MiB code cap. After #1192 (packed catalog) and #1194
  (receipt `textMargin`) the estimated margin is about 13.7 KiB. A 17-app packed catalog compiled under the cap
  as an experiment, so catalog text is not the limit; the surface layout is.
- `native/desktop.kotoba` does not use `browser-reduce.kotoba`; it has its own launch and press logic. `browser-reduce`,
  `browser-ime` and `kotoba/browser-frame2.kotoba` ship as object-route `.o` files (kernel-v1 target) for the C-driven
  `guest-browser-*` gates, each with a provenance record. `aiueos/browser_frame2.kotoba` is the copy the desktop
  kernel imports.

## Decision

1. **A window id stays a slot id (1..4); only the slot-to-app mapping is new.** Every rule keyed by window id today
   (z-order, focus, minimize, tray, Alt+Tab, scroll words 2040..2043, title and body slots, resize and drag) is
   unchanged. A window record's `id` is the slot. Four words hold the app shown in each slot (`slot-app`), in words
   25..28, and word 29 holds the launcher page. Nothing else in the map moves, and the 259-op budget is unchanged.
   Those five words are free only in the desktop kernel: the frozen object-route reducer (decision 8) still uses
   them for pointer capture, which is why that copy must never run against the desktop's surface. Before the first change lands, a
   canary build (words 25..29 pre-filled, frames and gates compared with the plain build) must show nothing in the
   desktop reads or writes them; the grep above does not rule out computed indices.
2. **Launching app A.** If a slot already shows A, that window is raised and focused (one window per app, as now).
   Otherwise a slot is chosen: the slot equal to A when A <= 4 and that slot is free (this keeps today's behavior for
   apps 1..4), else the lowest free slot. A is copied from the catalog into that slot's title and body, `slot-app` is
   set, and the window opens at the default cascade rect. If no slot is free the launch is refused, as it is today
   with four windows open. A slot is free when it has no open window.
3. **Slot reuse never destroys user text.** Slot 2's body holds the RAM-only Itonami goal draft (word 2038 is its
   length), so a free slot whose app has live user text is not a candidate for reuse. If every free slot is protected
   the launch is refused. (Open question 1.)
4. **The launcher row is paged.** `perPage = clamp((vw - 62) / 102, 1, 8)`; page p shows apps `p*perPage+1 ..`. Button j
   keeps today's geometry `(6 + 102j, 2, 96, 24)`. When the app count N exceeds perPage the row also draws two
   arrow buttons, `(vw - 58, 2, 24, 24)` ("<") and `(vw - 30, 2, 24, 24)` (">"), in the button colour. N is read from the
   catalog (`app-count`), not from the register. For N = 4 and any viewport at least 470 wide, perPage >= 4 so no arrow
   is drawn and page 0 is today's row exactly.
5. **Keyboard.** Digits 1..perPage launch the k-th app of the current page (digits 1..4 on page 0 are unchanged);
   PageUp and PageDown change the page. This keeps every control keyboard-reachable (ADR-0262). The mouse hits the
   same buttons and arrows.
6. **Dock and home grid are unchanged.** The dock keeps its four icons for apps 1..4 and the home grid its four cards;
   apps 5 and up are reached through the launcher. Pinning other apps to the dock is a follow-up with its own storage.
7. **Register.** Word 31 stays "launcher present when not 0". In the desktop copy of frame2 the "bit past app 4"
   refusal (-9) becomes "bit past the catalog's app count". Which apps exist comes from the catalog, not from bits.
8. **Two frame2 copies diverge on purpose.** `aiueos/browser_frame2.kotoba` (imported by the kernel) gains decisions
   1-7, reading titles from `aiueos.session.app-catalog`. The object-route copies (`kotoba/browser-frame2.kotoba`,
   `browser-reduce`, `browser-ime`) stay at the four-app ABI: they are not rebuilt, their provenance records stay
   true, and their header says so. They can only drift from the desktop copy in the paged launcher.
9. **Catalog.** `app_catalog.json` grows to the 17 apps of `distributions/awai/dapps/*.json`. Titles equal the dapp
   record titles; text is 7-bit ASCII (the generator refuses anything else), so titles and bodies are English. A body is
   the dapp's one-line state, so apps without a native core show their real state (not connected, planned).

## Gates (each lands with the change that needs it)

- **Parity (must stay green):** with a four-app catalog and page 0 the desktop build and every existing native QEMU
  gate (input, material, effects, consent, draft restart) pass unchanged. No existing gate is re-pinned.
- **New gate `check-native-launcher-pages-qemu.py`**, on a build with the 17-app catalog: arrows appear, PageDown shows
  page 1, a digit launches app 9 into a free slot with its title drawn, a second launch of app 9 raises it, a launch
  with four windows open is refused, the slot-2 draft survives opening and closing other apps. Observed through the
  same framebuffer/QMP readback the other native gates use. Each behavior has a negative control.
- **Receipt margin:** `textMargin` must stay at least 8 KiB (its warning threshold) after the change. The budget for
  this ADR is therefore about 5 KiB of kernel code; exceeding it stops the work for a decision, it does not move the
  threshold.
- **Catalog freshness:** `gen-app-catalog.py check` (exists). A check that catalog titles equal the dapp record titles.

## Order of work

frame2 desktop copy (slot-app, paging, arrows) -> `desktop.kotoba` launch and hit-tests, digits and PageUp/PageDown ->
catalog to 17 apps -> new gate. Parity is checked after the first step and after each later one.

## Not decided here

The signed variable-length catalog (JUN-811 option B, `app-catalog.sig`), dock pinning, the installer and update manager
screens, and the native render of dapp HTML/CSS (JUN-810) are separate. The hosted session is unaffected: it already
lists all 17 apps.

## Open questions (owner)

1. **Draft protection.** Is "never reuse a slot whose app has live user text, else refuse the launch" acceptable, or
   should the launch evict and the draft move to a dedicated store first? The draft is RAM-only today.
2. **perPage.** Is `clamp((vw - 62) / 102, 1, 8)` right, or should the page size be fixed at 4 (17 apps = 5 pages, no
   viewport dependence)?
3. **Frozen object copies.** Is it acceptable that the C-driven `guest-browser-*` object copies stay four-app, given
   they are not part of the current native qualification?

## Consequences

- With four apps and page 0 nothing changes on screen, which is the check that the change is safe.
- Apps 5..17 get native windows that show their catalog title and state. They run no dapp core: a dapp core is a
  separate piece of work per app (ADR-0283).
- The frame ABI gains five words of state in words 25..29, which only the frozen object-route reducer used. The ops
  budget and every other word keep their place. A future change that needs more surface words has none to take
  without shrinking the op budget.
- Four windows remain the maximum open at once. More than four would need surface space that does not exist.
