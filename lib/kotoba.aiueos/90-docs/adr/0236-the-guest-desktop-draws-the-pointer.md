# ADR-0236 — The guest desktop draws the pointer

Date: 2026-09-25

## Status

Accepted. Closes the `:pointer-cursor` floor of the ADR-0226 ladder,
extending ADR-0223 (frame / pointer input), ADR-0231 (event loop) and
ADR-0232 (caret).

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-cursor`
(tablet profile, after the dictionary) prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_CURSOR_OK`: KERNEL.ELF said no frame before
the stage had a pointer (`AIUEOS_GUEST_BROWSER_CURSOR_GO events=5 before=0`);
the host moved the tablet to (400, 300), (700, 450) and (1276, 796), pressed
at (1000, 600) on no window and released; after each event C wrote the
tablet's position into surface words 2046 / 2047, Kotoba
`kotoba_aiueos_browser_reduce` answered 0 (a move uncaptured, a press on no
window, an up), `kotoba_aiueos_browser_frame2` ended the list with the arrow
at the pointer, and C presented it; all five `AIUEOS_GUEST_BROWSER_CURSOR_FRAME`
lines were printed, and
`AIUEOS_GUEST_BROWSER_CURSOR_OK events=5 answers=00000 before=0 at=1000,600 tip=111111 fill=ffffff chain=f4bb42d8 ops=108 text-px=948 hash=3e8be657`.
Every frame's op count and #111111 census (count and FNV-1a) is
`os/aiueos/scripts/browser-frame-model.cljk`'s; the arrow's tip (#111111 at
the pointer) is read back from the framebuffer in every frame, its fill
(#ffffff at x + 1, y + 5) in the last.

Not, and stated here rather than at the end:

- **The pointer is drawn only from this stage on**
  (`:pointer-only-from-the-cursor-stage`). Every frame the tablet boot drew
  before it -- text-raised through the dictionary, some 30 pinned censuses --
  was drawn with word 2046 at 0 and is still pinned so; C writes the
  pointer's position only in this stage. Drawing it from the first tablet
  event on is the same object and a re-pin of every one of those lines from
  the model (as ADR-0232 did for the caret), not a new mechanism. The
  default profile never reaches the stage.
- **The sprite is the kernel's** (`:kernel-arrow-sprite`). browser.surface
  draws no pointer -- the hosted desktop has the host's -- so there is no
  oracle for its shape; the model draws it from the object header's prose.
- **One shape** (`:no-cursor-shapes`): no text beam over a body, no resize
  arrows over a handle, no hidden pointer while typing.

## Context

The desktop took a pointer (ADR-0223), dragged and resized with it
(ADR-0229, 0230) and ran it through one event loop (ADR-0231), and never
showed it: a person at the display could not see where a press would land.
The floor asks for the pointer drawn every frame at the tablet position, as
a sprite Kotoba lays out as ops, over everything, moving with the pointer.

## Decision

**Where the pointer lives.** Surface words 2046 and 2047, the two words past
the op area (480 + 6 x 261 = 2046), which nothing read or wrote: word 2046 is
the pointer's x + 1 (0 = no pointer to draw), word 2047 its y. The state
words 0..31 are full (ADR-0233 took 31), and browser-reduce's 128-byte state
is not the place: where the tablet is, is not a decision of the reducer.

**Who writes it.** C, after scaling the tablet's absolute axes to surface
pixels -- the same scaling it has always done before handing a point to
`kotoba_aiueos_browser_reduce`. Writing the scaled point into two words is
mechanism; C draws nothing and chooses nothing about the sprite.

**What is drawn (Kotoba, `browser-frame2.kotoba`).** With word 2046 not 0,
after the last window: an arrow 12 rows tall with its tip at (x, y). Row r
(0..11) is one #111111 rect (x, y + r, r + 1, 1) and, in rows 2..10, a
#ffffff rect (x + 1, y + r, r - 1, 1) over it -- a white arrow with a 1 px
outline, its left edge straight down from the tip, its right edge the
diagonal, row 11 its foot. 21 ops unclipped (33 #111111 px). Clipped to the
viewport: a row at or past vh is not drawn, every rect is cut at vw, a fill
with no width left is not drawn. Being the last ops of the list, nothing --
window, glyph, caret, launcher -- can cover it.

**Refused.** -10 when word 2046 is not 0 and the pointer is outside the
viewport (x >= vw or y >= vh), before any op is written.

**The stage.** After the dictionary, C drains the tablet, prints
`CURSOR_GO events=5 before=<word 2046>`, and for each of five events writes
the position, reduces, lays out, presents, takes the census, and samples the
tip and the fill; the census hashes fold into a chain.

## Verification

Measured 2026-09-25, QEMU tcg + OVMF, first run of the tablet profile:

```
AIUEOS_GUEST_BROWSER_CURSOR_GO events=5 before=0
AIUEOS_GUEST_BROWSER_CURSOR_FRAME n=1 src=3 at=400,300 answer=0 ops=108 text-px=948 hash=bc7b9ebc tip=111111 fill=ffffff
AIUEOS_GUEST_BROWSER_CURSOR_FRAME n=2 src=3 at=700,450 answer=0 ops=108 text-px=948 hash=0baecac3 tip=111111 fill=ffffff
AIUEOS_GUEST_BROWSER_CURSOR_FRAME n=3 src=3 at=1276,796 answer=0 ops=93 text-px=922 hash=531100a2 tip=111111 fill=ffffff
AIUEOS_GUEST_BROWSER_CURSOR_FRAME n=4 src=1 at=1000,600 answer=0 ops=108 text-px=948 hash=3e8be657 tip=111111 fill=ffffff
AIUEOS_GUEST_BROWSER_CURSOR_FRAME n=5 src=4 at=1000,600 answer=0 ops=108 text-px=948 hash=3e8be657 tip=111111 fill=ffffff
AIUEOS_GUEST_BROWSER_CURSOR_OK events=5 answers=00000 before=0 at=1000,600 tip=111111 fill=ffffff chain=f4bb42d8 ops=108 text-px=948 hash=3e8be657
```

Frame 3's `fill=ffffff` is not a fill: (1277, 801) is below the viewport and
`aiueos_desktop_sample_rgb` answers its out-of-range 0xffffffff, which
`serial_rgb` prints as six hex digits. That is why only the last frame's fill
is part of the verdict.

- The same boot: every other guest-browser classifier (frame, input, text,
  text-raised, type, preedit, ime-toggle, drag, resize, event-loop, caret,
  launch, dictionary) exit 0 on its serial -- the earlier lines are
  unchanged.
- The display: the screendumps after frames 1..4 and after the OK line hold
  948, 948, 922, 948, 948 #111111 pixels, equal to the memory census; the
  arrow read back from frame 1's dump is the header's shape (outline, white
  fill, foot row), frame 3's is four rows cut at x = 1279.
- Default profile (no tablet), same image:
  `AIUEOS_GUEST_BROWSER_FRAME_OK ops=5`, `AIUEOS_GUEST_BROWSER_TEXT_OK ops=58 text-px=1079 hash=89910f34`,
  `AIUEOS_GUEST_BROWSER_FLOW_OK windows=4 ops=158 text-px=3593 hash=a19f95a8`
  -- unchanged -- and no CURSOR line.
- Contract `browser-frame2-v1` in the KIR oracle: 50 vectors, 0 traps, 31
  memory assertions, -10 observed. Broken twice, red on the named vector: the
  fill colour one off (`:pointer-drawn-last-over-the-window`, memory
  mismatch), the y bound `>` instead of `>=`
  (`:pointer-y-at-vh-is-refused`, answered 4 instead of -10).
- The model, with the pointer, reproduces every pinned scene line and all
  27 older success vectors byte for byte before its new answers are used.
- Fuel: trap at 20,480, pass at 24,576, on `:more-than-261-ops-is-refused`
  (no pointer), as before; kotoba-native's tier for the entry is 262,144, so
  no kotoba-native row and no amu pin change.
- Provenance: `browser-frame2.o` compiled twice by amu main 4c04e448 to the
  same bytes (sha256 7ccbc353...); reproduce match=1; digests stale=0.
- Classifier tests: 17 tests, 239 assertions, 0 failures.
- QEMU red: the same image with C writing 0 into word 2046 instead of the
  pointer -- every frame is the dictionary's (ops=87 text-px=915
  hash=eaa427b3), the tip samples the window or the background --
  `AIUEOS_GUEST_BROWSER_CURSOR leftover=census-miss off=5 before=0 chain=5a2ee721 fill=f5f6f8`,
  classifier `:census-miss`, gate exit 1.

## Consequences

- Every later floor's frames carry the pointer once they come after this
  stage; a floor that moves earlier pinned frames onto the pointer re-pins
  them from the model.
- The ops cap (261) now includes the arrow's up to 21 ops.
