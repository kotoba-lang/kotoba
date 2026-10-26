# ADR-0226 — The guest desktop has a maturity ladder, and a loop that climbs it

Date: 2026-09-24

## Status

Accepted.

## Goal

**kotoba-lang/browser's surface is the aiueos desktop you can use on
KERNEL.ELF** -- seen on the display, driven by pointer and keyboard in one
running event loop, laid out as browser lays it out -- **and then the browser
component itself runs there.** ADR-0223..0225 are the first five rungs.

## Decision

1. **The ladder is data**: `os/aiueos/contracts/desktop-maturity-floors.edn`,
   one floor per rung, in the order they are taken. A floor is **closed only
   by its gate** -- a `scripts/compositor-guest.cljk` profile that is both
   registered in `src/aiueos/compositor/guest.cljk` and described by a
   "`<gate>` exit 0 means ..." paragraph in README.md on `origin/main`.
   A floor without a gate is never counted as closed. `:needs-a-human`
   floors (a dictionary licence, a physical machine) are reported, not taken.
2. **Maturity is measured, not asserted**: closed floors / all floors, read
   from `origin/main` by the superproject tick `scripts/aiueos-desktop-tick.cljk`
   (ledger `~/.itonami/aiueos-desktop-tick.ledger.edn`).
3. **A loop climbs it one floor per iteration**: LaunchAgent
   `cloud.itonami.bot.aiueos-desktop` runs `scripts/aiueos-desktop-loop.cljk`,
   which asks the tick for the next open floor and only then starts
   `claude -p "/aiueos-desktop"` through `scripts/loop/claude_run.cljk`. The
   skill `aiueos-desktop` is the iteration's runbook: worktree from
   `origin/main`, Kotoba object for the decision and C for mechanism, KIR
   oracle contract whose expected values come from kotoba-lang/browser or
   an independent model, a deliberate break seen red, a QEMU gate, landing
   (kotoba-native row -> amu pin via PR -> aiueos), west pins, cleanup.
4. **The ladder may be corrected** by an iteration (split a floor that is two
   jobs, reorder when one depends on another) -- in the same commit, with the
   reason.

## Consequences

Progress on the desktop is one number with a reproducible source, and each
step lands with its own gate. What the ladder does not contain is not
claimed: P5 and the dictionary stay open until a person acts.

## Ladder changes

- **2026-09-25, extended to 22 floors.** With 13 of 16 closed and the rest
  blocked or waiting on a person, the owner asked to continue: six browser
  behaviours the kernel desktop lacks were added (pointer cursor, focus
  cycle, scroll, selection, clipboard through the broker, damage-only
  present). Maturity went from 13/16 to 13/22 by the denominator, not by
  anything reopening.
- **2026-09-25, the dictionary is generated in-repo** (owner decision): from
  Unicode Unihan kJapaneseOn / kJapaneseKun (Unicode License v3), not from
  SKK (GPL). It is no longer a `:needs-a-human` floor.
- **`:browser-component` is `:blocked-by` amu** (measured walls in the floor
  entry); amu work on those walls runs as a separate task.
- **2026-09-25, `:dictionary` closed by ADR-0235.** The generator reads
  Unihan `kJapanese` (the readings in kana) rather than the romaji
  `kJapaneseOn` / `kJapaneseKun` the floor first named; the floor's goal says
  so.
- **2026-10-22, extended to 28 floors with six UIUX floors** (owner: take the
  GUI's UIUX maturity to 100% and measure it): title-active, hover,
  focus-ring, keyboard-activate, window-maximize, high-contrast. None of them
  exists in the kernel desktop (checked by searching the browser objects and
  kernel for hover / maximize / minimize / inactive / focus-ring / tooltip),
  and none has a gate, so none counts as closed. **Correction (same day):**
  title-active's behaviour already exists (`title-rgb` / `body-rgb` in
  browser-frame2.kotoba take the focus flag), so it is a missing gate, not a
  missing feature; the other five were absent when searched by behaviour. Maturity went from 20/22 to
  20/28 by the denominator, not by anything reopening.

## Measurement

At adoption (2026-09-24, `origin/main` after ADR-0225): the tick counts
5 of 16 floors closed (frame, pointer, text, text-raise, typing), 2 needing a
human, next floor `:preedit`.

## Measurement 2026-10-22: counted closed is not currently green

