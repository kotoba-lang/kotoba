# CSSOM flex lines of up to sixteen items, kernel region code (JUN-932 part 1, JUN-920 follow-up)

Date: 2026-11-06. Branch `claude/jun-932-flex-k`, stacked on `claude/jun-920-style-slice` (#1268, open at the time; merged into this branch at
`f86d0d2cf`, main `d3b50df04` already contained). Source, a host-native reference, an exact model, a QEMU profile and a gate. Nothing is wired
into `layout.cljk`, nothing runs in a CPL3 domain, nothing was merged or deployed.

## What it is

The merged scalar solver `flex_q6` (kotoba#1260) is capped at four items per line: five scalar parameters leave 310 bits and an item needs 70
(base 18, min 18, max 18, factor 16). The style slice (#1268) showed the way out: hold bounded tables in an owned window as region code.

| module | exports | role |
| --- | --- | --- |
| `fxdiv_k` | `xd-pack xd-floor xd-rem` | exact share `R * w / W = F + f / W` by long division on 7-bit chunks, widened for sixteen items |
| `flex_k` | `fx-run fx-size fx-header fx-count` | load and validate the line from the window, passes until nothing changes |
| `flexplace_k` | `fp-offset fp-auto` | justify-content (six modes, `safe`) and auto margins, prefix sums from the stored sizes |

Semantics are those of `flex_q6` (and of `layout.cljk` `resolve-flexible-lengths`, `place-main-axis`, `place-main-axis-auto-margins`): grow, or
shrink scaled by the base size; min/max clamp; freeze-and-redistribute; the freeze test on the EXACT proposal (the slice-3 finding: an item at
99.994 against a minimum of 100 must freeze); one half-up rounding of the exact share for an item that is not frozen; a zero weight is a frozen
item; `net = avail - gaps` is the caller's. **More than sixteen items is refused with status 1; nothing is truncated.** The ranges are those of
`flex_q6` (base, min 0..262143, max none or 0..262142, factor 0..65535, net -524288..524287) so the two agree wherever `flex_q6` is defined.

### Window and wire format

One owned window of 24576 bytes (`kernel-owned-window 0 24576`): input line 16 KiB at 0 (8 little-endian u32 header words then 16 bytes per item),
item table at 16384 (32 B x 16: cur, min, max, ev, weight u64, factor), header page at 20480. Details at the head of `flex_k.kotoba`. A record
keeps `2 * size + changed`; a changed item is frozen by `cur := size`, `weight := 0`; the pass loops are tail recursions over the table.

### Where it differs from `flex_q6` (stated, not hidden)

* `|R|` (free space) may be up to `2^23` here, `2^21` in `flex_q6`: sixteen bases of 262143 plus a net of 524288 reach 4.7e6. For up to four
  items `|R|` cannot exceed 1.57e6, so the two bounds agree on every line `flex_q6` can encode. `W` (sum of weights) is below `2^38`
  (16 x 65535 x 262143); every long-division step stays below `255 W < 7.01e13 < 2^46`. Four chunks of `|R|` instead of three.
* No pass counter below 18 is needed: each changing pass freezes at least one more item, so at most `n + 1` passes run; status 6 is a guard that
  cannot be reached. The source's own guard (initially `n`) also never fires: pass 0 may change only already-frozen items, every later changing
  pass freezes an unfrozen one, so the last pass has index at most `n`.
* `fp-auto` takes the gap itself (the sums of `flex_q6` are the caller's) and refuses a negative gap as `offset` does; `flex_q6/auto-offset`
  alone has no gap check (its caller adds the gaps). The reference carries that one rule when it calls `flex_q6`.

## References and oracles

* **Exact model** (`scripts/flex_k_cases.py`, Python `Fraction`, no float anywhere): the loop of `cssom.flex/solve` (itself the f64 transcription of
  the source) in exact arithmetic, then one half-up rounding; `place-main-axis` and `place-main-axis-auto-margins` likewise. The guest's digest of
  every case is compared with the digest of this model, not with anything the kernel produced.
* **Hand-derived cases**: 44 cases written from CSS Flexbox 9.7 before any run (the docstring table of `resolve-flexible-lengths` for 1..4 items; for
  5..16 items: equal grow, a min on one of five, two capped of eight, a **four-pass cascade of ten**, shrink with a floor, sixteen equal, sixteen
  scaled shrink `size = base * 1000 / 1360`, zero free space, shrink 0, all-min, max 0, 2:1, twelve zero factors, a 0.5-raw tie, mixed ladder;
  justify-content on five 100 px items in 800 px for all six modes and the safe/unsafe overflow, two auto-margin cases; ten refusals). The exact
  model reproduces every one (checked by the gate); so does the kernel.
* **n-item f64 reference** (`src/cssom/flex_ref.kotoba`, new, host-native): `solve-n`, `place-n`, `auto-n` over typed lists. Cross-checks: against
  `cssom.flex` (the four-item f64 reference, six items for the placement), 1,554 comparisons, 0 differences > 1e-9; against `flex_q6` on every line
  of at most four items, 684 sizes and 4,585 placements, 0 mismatches against the exact integers.
* The original `.cljk` cannot be run on this machine (`kbb` and `nbb` fail to load `cssom`); fidelity rests on the code read and the hand cases.

## What the gate ran (this machine, 2026-11-06)

`PASS_NATIVE_CSSOM_FLEX_K` (gate `lib/kotoba.cssom/scripts/check-flex-k-native-macos.py`, receipt in `measurements.json`). Native macOS Amu
`e13a2054...` / `amu-full-root` `88623412...`, QEMU 10.0.3 TCG, profile `flex` of `build-native-desktop-macos.py` (entry
`native/flex-entry.kotoba`, observer `check-native-flex-qemu.py`, fw_cfg file `opt/aiueos/flex`, state `MACOS_NATIVE_FLEX_K_QEMU_CANDIDATE`; a new profile,
modelled on `style`, not the style profile itself).

* **Grid: 990 cases** (hand 44, capacity 32, bound 36, cascade 35, tie 48, placement 135, random 520, small 140), 971 run and 19 refused with the
  expected codes 1, 2, 3, 4. Run by item count: 1:59 2:91 3:57 4:68 5:148 6:46 7:34 8:52 9:74 10:40 11:37 12:47 13:32 14:35 15:38 **16:113**. 368 cases
  carry a justify-content mode, 164 auto margins. Both sides of every bound: n 1/16/17/32, base, min, max, factor, net (each at the limit and one
  past), the sixteen-item extremes (weights near `2^38`, `|R|` near `2^22`), the placement range `2^30`.
* **Kernel against the exact model: 990 of 990 equal** (a 24-bit digest of the sizes, then the offsets, then the auto offsets, plus the status).
  Digest collisions: 24 bits, a wrong case would escape with probability about 6e-8 per case; the negative controls below show the digest does see
  one-line errors.
* **Maximum deviation**: kernel against the exact integers 0 raw. Against the f64 values (12,252 sizes and offsets compared): **0.500 raw** (500 on
  the x1000 scale, reached only at exact ties), no deviation above 0.5 raw; 0 violations.
* **Tie report**: the grid holds 124 items whose exact value has fractional part 1/2 (16 lines). In 8 comparisons the f64 oracle disagrees with the
  exact rule at such a tie (the f64 value lands on the other side of the half than the exact value): reported, not copied; the kernel follows the exact
  rule like `flex_q6`. No disagreement away from a tie.
* **Negative controls (3 rebuilt kernels, observer FAIL, builder exit non-zero)**: `fxdiv_k` chunk shift (466 cases differ from the model), `flex_k`
  freeze test `>=` to `>` (3: random cases with an exact proposal equal to a maximum and a remainder), `flexplace_k` space-evenly `i + 1` to `i` (31).
  Each anchor occurs once. A fourth, host-side: the f64 reference with the shrink weight missing the base size gives 27 violations.
* **Text bytes, kernel-v1 (cumulative compile, every export reached)**: `fxdiv_k` 4,158; `flex_k` +20,668 (24,826); `flexplace_k` +8,253 (33,079); 142 code
  lines, 233 bytes per code line. **Whole image** (kernel-v3, text segment): 2,597,376 for profile `flex` against 2,540,928 for profile `imgsig` built
  the same day on this tree, **+56,448** (includes the entry's fw_cfg glue and digest loops); estimated margin 493,216 bytes; 54 modules locked
  (51 + the three).
* **x86_64-aiueos-user-v1 verdict**: `flex_k` and `flexplace_k`, with a 0-argument and a 2-argument entry: refused,
  `E2101 unknown or unsupported form 'kernel-load-u32-16k' (byte 1282)` (no region accessor exists there). `fxdiv_k`, which holds no window form:
  the 0-argument entry is accepted, the 2-argument entry is refused `E7102` detail 9. A six-parameter function is refused on kernel-v1: `E7102` detail 1.
* The three mutant kernels and the baseline kernel were built and run in one invocation of the gate; the final receipt re-verifies those builds
  (`--reuse-run`: receipts read, every record compared with the exact model again) after a fix to the user-v1 stage that only touched the size
  stage. The module sources did not change between the build and the re-verification.

## Code against documents (reported, nothing in a document edited)

* The style evidence (`cssom-style-slice-20261106/README.md`) says "54 modules locked (50 + the four)"; `build-native-desktop-macos.py` checks
  `sourceModuleCount == 55` for `style` (51 + 4). The code is followed; for `flex` the check is 54 (51 + 3), which the build confirmed.
* `flex_q6.kotoba` documents `auto-offset` next to `offset` without saying that only `offset` refuses a negative gap; `auto-offset` has no gap check.
* The task text speaks of the f64 reference `flex.kotoba` as the oracle "for <= 4 items"; in code `solve` takes four items but `place` / `auto-place`
  take six, so the placement cross-check runs to six items.

## Not verified

* No CPL3 execution; the region code runs in the kernel image of the QEMU profile only (`x86_64-aiueos-user-v1` refuses it).
* The exact model and the f64 reference transcribe `layout.cljk`; neither was compared with the hosted `.cljk`.
* One boot of 990 cases; nothing here is a throughput measurement on hardware. `flex-wrap` line breaking, `flex-basis`, and the measured-size inputs
  are not part of this slice (they stay in `layout.cljk`).
