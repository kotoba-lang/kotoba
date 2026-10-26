# ADR-0238 — The wheel scrolls the window under the pointer

Date: 2026-09-25

## Status

Accepted. Closes the `:scroll` floor of the ADR-0226 ladder, extending
ADR-0223 (frame / pointer input), ADR-0224 (text), ADR-0233 (launcher and
close), ADR-0234 (body flow) and ADR-0237 (Alt+Tab).

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-scroll`
(tablet profile, after Alt+Tab) prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_SCROLL_OK`: the shell registered app 4 (its
title スクロール and its document, the lines 1 .. 20 each ended by a
`<br>`), and the host pressed launcher button 4 at (360, 14) (window 4 opened
at (80, 80, 520, 360) on top, fifteen of its twenty lines inside it),
released, sent a wheel notch over no window at (360, 14), moved to
(300, 300), and sent six notches toward the end and seven toward the start;
C turned each REL_WHEEL batch into tablet kind 6 or 7 and handed every batch
to Kotoba `kotoba_aiueos_browser_reduce` with the whole 8192-byte surface;
all seventeen `AIUEOS_GUEST_BROWSER_SCROLL_FRAME` lines were printed, and
`AIUEOS_GUEST_BROWSER_SCROLL_OK events=17 answers=40004444444444444 max=120 stack=1324 focus=4 scroll=0 chain=7421f3aa ops=164 text-px=994 hash=78270fda`.
Every frame's answer, offset, op count and #111111 census (count and FNV-1a)
is checked against `os/aiueos/scripts/browser-frame-model.cljk`'s scroll
frames and browser-reduce-v1's `:the-kernel-scroll-*` vectors.

Not, and stated here rather than at the end:

- **One notch is one line** (`:one-notch-is-one-line`). browser.input passes
  the host's `deltaY` through; the kernel has no host, so a notch is 20 px,
  browser.surface's default-theme `:line-height`. One kind per SYN-closed
  batch: a batch carrying a REL_WHEEL of 2 is still one notch.
- **Vertical only** (`:vertical-only`). browser.surface keeps
  `[x y]`; the kernel keeps y. The body flows to the window's width
  (ADR-0234), so nothing reaches past it sideways except a word with no break
  opportunity, and QEMU's tablet has no horizontal wheel to test one with.
- **No upper clamp** (`:no-upper-clamp`). browser.surface scroll-window clamps
  at 0 and nowhere else, and so does this: the stage scrolls to 120, past the
  100 at which line 20 and the caret are already inside, and the window shows
  its last lines with room below them.
- **A ceiling of 65535** (`:scroll-ceiling-65535`). An offset past it is
  refused (-12) and changes nothing -- the oracle would store it; the u32
  surface and frame2's unscrolled coordinates want a bound.

## Context

A body longer than its window was cut at the bottom inset (ADR-0224) and
could not be reached: nothing moved it. browser.input maps `:pointer/wheel`
over a window to `:window/scroll` of that window -- window-at, the same
topmost-first hit as a press -- and browser.surface scroll-window adds the
delta to `:window/scroll`, clamped at 0. It neither focuses nor raises, and
browser.input's capture is untouched. The floor asks for that on the kernel,
and for the frame to clip the scrolled body to the window.

## Decision

**Where the offsets live: surface words 2040..2043**, window id 1..4's
vertical offset. The surface had no unnamed word left (ADR-0237): the state
(0..31) is full, the IME's 432..479 are named, 2046..2047 are the pointer's.
The op area was 480..2045, 261 ops; it is now 480..2039, 260 ops, and
2040..2045 are named -- four offsets and two words of frame2 scratch. The largest
frame pinned before this used 158 ops (the flow frame); this stage's largest
uses 170. Contract vectors pin the new edge
(`exactly-260-ops-are-drawn`, `two-hundred-sixty-one-ops-are-refused`).