The tick counts a floor closed from two facts (the gate is registered, its
README paragraph exists); it does not re-run the gate. Re-running on
`origin/main` (ea25175 lineage, macOS arm64, qemu 10.0.3, zig 0.15.2; the
build and boot run natively, no Linux needed):

- `guest-browser-frame` exits 0.
- `guest-browser-focus-cycle` exits 1 on `origin/main` and on a tree with an
  unrelated change alike (a control run): the boot prints
  `AIUEOS_GUEST_BROWSER_TEXT leftover=census-miss ops=70 text-px=1079
  hash=89910f34` where the classifier and README pin `ops=58` with the same
  text-px and hash, then the guest stops after the first desktop key.
- Cause: dd7e849 / 774c407 / 1a2aab9 (2026-10-20, JUN-143: DDS palette,
  window shadow, rounded corners) changed `browser-frame2.kotoba` and its
  object. The ink census (text-px, hash) is identical, as that commit says,
  but the coloured-rect count moved, and the pinned `ops=` values in
  `src/aiueos/compositor/guest.cljk` (35), `test/aiueos/compositor_guest_test.cljk`
  (134), `README.md` (18) and the kernel's per-stage checks were not
  re-measured. `os/aiueos/scripts/browser-frame-model.cljk` is the independent
  oracle for those counts and has to produce the new rects first.

So the 20 closed floors are 20 floors whose gates were green when they landed,
not 20 floors green today. Re-greening is the first job of the ladder, before
any new floor: update the model, then the pins from the model, then run each
gate. Until then the honest reading is: frame-level gates green, later gates
red by stale pins, behaviour unchanged.
### Re-green, 2026-10-22/23

Done in one change: `browser-frame-model.cljk` learned JUN-143's shadow strips,
three-rect rounded bodies and titlebars, and the dock (tiles plus white
initials; census glyphs now carry a colour), then every pinned `ops=` (and the
damage rectangle 80,80,652,716 / 1,870,144 bytes) in the kernel, classifier,
tests, README and CHANGELOG was re-derived from the model, not copied from the
kernel. The model reproduced the kernel's own independent measurements first
(text 70, flow 182, launch 131/107/104 with the same hashes and chain).
Measured on macOS arm64 (qemu 10.0.3, zig 0.15.2): `guest-browser-frame`,
`guest-browser-focus-cycle` and `guest-browser-damage` exit 0; the damage run
prints the scroll, selection, clipboard and damage OK lines on one serial
(ops 197 / 201 / 202 / 203) and its ten screendumps agree. The classifier unit
tests pass (22 tests, 312 assertions). The other gate profiles were not run
one by one; they read prefixes of the same serial that the damage gate's
earlier-classifier chain already requires.

### UIUX floors, 2026-10-23

`title-active` (ADR-0245), `hover` (0246), `high-contrast` (0247), `focus-ring`
(0248) and `keyboard-activate` (0249) have gates; `window-maximize` does not.
Two floor goals were corrected in the same change because the gate that closed
them measures something narrower or different from the first wording: the ring
moves on F6 and Shift+F6, not Tab (Tab is the window switcher's and the input
method's), and activation is gated for Enter and Escape, with Space sharing
Enter's path without being pressed. The high-contrast floor's "7:1" was
already met by the default palette (7.9:1); what the palette adds is a larger
margin and a black ink, which ADR-0247 says.

`window-maximize` (ADR-0250) is closed for the double press; the floor was split
in the same change because it was two jobs: the visible control and a keyboard
shortcut are `:maximize-control`, open. The ladder is 29 floors.

`maximize-control` (ADR-0251) is closed. 27 of 29 floors have gates that were run
on a real boot; the two open floors are `:browser-component` (blocked by amu,
ADR 0373) and `:p5` (a real machine).

### 2026-10-23, after 27/29

The ladder is a list the work added to, not a fixed measure of "done": its UIUX
floors were chosen by what the kernel desktop lacked when they were chosen. A
scorecard of about forty desktop-shell behaviours (windows, input, feedback,
visual design, accessibility, system UI, hardware) puts the gated work near a
third. `:cursor-shape` (ADR-0252) is the first floor added from that list; the
missing items are named in the floors file. Until a reference is fixed
(JUN-90), "100%" means every floor in the file, and the file keeps growing.

### 2026-10-23, `:minimize`

`:minimize` (ADR-0254) is the second floor added from the scorecard list: a window can be minimized
and restored from the dock. The ladder is 32 floors, 30 gated; `:browser-component` and `:p5` stay open.
