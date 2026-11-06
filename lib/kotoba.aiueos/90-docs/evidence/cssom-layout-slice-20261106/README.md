# CSSOM layout slice (JUN-134 / JUN-135 / JUN-920, render path of ADR-0287)

Date: 2026-11-06. Branch `claude/jun-920-layout-slice`, one pull request, **stacked on kotoba#1268** (style slice, branch `claude/jun-920-style-slice`; its head
`f86d0d2c` is merged into this branch and the gate below was run on the merged tree). Source, a host-native f64 reference, a QEMU profile and a gate. Nothing is wired
into `layout.cljk`, nothing runs in a CPL3 domain, nothing was merged or deployed.

## What the slice is

ADR-0287: UI document plus events in, draw list out; fixed point; kernel dialect first. After style resolution (#1268: `ck-run` leaves the cascade-winning value of
every property for every element in the owned window) this slice computes, for normal block flow only, a **box table**: per element its position, border-box size,
content size, used margins, the margins that collapsed out of its edges, padding and border, all Q6 raw (1/64 px, round half up, `length_q6.kotoba`).

| part | here |
| --- | --- |
| style properties to used values | `box_k.kotoba` (`bk-run`), lengths through `block_style_q6` (horizontal equation, 10.3.3 + 10.4), `length_q6` (vertical lengths) |
| block flow, margin collapsing, positions | `flow_k.kotoba` (`fk-run` = `ck-run` + `bk-run` + passes 2 and 3), `margin_collapse_q6` |
| independent f64 reference | `layout_ref.kotoba` (arithmetic of the canonical f64 modules `block_style`, `block_width`, `length`, `margin_collapse`) |
| QEMU profile `layout` | `native/layout-entry.kotoba`, observer `check-native-layout-qemu.py`, builder edits (profile, `*_q6.kotoba` staged beside `*_k.kotoba`) |
| gate | `lib/kotoba.cssom/scripts/check-layout-k-native-macos.py`, grid `layout_k_cases.py` |

**Inside the slice:** block boxes (`display: block`, `flow-root`; an element without `display` is a block unless its tag is inline-level), `width` `height` `min-width`
`max-width` (px, %, auto, none as CSS allows), `box-sizing`, the four margins (px, %, auto; vertical `auto` is 0), padding (px, %), border widths (px), auto margins and the
over-constrained case (ltr), margin collapsing between siblings, parent and first/last child (negative margins included), self-collapsing boxes, nesting to depth 32,
percentage heights against a definite parent content height, `display: none` and the non-rendered tags (no box, no flow, their subtree is not read).
**Refused with a status, never guessed:** inline-level tags and every `display` other than the four above (-14); a present property from the refused list: floats, `clear`, `position`,
`overflow*`, `aspect-ratio`, `columns`, `writing-mode`, `direction`, `min-height`, `max-height`, the shorthands `margin padding border border-width border-style border-*`, every
`border-*-style` (-15; a *present* property is refused whatever its value, `float: none` too); a value outside the grammar or a unit the property does not take (-16); a length out of range or
negative where CSS forbids it (-17); a result beyond +-2^30 Q6 raw (-18); the viewport width (-19). The style slice's -1..-13 pass through. **Not modelled, so not claimed:**
UA tag margins (`ua-tag-box`: a `p` has margin 0 here, give it through a user-agent origin rule), text and line boxes (the document has no text nodes, so an element with no children is 0 tall), `border-style`
(the border-width longhand is the used width; layout.cljk zeroes a border without a style), shorthand expansion, `calc()`/`em`/viewport units, rtl, scroll containers, the root's own formatting context.

## Interface

`fk-run window length inlen vw` -> element count (>= 0) or the negative status. `inlen` and the stream are the style slice's (sheet + document, unchanged wire form); `vw` is the
viewport width as Q6 raw and is the containing width of the document root. Header word 33 holds the offending element + 1 on a refusal from box-k. `fk-height` is the margin-box
height of the root, `fk-word w length n i` reads word `i` of the record of element `n`. Nothing else leaves the window; the QEMU entry writes the tables to the debug console (port 0xe9).

## Box table (page 0 of the window, 128 bytes per element, u32 word i at `128 n + 4 i`, two's complement Q6 raw)

