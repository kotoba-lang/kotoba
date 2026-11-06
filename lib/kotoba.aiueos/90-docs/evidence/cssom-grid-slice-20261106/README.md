# CSSOM grid track sizing and table column widths as region code (JUN-932 part 2 / JUN-920, census group G07)

Date: 2026-11-06. Branch `claude/jun-932-grid-k`, stacked on `claude/jun-920-style-slice` (kotoba#1268, still open when this was written; its head `f86d0d2` is merged in).
Source, host references, a QEMU profile and a gate. Nothing is wired into `layout.cljk`, nothing runs in a CPL3 domain, nothing was merged or deployed.
Tags: **[M]** measured (a command ran, output in `measurements.json`), **[R]** read from source.

## What `layout.cljk` actually implements [R]

The census (`cssom-port-census-20261106`, group G07) lists the sizing sites; the code behind them is a subset, and the parser drops what it does not support:

| area | implemented | not implemented (the source says so, or the parser degrades it) |
| --- | --- | --- |
| track list | `Npx`, bare integer, `Nfr` (any decimal, `parse-dbl`), `auto`, `minmax(<px>, <px>)`, `minmax(<px>, Nfr)`, `repeat(<integer>, ...)` (expanded at parse time), constant `calc()` | **percentage tracks** (a `%` token becomes a 0px fixed track), `repeat(auto-fill/auto-fit)`, `minmax(auto, ...)` / `min-content` (become `1fr`), `subgrid`, named lines |
| track sizing | `track-sizes`: fixed, fr (`distribute-fr`), minmax, auto (min-content floor, equal-share growth with caps `distribute-equally-with-caps`, stretch of auto tracks past max-content only when no fr competes and `justify/align-content` is `normal`/`stretch`) | spanning items do not feed the intrinsics (`grid-track-intrinsics`, "scope cut, deliberately"), no `fit-content()` |
| table | `table-column-widths` (base widths, colspan shortfall shared equally and rounded up, proportional scale-down), `table-fixed-column-widths`, `distribute-excess` (surplus, `<col>`/cell-declared columns locked), the caption widening in `layout-table` | percentage cell widths beyond the `declared-cols` pre-pass, `colspan` in declared widths, border-collapse widths, `visibility: collapse` |

The arithmetic is **whole-pixel integer** (`parse-int`, `quot`, `long`); the only doubles are the fr weights (`parse-dbl`) and the proportional steps of the table (`(long (* x (/ a b)))`). There is no half-up rounding anywhere in these paths: every fraction is truncated, and the leftover goes to the last fr track / last column. See "Code against documents" for what that means for the task text.

## What the slice is

| module | `layout.cljk` | here |
| --- | --- | --- |
| `src/cssom/grid_k.kotoba` | `track-sizes` (6043), `distribute-fr` (5939), `distribute-equally-with-caps` (5982), `fixed-contribution`, `fr-weight`, `grid-track-intrinsics` (10133, single-track items), `span-width` (6711) | `gk-run`, `gk-sum`, `gk-count` |
| `src/cssom/table_k.kotoba` | `table-column-widths` (10554), `table-fixed-column-widths` (10437), `distribute-excess` (10386), the caption widening of `layout-table` (10838) | `tk-run`, `tk-sum`, `tk-count` |
| `src/cssom/grid_ref.kotoba`, `table_ref.kotoba` | the same, transcribed with the source's own arithmetic (doubles where the source has them), host-native, typed lists allowed | `run` |
| `scripts/grid_k_cases.py` | case table, wire encoding, an exact integer model and an f64 model of the source, hand-derived expectations | |
| `os/aiueos/native/grid-entry.kotoba`, `scripts/check-native-grid-qemu.py`, profile `grid` of `build-native-desktop-macos.py` | the QEMU run (fw_cfg file `opt/aiueos/grid`, same shape as the `style` profile) | |
| `scripts/check-grid-k-native-macos.py` | the gate | |

**Units.** Lengths enter and leave as Q6 raw (1/64 px) so the modules compose with the other Q6 slices; on entry every length is floored to whole px (`raw >> 6`: the `long` coercions of the source, which is also what `intrinsic-min` / `intrinsic-max` do to a measured 41.625), and a result is `px << 6`. An fr weight is D4 raw (1.5fr = 15000), exact integer arithmetic `floor(remaining * w / W)`. Negative lengths and negative weights are not representable (refused). Percentages: not in the source for tracks, so not in the module; a caller resolves a `%` before it calls (a table cell/column percentage is already resolved to px by `table-declared-column-widths`, which stays in the caller).

**Region technique** (as kotoba#1268): one owned window (`kernel-owned-window 0 61440`), page 0 holds the input as u32 words, page 1 the scratch (current sizes, intrinsics, live flags, outputs); every helper cuts the window with a constant-offset `kernel-subregion`, at most five parameters, tail-recursive loops, no heap/string/record/float, no `rem`, `/`; the largest product is `remaining * weight < 2^18 * 2^24 = 2^42`. Wire words and result encoding are documented in the headers of both modules.

## Bounds (nothing is truncated: past a bound the case is refused with the status of that bound)

| bound | value | why | status past it |
| --- | --- | --- | --- |
| grid tracks | 16 | the templates seen in `lib/` (`rg`, not an exhaustive census) have 1 to 3 explicit tracks; 16 = a page of 6-word track records | -2 |
| grid items | 32 | intrinsics derivation and span widths; 4-word item records | -3 |
| table column records / columns | 16 / 16 (`col + colspan <= 16`) | | -2 / -7 |
| table cells | 64 | 5-word cell records | -3 |
| a length word, a weight word | below 2^24 (a length: below 262144 px; a weight below 1677.7216fr) | `remaining * weight < 2^46` | -5 |
| input words | 8 + 6n + 4m (grid), 8 + 2K + 5C (table), at most 1024 | | -1 |

Other statuses: grid -4 unknown track type, -6 item range empty or outside the tracks; table -6 `colspan` 0, -7 a cell reaching past column 16; both -1 for a malformed header (length, flags, reserved words). The gate has one case on each side of every bound (16/17 tracks, 32/33 items, 2^24-1 / 2^24 for a length, a weight and the total, 16/17 records, 64/65 cells, `colspan` 0, column 16/17).

Not an unbounded-data sentinel: the one thing the sizing needs that is unbounded is the track list itself; it is bounded as above and refused beyond, never truncated. Things that need unbounded data and are **not ported** are listed below.

## What the gate ran (this machine, 2026-11-06) [M]

`PASS_NATIVE_CSSOM_GRID_K` (gate `lib/kotoba.cssom/scripts/check-grid-k-native-macos.py`, receipt `measurements.json`) and inside it `PASS_NATIVE_GRID_K_QEMU` (observer `check-native-grid-qemu.py`, profile `grid`, state `MACOS_NATIVE_GRID_K_QEMU_CANDIDATE`). Run on the merged tree, native macOS Amu `e13a2054...` / `amu-full-root` `88623412...`, QEMU TCG.

* **Grid: 229 cases** (168 grid, 61 table): 32 hand-derived (written from the CSS text and the docstrings of `layout.cljk` before any run: `100px 1fr 2fr`, thirds with the leftover, gaps, `minmax(80px, 1fr)` with and without room, fractional fr, zero and negative free space, indefinite size, the measured `auto auto` / `auto 1fr` / `auto 100px` / 400px and 200px equal-share points, the cap re-offer, the one-px hand-out, intrinsics derived from items, span widths; tables: 9/163, the surplus, the 200px `<col>`, colspan (even and odd shortfall), scale-down, fixed with a declared 52 giving 52/120/120, fixed equal 147/147, all declared, caption even and odd); 99 track-mix cases (10 mixes of fixed/fr/minmax/minmax-fr/auto x totals nil/0/25/200/1000 x gap/stretch); 26 seeded random grids; 32 seeded random tables; 9 exact-tie cases; 31 bound cases (the two sides of every bound: 17 grid, 14 table). 209 are accepted, 20 refused with the expected status.
* **Kernel against exact model: 229 of 229** (status, count, hash and sum, the observer's own check, from the case table and not from the kernel). The 32 hand-derived expectations equal the exact model and the kernel.
* **Reference against f64 model: 209 of 209 accepted cases** (the native f64 transcriptions equal an independent Python double-arithmetic model of the source, so the two transcriptions of the double semantics agree). Where a case has no tie step they also equal the hand-derived numbers.
* **Tie report** (kernel exact vs reference doubles): 200 of the 209 accepted cases are equal. **9 differ, every one at an exact tie**: the step's exact quotient is a whole number that the source's double evaluation puts one below (`99 * 0.1 / 0.3 = 33` exactly, the double chain gives 32 and moves the missing px to the last fr track; the table's `117 * 10 / 78 = 15`, double 14). 14 tie steps in 11 cases (two cases hide it: the missing px lands in the same last track). The kernel's numbers are the mathematically exact ones; whether Blink agrees was not measured, and the original `.cljk` on the JVM would evaluate `(/ content-w total)` of the table scale-down as an exact ratio (equal to the kernel there) but `distribute-excess` and `distribute-fr` in doubles (equal to the reference). The full list with the step, numerator, denominator, exact floor and double result is in `measurements.json` (`ties`). Not copied: the kernel does not reproduce the oracle's off-by-one.
* **Negative controls (4 rebuilt kernels, builder exit 1, observer FAIL)**: the fr share divides by W+1 (16 cases differ from the table, 11 from the reference beyond the ties), auto tracks stretch although an fr track competes (15 / 15), the colspan shortfall rounds down (1 / 1: `table-hand-colspan-odd`; the first draft of that case was even and the mutant passed, which is why the odd case exists), the table surplus is shared over total+1 (14 / 10). One more mutant (a capped entry freezing one px late) was tried and **passed**: it is behaviourally equivalent (the entry freezes in the next pass at the same size), so it was replaced, not counted.
* **Bounds chosen**: see the table. Window 61440 bytes (two pages used).
* **Text bytes, kernel-v1 (cumulative compile, every export reached)**: `grid_k` 39,677 (52 helpers + 3 exports, 174 code lines), `table_k` +31,979 (71,656 cumulative, 157 code lines): 216.5 bytes per code line (the style slice: 257, the Q6 scalar slices: about 160). **Whole kernel-v3 image**: text segment 2,623,232 bytes against 2,540,928 for the `imgsig` profile built in the same run (**+82,304**, includes the entry's fw_cfg glue); estimated margin 467,360 bytes; 53 modules locked (51 + the two).
* **x86_64-aiueos-user-v1**: refused for both modules, with a 0-argument and a 2-argument entry, `E2101 unknown or unsupported form 'kernel-load-u32-4k' (byte 51)` (no region accessor exists there; the same verdict as the style slice). A six-parameter function is refused on kernel-v1 with `E7102` detail 1. So no part of this runs in a CPL3 user domain.
* Dialect limits found on the way [M]: an `if` as an argument of a call or of a tail call is refused (`E7106` detail 8), a u8 store of an inline `if` is refused (detail 23); both are rewritten with a `let` binding or a helper function.

Re-run: `python3 -I lib/kotoba.cssom/scripts/check-grid-k-native-macos.py --amu ... --amu-full-root ... --amu-source ... --owner-repo-root /Users/junkawasaki/github/kotoba-lang --qemu ... --firmware ... --output NEW` (about 15 minutes; `--reuse-baseline DIR` / `--reuse-imgsig DIR` skip those builds). Builder command for the profile alone: `build-native-desktop-macos.py --profile grid`.

## What is covered and what is NOT

**Covered (ported completely):** every sizing rule of `track-sizes` for tracks of the five types the parser produces (fixed, fr, minmax-fixed, minmax-fr, auto), including the leftover rule, the stretch condition and the re-offer loop; the single-track intrinsics reduction and the span widths; all three branches of `distribute-excess`; the automatic and the fixed column algorithms; the caption widening. The implemented subset is small enough to be ported completely, so it is.

**Not covered (not ported, no sentinel because the caller owns it):**
* parsing: `parse-track-list`, `repeat()` expansion, `calc()`, `minmax()` argument parsing, the 0px / `1fr` fallbacks for unsupported tokens (strings; the caller encodes the five types), `grid-auto-rows/columns` implicit tracks (`implicit-track`), `grid-template-areas`, `used-gap` (percentage gaps), `distribution-stretches?`;
* placement: `place-grid-items`, `item-grid-placement`, auto-placement, `grid-column`/`grid-row`;
* measurement: `grid-item-min/max-content-width`, `flex-item-min-content-width` (text measurement), `measure-child`; the intrinsics enter as numbers;
* the row axis beyond what `track-sizes` does (`row-content-h`, stretch of items, `row-span-h`), `justify-content` placement of the tracks (`place-main-axis`, already in `flex_q6`), the inline-grid intrinsic width (`intrinsic-cw`);
* tables: `assign-table-cells` (the occupancy walk of `rowspan`; the caller supplies placed cells), `table-columns` (colgroup/col parsing), `table-declared-column-widths` (percentage vs length cell widths, min-content floors), collapsed borders, `visibility: collapse`, row heights, rowspan, captions' own layout;
* a refusal of a percentage track: the module has no percentage type; a `%` token is the parser's 0px fallback in the source and stays so.

## Code against documents (reported; no document edited)

* **Task text / census README vs code: "round half up", "Q6 f64 oracle".** The grid and table paths contain no rounding at all; they truncate (`quot`, `long`). The port keeps truncation, so "round half up" never applies here; the "tie" this slice reports is the exact-integer quotient that a double evaluation puts one below. The hosted values are whole pixels, not f64 fractions: the Q6 interface adds only the floor-on-entry.
* **`distribute-excess` docstring** says a 300px table with cells wanting 7px and 14px gets "100px and 200px (exactly 1:2)" (a Brave measurement). The code `(long (* target (/ w (double total))))` gives that point (the double chain happens to land on 100.0), but not every exact multiple: `10 42 26` with target 117 gives `14 63 40` in doubles where the exact floors are `15 63 39` (cases `table-tie-*`). The docstring's proportions are not what the code guarantees at exact ties. Same for `distribute-fr` (`0.1fr 0.2fr` in 99px: doubles give 32/67, exact 33/66).
* **`layout.cljk` header (lines 7 to 11)** says `minmax(<px>, <px-or-1fr>)`; `parse-minmax-token` accepts any `Nfr` maximum (a decimal weight). The module takes the weight.
* **`parse-track-token` docstring** lists percentages among the forms that "degrade to a single 0px fixed track"; the task text for this slice lists `%` among the tracks to port. The code has none; none was invented.
* `table-column-widths`'s `(/ content-w total)` is an exact Ratio on the JVM and a double elsewhere (the file is `.cljc`); which one the kotoba-hosted build uses was not run. The reference uses doubles; the kernel is exact; they agree except at ties.

## Not verified

* No CPL3 execution; the region code runs in the kernel image of the QEMU profile only (`user-v1` refuses it at the first region accessor).
* The references could not be compared with the hosted `layout.cljk` (the `.cljk` does not load on this machine, see `cssom-q6-slice2-20261106`); fidelity rests on the hand-derived cases and the code read.
* No browser comparison (Blink) of the tie cases, and no wiring of `layout.cljk`; elapsed time on hardware was not measured; the whole case grid ran in one QEMU boot.
