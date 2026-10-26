# ADR-0240 — Shift+Left / Shift+Right select, and Backspace deletes the selection

Date: 2026-09-25

## Status

Accepted. Closes the `:selection` floor of the ADR-0226 ladder, extending
ADR-0225 (typing), ADR-0232 (caret and Backspace) and ADR-0238 (wheel).

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-selection`
(tablet profile, after the wheel) prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_SELECTION_OK`: the host sent five wheel
notches toward the end at (300, 300) -- window 4's offset 20 .. 100, line 20
and its caret inside the window -- then Shift down, Left down / up, Left
down / up, Right down / up, Left down / up, Shift up, Backspace down / up; C
handed each tablet batch to Kotoba `kotoba_aiueos_browser_reduce` (whole
surface) and each key, as code * 4 + value, to Kotoba
`kotoba_aiueos_browser_key`; all seventeen
`AIUEOS_GUEST_BROWSER_SELECTION_FRAME` lines were printed, and
`AIUEOS_GUEST_BROWSER_SELECTION_OK events=17 answers=44444000000000000 max-sel=2 body=48 focus=4 scroll=100 chain=2b46197d sel-chain=cb830579 ops=168 text-px=1058 hash=6ca5ee4a`.
Every frame's answer, offset, selection length, op count, #111111 census and
#b5cdf1 census (count and FNV-1a) is checked against
`os/aiueos/scripts/browser-frame-model.cljk`'s selection frames.

Not, and stated here rather than at the end:

- **The caret is still only at the end outside a selection**
  (`:caret-only-at-the-end`). Left / Right without Shift, Home and End are
  not taken. A selection is therefore always the last k code points of the
  body, the anchor at its end: browser.text-edit move-caret with `:extend?`
  from a caret at the end keeps the anchor there and moves the caret, and
  every state the object can reach is [n - k, n) with the caret at n - k.
- **One selection at a time** (`:one-selection-at-a-time`). The words name
  one window. A selection of a window that is not focused is kept and drawn
  again when it is focused, but the first Shift+Left in another window
  replaces it (the hosted desktop keeps a text state per window).
- **No arrows in a composition** (`:no-arrows-in-a-composition`). While
  romaji, a preedit or a conversion is pending the arrows change nothing; a
  letter empties the selection before it composes, so the two never meet.
- **Shift does not case a letter** (`:shift-does-not-case-letters`): it is
  held for the arrows only, as before.
- **An opaque highlight** (`:opaque-highlight`). cssom.layout's sel-ops lays a
  translucent rgba(70,130,220,0.4) rect over the text; the blit has no
  alpha, so the kernel draws its colour over the focused body's #ffffff,
  #b5cdf1, BEHIND the glyphs -- which is what the floor asks and what keeps
  the #111111 census of the text the same.

## Context

Text editing stopped at the caret (ADR-0232): Backspace deleted the code point
before it and nothing selected. browser.input maps Shift+Arrow to
`:text/edit` move-caret with `:extend?`, Backspace to delete-backward and a
typed character to insert-text, and browser.text-edit keeps
`:text/selection`; cssom.layout's sel-ops draws a non-collapsed selection as
a highlight rect and no caret. The floor asks for that on the kernel.

## Decision

**Where the state lives: surface words 2035..2037**, freed by cutting
browser-frame2's op capacity from 260 to 259 (ops at words 480..2033, as
ADR-0238 cut it from 261). 2034 is frame2's scratch (the first highlighted
index of the body being laid out, 64 for none), 2035 is Shift held, 2036 the
window id the selection belongs to (0 none), 2037 its length k; 2038 and 2039
are not assigned. The largest frame pinned so far is 171 ops (this stage).
The contract's edge vectors are the ADR-0238 ones with one body code point
less (`exactly-259-ops-are-drawn`, `two-hundred-sixty-ops-are-refused`).