**Who decides: browser-reduce**, kinds 6 (a notch toward the end, +20) and 7
(toward the start, -20) at the pointer. It hits as a press hits, scrolls
that window's offset, answers its id, and changes nothing else; a miss
answers 0. The offsets are past its 128-byte state, so it now also takes the
whole surface (state-bytes 8192, whose first 128 bytes are the state); a
wheel on 128 bytes is -10, and a hit window whose id has no offset word is
-11. With the whole surface a close zeroes the closed window's offset --
browser.surface close-window drops the window and its `:window/scroll` with
it -- so a later launch opens at 0. Every earlier call site still passes 128
and is unchanged.

**How the frame clips: browser-frame2**, in unscrolled coordinates. For each
window it lays the body, the composition and the caret out as before and
writes each op the offset higher; a glyph, rule or caret whose top is above
the top inset (y + 36: the titlebar and the body's 8 px padding, the mirror
of the bottom inset y + h - 8) is not drawn, as one whose foot passes the
bottom inset is not. The insets move down by the offset instead of the pen
moving up, so no coordinate is ever negative. The title, the close control
and the launcher do not scroll. An offset past 65535 is refused (-11). With
every offset 0 each frame is the one before this ADR.

**What C does: mechanism.** pci.c reads REL_WHEEL (and, for older QEMU, the
BTN_GEAR_DOWN / BTN_GEAR_UP presses) into tablet kinds 6 / 7; main.c writes
app 4's slot and register bit (as ADR-0233 wrote app 3's), zeroes the
offsets, and hands each batch to browser-reduce and each frame to
browser-frame2.

## Verification

Measured 2026-09-25, QEMU tcg + OVMF, tablet profile. Four boots did not
answer, all for the host: two were killed by the quiet limit before the
kernel's first line (load average 121, then 235), one was stopped by hand at
load 86 when QEMU was getting 16 % of a core, and one ran out of the
profile's 1500 s wall clock at `FOCUS_GO`, before this stage. The profile's
clock is now 2400 s. The fifth boot, load ~40, first run of these sources to
reach the stage:

```
AIUEOS_GUEST_BROWSER_SCROLL_GO events=17
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=1 src=1 answer=4 focus=4 scroll=0 ops=164 text-px=988 hash=16c7e9ce
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=2 src=4 answer=0 focus=4 scroll=0 ops=164 text-px=988 hash=16c7e9ce
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=3 src=6 answer=0 focus=4 scroll=0 ops=164 text-px=988 hash=16c7e9ce
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=4 src=3 answer=0 focus=4 scroll=0 ops=164 text-px=994 hash=78270fda
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=5 src=6 answer=4 focus=4 scroll=20 ops=165 text-px=1017 hash=6c0a4440
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=6 src=6 answer=4 focus=4 scroll=40 ops=166 text-px=1027 hash=b5e126eb
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=7 src=6 answer=4 focus=4 scroll=60 ops=167 text-px=1047 hash=40c08679
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=8 src=6 answer=4 focus=4 scroll=80 ops=168 text-px=1065 hash=f7ee3a0b
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=9 src=6 answer=4 focus=4 scroll=100 ops=170 text-px=1103 hash=5793612f
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=10 src=6 answer=4 focus=4 scroll=120 ops=169 text-px=1080 hash=2d9fc3f6
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=11 src=7 answer=4 focus=4 scroll=100 ops=170 text-px=1103 hash=5793612f
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=12 src=7 answer=4 focus=4 scroll=80 ops=168 text-px=1065 hash=f7ee3a0b
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=13 src=7 answer=4 focus=4 scroll=60 ops=167 text-px=1047 hash=40c08679
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=14 src=7 answer=4 focus=4 scroll=40 ops=166 text-px=1027 hash=b5e126eb
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=15 src=7 answer=4 focus=4 scroll=20 ops=165 text-px=1017 hash=6c0a4440
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=16 src=7 answer=4 focus=4 scroll=0 ops=164 text-px=994 hash=78270fda
AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=17 src=7 answer=4 focus=4 scroll=0 ops=164 text-px=994 hash=78270fda
AIUEOS_GUEST_BROWSER_SCROLL_OK events=17 answers=40004444444444444 max=120 stack=1324 focus=4 scroll=0 chain=7421f3aa ops=164 text-px=994 hash=78270fda
```

