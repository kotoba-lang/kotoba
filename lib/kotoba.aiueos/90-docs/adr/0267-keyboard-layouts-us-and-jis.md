# ADR-0267 — Keyboard layouts: US and JIS

Date: 2026-10-24

## Status

Accepted. Adds the `guest-browser-layout` gate; no new floor. Row D5 ("Other layouts and input methods") of the ChromeOS-grade
scorecard is addressed for two layouts in English mode (see Not).

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-layout` prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_LAYOUT_OK`: the clock gate is green on the same serial and all 36 `AIUEOS_GUEST_BROWSER_LAYOUT`
lines equal the frame model's, which states the typed characters apart from the Kotoba. The same physical keys give `@ 2 A : "`
on the US layout and, after F9, `" * @ +` on JIS; F9 again returns to US.

## Decision

- Surface word 1970 is the layout (0 US, 1 JIS); F9 (evdev 67) flips it and is no text.
- With the input method off, the digit row and the punctuation keys (evdev 2..13, 26, 27, 39, 40, 43, 51..53) type their
  character, Shift picks the second character of a key (`browser-ime.kotoba`: `sym-of`, `pick`, `digit-sym`), and Shift makes a
  letter upper case. Keys are physical positions, so the layout is what a position means: US and JIS differ in the shifted digit row
  and at codes 12, 13, 26, 27, 39, 40 and 43.
- The layout stage runs after the clock stage in the same session, continuing in the window the editing stage left.

## Not

Only US and JIS; only English mode (with the input method on, letters feed the romaji buffer and symbols are not typed); no dead
keys or compose; no yen / ro keys of a physical JIS board; the layout is not kept across a reboot; no layout indicator in the
status area.