**Who decides: browser-key.** Shift (evdev 42 or 54) is held from its press to
its release, as Alt is (ADR-0237). Shift+Left / Shift+Right presses are
move-caret -1 / +1 with `:extend?` on the focused body: k + 1 up to the body's
length, k - 1 down to 0; at either end the key changes nothing. k is read
clamped to the body (normalize-selection), and as 0 when the words name
another window. Backspace with a selection is delete-backward's first branch
(insert-text "" over it: the k code points go, k is 0); without one it
deletes the code point before the caret as before. A letter with a selection
first does the same -- with the IME off insert-text of the letter, with it on
the composition then starts over the emptied place, as a platform IME's
compositionstart deletes the selection. No answer changes: every key of the
stage answers 0.

**How it is drawn: browser-frame2.** For the focused window whose id is word
2036, the last min(k, n) code points are selected. Each glyph drawn for a
selected code point is preceded by a rect of its own width, 16 high, at its
place, in #b5cdf1; a collapsed white-space run's one U+0020 goes with the code
point it is drawn for (the first of the run on a line kept as collapsed, the
last before the word on a line packed by words); a 10 draws nothing; a glyph
not drawn (cut by an inset or the viewport) has no highlight. With something
selected there is no caret. With the words 0 each frame is the one before
this ADR.

**What C does: mechanism.** main.c's new stage after the wheel reads the
tablet and keyboard rings, hands batches and keys to the objects, presents
each frame and counts two colours; no code point, key or rect is chosen in C.

## Verification

Measured 2026-09-25, QEMU tcg + OVMF, tablet profile. The first boot was
killed by the quiet watchdog (150 s) before the kernel's first line, at load
~56 rising to ~190 -- the host, during firmware. The second, with
`AIUEOS_QEMU_QUIET=600` (the smoke script's own override), is the first boot of
these sources to reach the stage:

```
AIUEOS_GUEST_BROWSER_SELECTION_GO events=17
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=1 src=6 key=0 answer=4 scroll=20 sel=0 ops=165 text-px=1017 hash=6c0a4440 sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=2 src=6 key=0 answer=4 scroll=40 sel=0 ops=166 text-px=1027 hash=b5e126eb sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=3 src=6 key=0 answer=4 scroll=60 sel=0 ops=167 text-px=1047 hash=40c08679 sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=4 src=6 key=0 answer=4 scroll=80 sel=0 ops=168 text-px=1065 hash=f7ee3a0b sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=5 src=6 key=0 answer=4 scroll=100 sel=0 ops=170 text-px=1103 hash=5793612f sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=6 src=0 key=169 answer=0 scroll=100 sel=0 ops=170 text-px=1103 hash=5793612f sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=7 src=0 key=421 answer=0 scroll=100 sel=1 ops=170 text-px=1087 hash=2602913b sel-px=104 sel-hash=e4f21595
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=8 src=0 key=420 answer=0 scroll=100 sel=1 ops=170 text-px=1087 hash=2602913b sel-px=104 sel-hash=e4f21595
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=9 src=0 key=421 answer=0 scroll=100 sel=2 ops=171 text-px=1087 hash=2602913b sel-px=211 sel-hash=49ff70dc
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=10 src=0 key=420 answer=0 scroll=100 sel=2 ops=171 text-px=1087 hash=2602913b sel-px=211 sel-hash=49ff70dc
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=11 src=0 key=425 answer=0 scroll=100 sel=1 ops=170 text-px=1087 hash=2602913b sel-px=104 sel-hash=e4f21595
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=12 src=0 key=424 answer=0 scroll=100 sel=1 ops=170 text-px=1087 hash=2602913b sel-px=104 sel-hash=e4f21595
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=13 src=0 key=421 answer=0 scroll=100 sel=2 ops=171 text-px=1087 hash=2602913b sel-px=211 sel-hash=49ff70dc
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=14 src=0 key=420 answer=0 scroll=100 sel=2 ops=171 text-px=1087 hash=2602913b sel-px=211 sel-hash=49ff70dc
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=15 src=0 key=168 answer=0 scroll=100 sel=2 ops=171 text-px=1087 hash=2602913b sel-px=211 sel-hash=49ff70dc
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=16 src=0 key=57 answer=0 scroll=100 sel=0 ops=168 text-px=1058 hash=6ca5ee4a sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=17 src=0 key=56 answer=0 scroll=100 sel=0 ops=168 text-px=1058 hash=6ca5ee4a sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_SELECTION_OK events=17 answers=44444000000000000 max-sel=2 body=48 focus=4 scroll=100 chain=2b46197d sel-chain=cb830579 ops=168 text-px=1058 hash=6ca5ee4a
```

- The same boot: the sixteen other guest-browser classifiers (frame, input,
  text, text-raised, type, preedit, ime-toggle, drag, resize, event-loop,
  caret, launch, dictionary, cursor, focus-cycle, scroll) exit 0 on its
  serial; flow-parity answers exit 3 `:no-hosted-answer` there, as it does
  without its hosted answer file.
- The display: the screendumps after frames 1..16 and after the OK line hold
  1017, 1027, 1047, 1065, 1103, 1103, 1087 x 9, 1058 and 1058 #111111 pixels
  and 0 x 6, 104, 104, 211, 211, 104, 104, 211, 211, 211, 0, 0 #b5cdf1 pixels
  -- the memory census, frame by frame -- and 6 colours, 7 while something is
  selected (docs/assets/guest-browser-selection.png: frame 9, "20" selected).
- Default profile (no tablet), same sources, `guest-browser-text` exit 0:
  `AIUEOS_GUEST_BROWSER_FRAME_OK ops=5`,
  `AIUEOS_GUEST_BROWSER_TEXT_OK ops=58 text-px=1079 hash=89910f34`,
  `AIUEOS_GUEST_BROWSER_FLOW_OK windows=4 ops=158 text-px=3593 hash=a19f95a8`
  -- unchanged -- and no SELECTION line.
- QEMU red: the same sources linked with origin/main's browser-ime.o (no
  selection; `AIUEOS_KOTOBA_BROWSER_IME_OBJECT`, its digest swapped in for that
  run only): Shift+Left selected nothing and Backspace deleted one code point --
  `AIUEOS_GUEST_BROWSER_SELECTION leftover=census-miss off=11 chain=62410b1b sel-chain=f9ed9fe0 sel=0 shift=0`,
  classifier `:census-miss`, gate exit 1.