- The same boot: the fifteen other guest-browser classifiers (frame, input,
  text, text-raised, type, preedit, ime-toggle, drag, resize, event-loop,
  caret, launch, dictionary, cursor, focus-cycle) exit 0 on its serial;
  flow-parity answers exit 3 `:no-hosted-answer` there as it does without its
  hosted answer file, and the serial carries `AIUEOS_GUEST_BROWSER_FLOW_OK`.
- The display: the screendumps after frames 1..16 and after the OK line hold
  988, 988, 988, 994, 1017, 1027, 1047, 1065, 1103, 1080, 1103, 1065, 1047,
  1027, 1017, 994 and 994 #111111 pixels, equal to the memory census frame by
  frame. At offset 0 window 4 shows lines 1 .. 15; at 120 it shows 7 .. 20 and
  the caret after 20, the first line under the titlebar cut
  (docs/assets/guest-browser-scroll.png).
- Default profile (no tablet), same sources, `guest-browser-text` exit 0:
  `AIUEOS_GUEST_BROWSER_FRAME_OK ops=5`,
  `AIUEOS_GUEST_BROWSER_TEXT_OK ops=58 text-px=1079 hash=89910f34`,
  `AIUEOS_GUEST_BROWSER_FLOW_OK windows=4 ops=158 text-px=3593 hash=a19f95a8`
  -- unchanged -- and no SCROLL line.
- QEMU red: the same sources with C handing the wheel to browser-reduce with
  128 bytes instead of the surface -- every notch answered -10 and nothing
  moved: `AIUEOS_GUEST_BROWSER_SCROLL leftover=census-miss off=14 max=0 chain=d78ab219 focus=4 scroll=0`,
  classifier `:census-miss`, gate exit 1.
- Contracts in the KIR oracle: browser-reduce-v1 115 vectors, 0 traps, 127
  memory assertions, every reason -12 .. -1 observed -- 25 new: 22 printed by
  browser-reduce-oracle.cljk from browser.input + browser.surface
  (`--check`: COMPARED 101, no DIFFERS) and the three refusals the oracle has
  no counterpart for (-10 twice, -11). browser-frame2-v1 63 vectors, 0 traps,
  41 memory assertions -- 13 new, their lists printed by
  browser-frame-model.cljk `--vectors`; the 50 before them unchanged.
- Broken six times, each red on the vector that names it: the offset not
  clamped at 0 (`:a-wheel-up-at-0-stays-at-0`, the word wraps to 0xffffffec);
  the wheel raising the window it scrolls
  (`:a-wheel-over-the-back-window-scrolls-it-without-focus-or-raise`, state
  mismatch); a close keeping the offset
  (`:a-close-drops-the-closed-windows-offset`, 40 for 0); frame2 without the
  top clip (`:an-offset-of-20-draws-the-body-20-higher-cut-at-the-top-inset`,
  7 ops for 6); the caret not moved by the offset
  (`:the-composition-and-caret-move-with-the-offset`, memory mismatch); the
  op capacity back at 261 (`:two-hundred-sixty-one-ops-are-refused`, 261 for
  -5).
- The model, with the offsets, reproduces every pinned scene and the earlier
  stages' chains (loop b185dff1, caret 62295970, launch 2845aee9, cursor
  f4bb42d8, focus 2254db31) before its scroll frames are used.
- Fuel: browser-reduce traps at 64 and passes at 128; browser-frame2 traps at
  22,528 and passes at 24,576 -- both as before, under the default 1,024 and
  the kotoba-native tier 262,144. No kotoba-native row and no amu pin change.
- Provenance: browser-reduce.o (sha256 081c1680...) and browser-frame2.o
  (aee40879...) compiled by amu main 53799cb4, twice, to the same bytes; their
  `.o.provenance.edn` / `.o.publication.edn` receipts are that compile's.
  `sync-kernel-object-digests --check`: scanned=105 stale=0.
- Classifier tests: 19 tests, 267 assertions, 0 failures.

## Consequences

- A body is reachable to its end; the next floors (selection, clipboard)
  edit text the user can now see.
- The op capacity is one less, and the surface has two scratch words
  (2044, 2045) and no free word below the pointer.