The input stream (offset 0, 16 KiB) is dead once the cascade is done (the strings were copied into the pool), so the table overwrites it: 128 elements x 128 bytes = 16384.

```
0 kind (0 no box: display none / non-rendered tag; 1 block box; 2 inside a box-less ancestor)   1 x   2 y   3 border-box width   4 border-box height
5 content width   6 content height   7 margin-left   8 margin-right   9 margin-top   10 margin-bottom (own, auto vertical = 0)
11 margin collapsed out of the top edge   12 margin collapsed out of the bottom edge   13..16 padding top right bottom left   17..20 border top right bottom left
21 y relative to the parent's content top (the root: its collapsed top margin)   22 flags (1 flow-root, 2 height definite, 4 top margin may collapse with the first child, 8 bottom with the last)
23 border-box height from `height`   24 definite content height handed to the children (-1 none)   29 first child + 1   30 next sibling + 1   31 last child + 1
```

x, y are absolute (from the document origin), border-box. Other pages: the node table (24576), computed values (40960), property table (header @256), string table are the style slice's and are read, not changed;
the header words 32..57 (viewport, offending element, element being closed, document height, the 18 length slots), u16 at 400 + 2 s (property index + 1 of supported slot s) and u8 at 448 + k (property k is refused) are scratch.

## Properties read from the cascade output, and what had to be added

Today the cascade exposes, per (element, property index), a string id (`cv`, u16 at `40960 + 32 n + 2 k`, 0 absent) and the property name's string id in the header table (u16 at `256 + 2 k`), no key and no initial values.
Added, minimally, **without changing a style module**: `box_k` classifies each property name once per run against a generated table `nt` of 87 names (18 supported, 27 refused, 35 inline-level tags and 7
non-rendered tags of `layout.cljk`; 4 words per name: byte length and the three little-endian 7-byte words, compared with `ik-len` / `ik-word`; the gate regenerates the table from the lists in
`layout.cljk` and in the reference and compares it with the source text). Missing declared values get the CSS initial value inside `box_k` (width/height auto, min-width 0, max-width none, margins, padding, borders 0, content-box).
The value text is scanned by a port of `parse_px_q6.kotoba` over the interned bytes (that module takes a `:string` and is host-only): sign, digits (the 2^24 guard of the original: more than 8 integer digits is -16), 6 fraction
digits, `px` / `%` / unitless (read as px, as `parse-int` does), `auto` / `none` case-insensitively, no `calc()`. Vertical lengths use `length_q6`; the horizontal equation is one call of `block_style_q6/solve-pick` per output (content, margin-left, margin-right).
Shorthands cannot be expanded in the cascade without changing `selector_k` (a declaration would have to become four with the same order), so a shorthand is a refusal here; **the sheet of a layout run uses the longhands**. The cascade
allows 16 distinct property names per sheet and the slice reads 18, so a sheet uses at most 16 of them (case `bound-properties-16-at` / `-17-past`).

## Passes

1. `bk-run`, document order: per element `display` (none / non-rendered tag -> kind 0, children kind 2 and unread), refused names, `box-sizing`, the 16 lengths in slot order, vertical lengths against the containing **width** (layout.cljk
   `percentage-box-basis`), the three horizontal solves with the parent's content width, definite height (`height` px, or % of the parent's definite content height else auto; content-box adds padding and border), the flags of layout-block
   (`fc-free?` needs border-top **and** border-bottom zero, `collapse-top?` also padding-top zero, `collapse-bottom?` also padding-bottom zero and no definite height), child links. The first failing element ends the run (offending element in header word 33).
2. `up`, last element to first (descendants first): the loop state of `layout-children-block` over the in-flow children `(ht, pm, om, first?)` as documented at the top of `flow_k.kotoba`, giving each child's `rel-y`, then the box's height, collapsed-out margins.
3. `down`, document order: absolute x, y. The root's rel-y is its collapsed top margin (`ck`-style initial containing block that does not collapse); `fk-height` = rel-y + height + collapsed bottom margin.

## Bounds

128 elements, depth 32 (style slice: -3, -11); at most 16 property names per sheet (-10); viewport width 0..2^30 raw (-19); every length |px| < 2^21 (2^27 raw), percentages up to 655.35% (-17); every result and running sum within +-2^30 raw (-18). The window is the style slice's 61440 bytes.
The grid has the case on each side of each: `bound-elements-128-at/past`, `bound-depth-32-at/past`, `bound-properties-16-at/17-past`, `bound-viewport-2^30-at/past`, `bound-slot-2097151px-at` / `2097152px-past`, `bound-percent-65535-at`, `bound-geometry-eight/nine-big-siblings`, integer-part guards.