- Contracts in the KIR oracle: browser-ime-v2 94 vectors, 289 steps, 264
  memory assertions, 0 traps -- 23 new, printed by
  `os/aiueos/scripts/browser-selection-oracle.cljk` from browser.text-edit
  move-caret / delete-backward / insert-text (`--check`: COMPARED 23);
  browser-frame2-v1 74 vectors, 52 memory assertions -- 11 new, their lists
  printed by browser-frame-model.cljk `--vectors`, and the model reproduces
  all 52 listed vectors from their seeds.
- Broken six times, each red on the vector that names it: Shift+Right below 0
  (`:shift-right-with-nothing-selected-changes-nothing`, word 2037 0xffffffff);
  Backspace ignoring the selection (`:backspace-deletes-the-selection`); a
  letter appended past the selection
  (`:ime-off-a-letter-replaces-the-selection`); the highlight after the
  glyph (`:a-selection-is-highlighted-behind-its-glyphs-with-no-caret`, ops
  mismatch); the caret kept (same vector, 10 for 9); the collapsed space's
  index moved (`:a-collapsed-space-goes-with-the-first-white-space-of-its-run`,
  9 for 8).
- The model, with the selection, reproduces every pinned scene and the earlier
  stages' chains (loop b185dff1, caret 62295970, launch 2845aee9, cursor
  f4bb42d8, focus 2254db31, scroll 7421f3aa; flow 158 / 3593 / a19f95a8)
  before its selection frames are used.
- Fuel: browser-key traps at 600 and passes at 640, browser-frame2 traps at
  22,528 and passes at 24,576 -- both as before, under the kotoba-native tiers
  16,384 and 262,144. No kotoba-native row and no amu pin change.
- Provenance: browser-ime.o (sha256 d0250385...) and browser-frame2.o
  (1ac6a7da...) compiled by amu main 3e81c6b3, twice, to the same bytes; their
  receipts are that compile's. `sync-kernel-object-digests --check`:
  scanned=111 stale=0.
- Classifier tests: 20 tests, 281 assertions, 0 failures.

## Consequences

- Text the user can see can be selected and deleted; the next floor
  (clipboard) has a selection to copy.
- The op capacity is one less (259), and 2038 and 2039 are the surface's only
  unassigned words.
