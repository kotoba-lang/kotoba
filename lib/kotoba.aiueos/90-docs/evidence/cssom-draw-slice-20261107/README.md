# CSSOM draw list: the laid-out box table as rect fills and borders in a shared region (JUN-805 / ADR-0287)

Date: 2026-11-07. Branch `claude/jun-805-draw-list`, from main `d5ebf8a0d`. Source, an independent host reference and decoder, a QEMU profile and a gate.
Nothing is wired into `browser.surface` or `layout.cljk`, nothing runs in a CPL3 domain, nothing was merged or deployed.
Tags: **[M]** measured (a command ran, output in `measurements.json`), **[R]** read from source.

## What the slice is

ADR-0287 fixes the interface: UI document and events in, draw list out, through shared regions. The style slice (cascade) and the layout slice
(`flow_k`, box table) existed; nothing turned boxes into output. `src/cssom/draw_k.kotoba` (`cssom.draw-k`, `dk-run`, `dk-word`) is that step:

* Input: the owned window after `fk-run` (box table 0..16383, node table, computed values, property table).
* Output: a draw list in the two free pages 13 and 14 (53248..61439) of the window, as a stand-in for the region the kernel will map read-write into the renderer
  domain and read-only into the compositor. 32-byte slots, slot 0 header, slots 1..255 ops. Header: magic `DLv1`, op count, status, element count, document height
  (Q6), slot size 32. Op: code 1 (fill-rect), x, y, w, h (Q6 raw, two's complement), colour `r<<24|g<<16|b<<8|a`, element index, role (0 background, 1..4 border top,
  right, bottom, left). The byte layout is this module's proposal; it is **not** the encoding of the existing compositor draw list (ADR-0287 still lists the
  region layouts and encodings as open), and the 259-op budget of the kernel is not checked here (this region holds 255).
* Order: CSS 2.1 Appendix E step 4 for in-flow non-positioned blocks, tree order: per box the background (border box) then the four borders. Only kind-1 boxes paint;
  a rectangle with width or height <= 0 is not emitted.
* Paint properties: `background-color` and `border-color` (one colour for the four sides), `#rgb` / `#rrggbb` any case, or `transparent`; absent = no paint.
  A border without `border-color` paints nothing (currentcolor, border-style, radius are not modelled; `box_k` already refuses border-style). Any other value
  is refused: status -20 (offending element + 1 in header word 33), -21 more than 255 ops, -18 a coordinate outside +-2^30 Q6.
* Not modelled, so not claimed: text, images, gradients, opacity, clipping/scroll, positioned/floated boxes, stacking contexts, hex with alpha, named colours, `rgb()`.

## Gate [M]

`lib/kotoba.cssom/scripts/check-draw-k-native-macos.py` (native macOS Amu `e13a2054...` / `amu-full-root` `88623412...`, QEMU TCG, profile `draw`, observer
`os/aiueos/scripts/check-native-draw-qemu.py`, entry `os/aiueos/native/draw-entry.kotoba`), receipt `measurements.json`, status `PASS_NATIVE_CSSOM_DRAW_K`.

* 198 cases (`scripts/draw_k_cases.py`): 29 hand-written (28 with an explicit draw list: px written out from the CSS rules; the reference reproduces 20 of them from the
  hand-derived box table before the kernel is looked at, the other 8 are refusals with a fixed status or lists without a hand-derived table), 6 bounds (255 ops at, 256 past,
  128 elements with one and with five ops each, 8-deep x+w past 2^30, 16 properties), 93 component trees with block sheets plus colours, 70 seeded random documents.
  1591 ops in total; draw statuses seen 0 (186), -20 (9), -21 (2), -18 (1);
  every role seen (740 backgrounds, 266 / 203 / 205 / 177 borders); 18 distinct colours.
* Host side, independent of the module: its own cascade (single compound selectors, specificity, `!important`, order), colour parser and ordering (`expected`), and a decoder
  of the raw region words (`decode`: magic, slot size, reserved words, count, op codes, roles, element indices). The observer compares the kernel's draw list with the
  reference run on the kernel's own box table (status, offending element, every op), the hand-derived lists op for op, and the kernel's box table with the hand-derived one;
  the gate decodes the receipt a second time. The reference is Python, not a native Amu program (the layout reference is native Amu).
* Negative controls: 11 one-line mutants of `draw_k.kotoba`, each rebuilt into a kernel and run; all seen. Ten end `FAIL_NATIVE_DRAW_K_QEMU` (8 to 157 cases differ). The op-limit
  mutant (256) is seen by the observer's own parse assertion (op count 256 > 255) before a receipt is written, so it has no JSON receipt.
* Size [M]: kernel-v1 text bytes of `draw_k` 22,837 (28 functions, 92 code lines, 248.2 bytes per code line; intern closure 17,393 -> 40,230); the layout closure alone is
  203,726 and with `draw_k` in one object 226,563. Whole kernel-v3 image, `draw` profile 2,974,208 text bytes against 2,936,704 for the `layout` profile built in the same run:
  **+37,504** (module plus the draw entry's dump glue); estimated margin 116,384 under the compiler cap 3,080,192; 63 modules. **History (2026-11-07):** the first measurement (before #1277 and #1278 landed) was 2,931,712 text bytes, 62 modules, margin 158,880. On the tree merged with #1277 (production signer keys) and #1278 (RTC probe) the `draw` kernel was refused E7104 at 3,103,294 B (63 modules: `native/update` now links `aiueos.imgsig-prodkeys`; imgsig_prodkeys and imgsig_testkeys were 149,125 kernel-v1 text bytes each, one case arm per word). With both key modules as 64-bit pair cases (two little endian u32 words per arm, 79,051 text bytes each; JUN-805; same words, host-checked against the old form) the numbers above and in the table are the current ones: `layout` profile 2,936,704, `draw` 2,974,208 text-segment bytes. The `prodsig` kernel (52 modules) is 2,584,576 B. The `desktop` profile does not link
  cssom at all, so this delta was not measured there; against a ~73 KB headroom the module (about 23 KB by the kernel-v1 route, 37.5 KB with glue) would fit, but that is an estimate
  by addition, not a build.
* `x86_64-aiueos-user-v1` still refuses region code (E2101), as for the other slices.

## Found on the way [M]

An `if` expression as an argument of a window-store helper (`(dw! st 0 2 (if ...))`) made the kernel-v1 object route refuse the function (E7106, rooted-base rule) while the
kernel-v3 image route accepted it; it is now computed in a helper (`code-of`).

## Re-run

`python3 -I lib/kotoba.cssom/scripts/check-draw-k-native-macos.py --amu ... --amu-full-root ... --amu-source ... --owner-repo-root /Users/junkawasaki/github/kotoba-lang --qemu ... --firmware ... --output NEW`
(about 4 minutes; `--reuse-baseline DIR`, `--reuse-layout DIR` skip builds). Profile alone: `build-native-desktop-macos.py --profile draw`.

## Next

Wire `browser.surface` / the UI document (JUN-856) as the input of the style stage, text and image ops, the real region mapping (CPL3, JUN-919) and the compositor's own op
encoding; owner decisions on the region layout (ADR-0287 "still open").