## The reference and its validation

`layout_ref.kotoba` is written from `layout.cljk` (`layout-block`, `layout-children-block`, `self-collapsing-block?`, `collapse-margins`, `percentage-box-basis`, `used-block-height`, `definite-content-height`) and CSS 2.1 8.3.1, 10.3.3, 10.4, 10.6.3, with recursion, strings
and f64; it takes the cascade as data from `style_ref.kotoba` (four exports added: `run-status run-props run-values run-prop-count`, nothing else changed), so it shares no code with the region modules. It receives each case together with the kernel's table and returns the status it refuses with, or the largest
|kernel - reference| in thousandths of a Q6 unit and the tie report. **The original `.cljk` cannot be run here** (kbb/nbb fail to load `cssom`, see `cssom-q6-slice2-20261106`), so fidelity rests on 48 hand-derived cases (`layout_k_cases.py` `hand_cases`, derived from CSS 2.1, from the measurements quoted in the docstring of
`self-collapsing-block?` (Brave 151) and from the code): the reference reproduces all 48 tables (every fixed word) with deviation 0, and the kernel's table equals them word for word (observer).

## What the gate ran (this machine, 2026-11-06, merged tree)

`PASS_NATIVE_CSSOM_LAYOUT_K` (gate, receipt `measurements.json`) and inside it `PASS_NATIVE_LAYOUT_K_QEMU` (observer, profile `layout`, state `MACOS_NATIVE_LAYOUT_K_QEMU_CANDIDATE`). **Run**, not read: native macOS Amu `e13a2054...` / `amu-full-root` `88623412...`, QEMU 10.0.3 TCG, kernel-v3 image `76aadd52...`.

* **Grid: 426 cases**: 48 hand-derived, 65 refusal cases with the status fixed by the table, 17 bound cases (each side), 93 real component trees with the real sheet (mostly refused: inline-level tags, `display: inline-block` / `flex`, shorthands), the same 93 trees with a block sheet (every element a block, per-class margins, paddings, borders, widths), 110 seeded random trees (48 elements at most, sheets of up to 16 names). **306 run, 120 refused** (statuses reached: 1, 3, 10 to 19; histogram in the receipt).
* **Kernel against the case table**: all 426 equal (status, element count, and for the hand cases every fixed word and the document height). **Kernel against the reference**: 422 compared (4 bound-past cases are not run through it); all statuses equal, no structural disagreement.
* **Maximum deviation, kernel (Q6 integers) against the f64 reference: 4.875 Q6 units (random-008)**; 234 of 306 cases at exactly 0, 292 within 0.5, 9 within 1, 4 within 2, 1 above (random-008 4.875). It is the sum of up to one half unit per rounded percentage term along the path to the element (y of the last of 48 elements); not itemised term by term.
* **Tie report (round half up)**: 43 fields in 7 cases are exact .5 of a Q6 unit in the f64 reference; at 3 of them (random-035, -073, -104; a viewport of 25607 raw makes the percentages ties) the kernel is not `floor(x + 1/2)` of the exact result: a derived value (content width = containing width - rounded padding) is the difference of rounded terms, the rule is applied per length, not per output, and the f64 oracle is not copied. The 3 fields are not itemised. The auto-margin halves are split floor/ceil by `block_width_q6` by design.
* **Negative controls (6 rebuilt kernels, builder exit 1, observer FAIL, each anchor occurs once)**: box_k border-box ignored (1 hand case differs from the table), flow_k siblings add instead of collapse (4), margin_collapse_q6 negatives ignored (3), block_width_q6 auto-margin half (2), length_q6 percentages halved (8), block_style_q6 max-width never applied (2).
* **Text bytes, kernel-v1 (reachable functions of a main reaching every export)**: style slice 98,232; length_q6 +3,552; block_width_q6 +8,019; margin_collapse_q6 +1,401; block_style_q6 +7,435; **box_k +65,483** (22,367 of them the name table `nt`); **flow_k +19,604**; the layout slice adds 105,494 over the style slice (284.6 bytes per code line of the two new modules). **Whole kernel-v3 image**: text segment 2,867,968 bytes against 2,675,584 of the `style` profile built the same day from the same tree (**+192,384**, includes the entry glue and the debug-console writer); estimated margin 222,624 bytes; 61 modules locked (51 + 10 cssom).
* **x86_64-aiueos-user-v1**: refused for every module and entry shape (0 or 2 arguments) with `E2101 unknown or unsupported form 'kernel-load-u32-4k' (byte 53)` (no region accessor exists there). Six parameters: `E7102` detail 1.
* Pipeline: the 426 cases ran inside one QEMU boot; the debug console carried the tables (a few hundred KiB).

