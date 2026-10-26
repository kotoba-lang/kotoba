# ADR-0242 — A frame sends only the rectangle that changed

Date: 2026-09-26

## Status

Accepted. Closes the `:damage-present` floor of the ADR-0226 ladder (20/22),
extending ADR-0224 (scanout) and ADR-0223 (the frame's draw list).

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-damage`
(tablet profile, after the clipboard) prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_DAMAGE_OK`: the five
`AIUEOS_GUEST_BROWSER_DAMAGE_FRAME` rectangles are
`os/aiueos/scripts/browser-frame-model.cljk`'s damage frames, five
`AIUEOS_GUEST_BROWSER_DAMAGE_FULL` lines follow them, the RUN line has
`refused=0`, the OK line is the model's, and the ten screendumps the host took
(each frame's damage present, then the whole screen after F12) say the damage
screendump is byte-identical to the whole-screen one for every frame, all
written by this boot, with the raise visible. Screendumps that are missing,
stale or not a 1280 x 800 P6 are exit 3 -- the display was not measured.

Not, and stated here rather than at the end: the smallest rectangle (the box
is slot by slot over the op list, so Alt+Tab sends the union of both
windows), more than one rectangle per frame, vsync or fences, hardware
other than QEMU TCG.

## Context

Every show of the desktop sent 1280 x 800 x 4 bytes to the host
(TRANSFER_TO_HOST_2D and RESOURCE_FLUSH of the whole resource), whatever an
event changed -- a pointer move re-sent 4 MB.

## Decision

- **Kotoba decides, C moves bytes.** `os/aiueos/kotoba/browser-damage.kotoba`
  (`kotoba_aiueos_browser_damage`, arity 5: ops, ops-bytes, shadow,
  shadow-bytes, count) compares the list `aiueos_desktop_present_ops2` just
  painted with the previous one, kept in an 8,192-byte shadow the caller owns
  (word 0 previous count, 1..4 the answer x y w h, 5..6 the viewport,
  8 + 6j previous op j), and answers the bounding box of every op, in either
  list, at a slot where the two differ (a glyph's box is its width x 16),
  clipped to the viewport; 0,0,0,0 when they are the same; the whole viewport
  after no list. It then copies the list over the previous one. Refusals
  -1..-4 (null region / shadow not 8,192, count outside 1..261, a bad shadow,
  an op kind that is neither rect nor glyph) touch nothing.
- `framebuffer.c` hands the object the list only when the framebuffer holds
  exactly what `aiueos_desktop_present_ops2` painted over the last frame that
  was sent. Anything else -- a paint that was not such a list, a list painted
  over a frame that was never sent, a refusal, a failed transfer -- sends the
  whole screen and makes the next list compare against nothing. `pci.c`'s
  `aiueos_gpu_present_desktop_rect` sends the rectangle (TRANSFER_TO_HOST_2D
  with its offset, RESOURCE_FLUSH with the rect); an empty answer sends
  nothing.
- A new stage after the clipboard: tablet to (320, 310), Alt down, Tab down,
  Tab up, Alt up. After each the kernel prints FRAME and holds; the host
  screendumps and presses F12; the kernel sends the whole screen, prints FULL
  and the host screendumps again.

## Verification

Measured (QEMU tcg + OVMF, 2026-09-26), first boot of these sources to reach
the stage:

    AIUEOS_GUEST_BROWSER_DAMAGE_FRAME n=1 ... damage=300,300,32,22 bytes=2816
    AIUEOS_GUEST_BROWSER_DAMAGE_FRAME n=2 ... damage=0,0,0,0 bytes=0
    AIUEOS_GUEST_BROWSER_DAMAGE_FRAME n=3 ... damage=80,80,520,360 bytes=748800
    AIUEOS_GUEST_BROWSER_DAMAGE_FRAME n=4 ... damage=0,0,0,0 bytes=0
    AIUEOS_GUEST_BROWSER_DAMAGE_FRAME n=5 ... damage=0,0,0,0 bytes=0
    AIUEOS_GUEST_BROWSER_DAMAGE_RUN shows=110 partial=66 empty=43 whole=1 refused=0 bytes=34076936 whole-bytes=450560000
    AIUEOS_GUEST_BROWSER_DAMAGE_OK events=5 partial=2 empty=3 bytes=751616 whole-bytes=20480000 focus=1 chain=6653b143 ops=170 text-px=2330 hash=5581e21a
    AIUEOS_COMPOSITOR_DAMAGE_SHOTS identical [["f91aea86507c" "f91aea86507c"] ["f91aea86507c" "f91aea86507c"] ["17ef59cabc44" "17ef59cabc44"] x3]

- The whole boot sent the whole screen once (the first show); its 110 shows
  sent 34,076,936 bytes where whole presents would have been 450,560,000. The eighteen
  earlier browser classifiers exit 0 on the same serial (flow-parity exit 3
  `:no-hosted-answer` as before). Default profile (no tablet):
  `guest-browser-flow-parity` exit 0, `FLOW_OK windows=4 ops=158 text-px=3593 hash=a19f95a8`
  unchanged.
- Screendumps: frame 1 6 colours, frame 3 8, the crop of frame 3's rectangle
  6 (`docs/assets/guest-browser-damage.png`).
- **Red in QEMU**: transferring `h - 1` rows of the answer (C only; the serial
  lines and the OK line are unchanged) -> `AIUEOS_COMPOSITOR_DAMAGE_SHOTS differs`,
  exit 1 `:display-differs`. The serial alone could not have seen it.
- Contract `os/aiueos/contracts/browser-damage-v1.edn`, 24 vectors, every one
  asserting the shadow after; expected values from
  `os/aiueos/scripts/browser-damage-oracle.cljk`, written from the rule and
  checked against painting both lists (`--check` COMPARED 24). Broken twice:
  a glyph box of 15 rows -> memory mismatch on
  `:a-changed-glyph-sends-its-width-by-16`; a previous count bound of 262 ->
  `:a-previous-count-past-261-refused` expected -3, actual -4.
- Fuel (KIR oracle bisection, 261 ops against 261, every slot changed): traps
  at 30,256, passes at 30,319; kotoba-native tier 262,144 with its
  `elf64_test` row (kotoba-native bc42c311, amu #1157).
- `browser-damage.o` 5dc5c338...: compiled by amu main 80a0d03f to the same
  bytes (`reproduce-kotoba-objects.cljk --attest`, rewritten=0); provenance
  116/116 recorded; `sync-kernel-object-digests.cljk --check` stale=0.
- Classifier: `test/aiueos/compositor_guest_test.cljk` 22 tests, 312
  assertions.

## Consequences

- A present costs what changed. The frame model and the kernel agree on the
  rectangle; the display agrees with a whole present byte for byte.
- Leftovers: `:one-rectangle-per-frame`, `:slot-by-slot-not-smallest`,
  `:no-vsync-or-fence`, `:tcg-only`.