## Dialect findings (exact errors, smallest shape that compiles)

* `kernel-store-u32-16k` is accepted by the frontend table but refused by the kernel-v1 object route: `E2101 unknown or unsupported form 'kernel-store-u32-16k' (byte 10703)`. `kernel-load-u32-16k` and the u8/u16/u64 stores work. Smallest shape: two `kernel-store-u16-16k` (low, high half), as `bx!`.
* A conditional (`if`, and the like) **inside the argument list of a call that takes a rooted window** is refused: `E7106 unsupported object profile or code limit; detail <SIR index>` (e.g. `(h8! st at (if c 1 0))`). Bind the value in a `let` first.
* `kernel-out-u8 233 b` is refused in the kernel-v1 *object* profile (`E7107 ... detail 6`), so the size compile of the entry is not possible; it compiles and runs in the kernel-v3 image build (the QEMU profile).
* `case` with 340 arms compiles (22 KiB of text); no recursion other than tail calls; the reference needs memoisation: the unmemoised version trapped (SIGTRAP, the host runtime keeps every record) at 128 elements.

## Code against documents (reported, nothing in a document edited)

* `layout.cljk` `layout-children-block`: after a self-collapsing *first* child escapes its margins through the top, the next child sets `out-mt` to its own `mt*` (`(and first? collapse-top?) mt*`), so the escaped margin is lost: `empty-first-then-sibling` puts the container at y=0 where CSS 2.1 8.3.1 puts it at y=14 (hand case, `note`).
* The same function positions a self-collapsing box at `y + gap-before` where `gap-before` ignores the box's own bottom margin: with margins 20 / (5, -7) / 12 the empty box is at 30 and the next box at 23 (CSS: the same y, 23); `hand-siblings-three-margins`.
* `layout-block` `fc-free?` tests `border-y` (top **and** bottom): a bottom border alone also stops the first child's top margin collapsing (`hand-border-bottom-blocks-both`).
* `layout-block` `content-h` uses `(* 2 inset)` of the uniform `content-inset`; the table uses per-side padding and border (the code's own draw ops use per-side `inset-side`).
* `layout.cljk` `resolve-width` clamps min/max on the border-box width and does not recompute over-constrained margins; this slice uses the merged Q6 modules (CSS 2.2 10.3.3 / 10.4) as the task prescribes, so the two disagree for `min-width` / `max-width` with padding and for `width` + `margin` over-constraints. Not compared with the hosted engine (it cannot be run).
* The #1268 README says the style slice's output is "the cascade-winning declared value per property name"; the layout slice therefore needs longhands: `padding: 6px 12px` in the real component sheet is a refusal (-15) here.
* `selector_k` rejects 17 property names (-10) while this slice reads 18; documented above, not changed.

## Not verified

* No CPL3 execution (user-v1 refuses the region forms), no wiring into `layout.cljk`, no draw list, no hardware timing.
* The reference could not be compared with the hosted `layout.cljk`; the hand cases carry that burden. Text, inline layout, floats, positioning, flex/grid, UA tag boxes are absent by design.
* The deviation of the worst random case and the three tie disagreements are explained, not itemised per field.
* The 4 bound-past cases (elements 129, depth 33, viewport 2^30 + 1, 17 properties) are checked against the case table only.

Re-run: `python3 -I lib/kotoba.cssom/scripts/check-layout-k-native-macos.py --amu ... --amu-full-root ... --amu-source ... --owner-repo-root ... --qemu ... --firmware ... --output NEW` (about 25 minutes; `--reuse-baseline DIR`, `--reuse-style DIR`, `--skip-mutants`).
