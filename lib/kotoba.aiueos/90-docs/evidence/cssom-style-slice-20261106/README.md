# CSSOM style slice (JUN-134 / JUN-135 / JUN-920, render path of ADR-0287)

Date: 2026-11-06. Branch `claude/jun-920-style-slice`, one pull request. This is source, a host-native reference, a QEMU profile and a gate. Nothing
is wired into `layout.cljk`, nothing runs in a CPL3 domain, nothing was merged or deployed.

## What the slice is

ADR-0287 fixes the renderer's input as a UI document (a Hiccup-shaped tree, JUN-856) plus a stylesheet (`css_sheet.kotoba` renders the rules,
`ui_components_sheet.kotoba` is the components' sheet) and its output as a draw list. HTML text parsing (htmldom) is not on the native path and is not in
this slice. What layout needs first is the style of every element, so this slice is the style-resolution core of `lib/kotoba.cssom/src/cssom/core.cljk`:

| part | `core.cljk` | here |
| --- | --- | --- |
| selector tokens, compound parts | `selector-tokens`, `selector-parts`, `parse-simple-selector` (2969, 3091, 3560) | `selector_k.kotoba` (`chain`, `compound`), reference `complex`, `compound` |
| matching | `matches-simple?`, `parts-match?` (7410, 7362) | `match_k.kotoba` (`pbits`, `rel`), reference `match-at?` |
| specificity | `simple-selector-specificity`, `specificity` (3586, 3679) | packed in one i64 in `selector_k`, a triple in the reference |
| cascade order | `resolve-style-and-flow` `sort-by (juxt :important? :origin :inline? :layer :specificity :proximity :order :decl-index)` (10390) | `cascade_k.kotoba` key, reference `larger?` |
| inheritance | `inherited-properties` / `inherited-property?` (8031) | `cascade_k.kotoba` `inh?` (generated), reference `inherited?` |

**Inside the subset:** type, `*`, `#id` and `.class` compounds (first `#id` only, as the code); the four combinators (descendant, `>`, `+`, `~`); selector
lists split at commas; `!important`; user-agent below author origin; later source order wins a tie; the 37 inherited properties of the engine's list take the
parent's computed value when no declaration applies; values are opaque text.

**Outside it, and refused rather than skipped:** attribute selectors, pseudo-classes and pseudo-elements, namespaces, escapes, non-ASCII identifiers
(status 12); CSS-wide keyword values `inherit initial unset revert revert-layer`, case-insensitive (status 13); a property repeated inside one rule
(status 1, `core.cljk` keeps a rule's declarations in a map). **Outside it and not modelled** (nothing refuses these; the hosted engine does them):
cascade layers, `@scope` proximity, `@media`/`@container`/`@supports`, inline style, shorthand/longhand expansion (`padding` and `padding-left` are two
unrelated names here), `var()`/`env()`/`attr()` substitution, `content`/counters, pseudo-element styles. The slice's output is the cascade-winning
declared value per property name, plus inheritance.

## Encodings (the contract of the region modules)

Everything lives in one owned window of 61440 bytes (`kernel-owned-window 0 61440`; the compiler's guard is bytes <= 61440 and <= (15 - slot) * 4096). The
public functions take `(window, length, ...)` and cut the window with inline `kernel-subregion` at constant offsets, as `mldsa_sample.kotoba`; every
helper takes a rooted window of constant length, at most five parameters, loops are tail recursion, no product exceeds 2^46.

### Input stream (read-only; the document and the stylesheet)

All lengths are one byte; strings are bytes (the grid is ASCII). `stream = sheet document`.

```
sheet    = rule* 0x00
rule     = 0x52 origin selector-length selector declaration-count declaration*      origin 0 user agent, 1 author
declaration = property-length property value-length value flags                      flags bit 0 = !important, others must be 0
document = op* 0x00                                                                  exactly one root, balanced
op       = 0x45 tag-length tag id-length id class-length classes                     open an element (id/classes may be empty)
         | 0x2F                                                                      close the current element
```

Text nodes are not part of the document (only elements matter for the sibling combinators, `preceding-element-siblings`). The class string is split on the
space byte only (`core.cljk` `classes` uses `split-value-components ... " "`) and is a set. Values are trimmed by the producer. A sheet declaration
carries the value text exactly as `css_sheet.kotoba` renders it (`6` becomes `6px`); the gate proves that the grid's sheet equals the rendered one.

### Tables

| page (byte offset) | content | record | capacity |
| --- | --- | --- | --- |
| 0 (16 KiB) | input stream | bytes | 16384 |
| 16384 | string entries | 8 B: u16 pool offset, u16 length, u32 hash; id 1..511 | 511 strings |
| 20480 | string pool | bytes | 4096 |
| 24576 | node table | 32 B: u16 tag @0, id @2, parent @4, previous sibling @6 (65535 none), depth @8, class count @10, class ids @12 (8 x u16) | 128 elements, 8 classes each |
| 28672 | selector entries | 32 B: u16 origin @0, compound count @2, first compound @4, first declaration @6, declaration count @8, u64 specificity @16 | 128 entries |
| 32768 | declarations | 8 B: u16 property index @0, value id @2, flags @4 | 512 |
| 36864 | compounds | 16 B: u16 combinator @0 (0 first, 1 descendant, 2 child, 3 adjacent, 4 general sibling), tag @2, id @4, class count @6, class ids @8 (4 x u16) | 256 (8 per selector), 4 classes each |
| 40960 | computed values | u16 value id at `32 n + 2 k` | 128 x 16 |
| 45056 | match matrix and scratch | rows of 16 B (bit n of row s); u8 P, ANC, SIB per node at +2048, +2176, +2304 | 128 x 128 bits |
| 49152 | header words and scratch | u32 words (nodes 2, entries 3, declarations 4, compounds 5, properties 6, ...), u16 property table @256, u16 open stack @512, u16 last child @640, best key u64 @1024, best value @1152, inherited flag @320 | 16 properties, depth 32 |

Pages 13 and 14 (53248..61439) are free. `ik_intern` (`intern_k.kotoba`) gives every identifier an id once (hash `h <- 257 h + b + 1` mod 2^32 from 5381, then a byte
compare): tags, ids, classes, property names, values. A selector tag is lower-cased before it is interned, as `parse-simple-selector` does with
`str/ascii-lower`; an element's tag is not. Every other module compares ids.

**Specificity** is `ids << 32 | classes << 16 | tags`, summed over the compounds, so three counters up to 65535 sit in one i64 and compare as the tuple does;
a selector is at most 255 bytes, so no counter can reach 128. As in `core.cljk` only the first `#id` of a compound counts and matches (`(first ids)`).
**Cascade key** of a declaration: `((important << 49 | origin << 48 | specificity) << 12) + (declaration index + 1)`, 62 bits; the larger key wins. The
declaration index grows with rule order and with position inside a rule, so it is `:order` and `:decl-index` of the sort in one number.

**Matching without recursion or backtracking.** Elements come in document order, so a parent and a previous sibling are always done before the element.
For one selector entry, per element: `ANC[n] = ANC[parent] | P[parent]`, `SIB[n] = SIB[prev] | P[prev]`, and bit k of `P[n]` is set when compound k
matches `n` and (k = 0, or by its combinator: bit k-1 of `ANC[n]` for descendant, of `P[parent]` for child, of `P[prev]` for adjacent, of `SIB[n]`
for general sibling). The entry matches `n` when bit (count - 1) of `P[n]` is set. This is the dynamic-programming form of `parts-match?`' right-to-left walk with
backtracking; the reference uses the backtracking form, so the two are independent.

### Why these capacities

* **One 60 KiB window**: the largest owned window the compiler admits; the nine tables above use 53 KiB of it. The tier accessors are 4 KiB and
  16 KiB, so each table is one 4 KiB page except the 16 KiB input.
* **128 elements, depth 32**: the largest component tree is 31 elements (`compositor-view`, `session-document`); a node record is 32 B and a match row is 128
  bits, so 128 fills a page exactly. Depth 32 is the stack the header page holds.
* **8 classes per element, 4 per compound, 8 compounds per selector**: the real documents have at most 3 classes (`dock-app`, `dads-chip-label`) and the real
  sheet selectors are single classes; `P` is one byte per element so a selector has at most 8 compounds.
* **128 selector entries, 256 compounds, 512 declarations, 16 properties**: the real sheet is 15 rules, 40 declarations, 9 properties. 128 entries is a
  page of 32 B records; 16 properties x 128 elements x 2 B is one page of computed values.
* **511 strings, 4096 pool bytes**: the largest case (the real sheet over a component tree) interns about 90 strings of about 600 bytes.
* **16384 input bytes**: the largest case is 1658 bytes. A stream of any length is cut at 16384 by the caller and refused (status 2) by `ck-run`.

Nothing is truncated: past a bound the case is refused with the code of that bound, and the grid has one case on each side of every bound.

## The reference (`src/cssom/style_ref.kotoba`, host-native)

Written without looking at the region modules' encodings, from `core.cljk`: tokens, parts with a combinator each, specificity as a vector, right-to-left
matching with backtracking over ancestors and preceding siblings, a winner per property by lexicographic `(important origin a b c order)`, inheritance by
the engine's `|`-delimited list. It uses strings and `:document` values (the case is `document-edn-read`). Measured limits of that dialect that shaped it:
`document-vector-conj` built past 32 elements and `typed-map-assoc` past about 24 entries trap (SIGTRAP; `typed-list-conj` works to at least 100), so
nodes, entries and styles are typed lists; `string-length` counts bytes while `string-code-point-at` indexes code points (a non-ASCII selector traps), so
that one refusal case is not run through the reference.

## Validation of the transcription

The original `.cljk` cannot be run here (`kbb` and `nbb` fail to load `cssom`: "Can only recur from tail position", see `cssom-q6-slice2-20261106`). The
reference is therefore checked against 35 hand-derived cases whose computed styles were written out from the CSS rules before any run (`style_k_cases.py`
`hand_cases`): the sibling-combinator test `matches-adjacent-and-general-sibling-combinators` (core_test.cljk:1140) flattened by hand, `div` vs `#hero` with and without
`!important` (core_test.cljk:1807, 1887), source-order ties both ways, selector lists with an entry per selector, inheritance of `color`/`font-size` and
non-inheritance of `padding`/`display`/`cursor`, a descendant selector that needs backtracking, user-agent below author. Both the reference and the
kernel modules reproduce every one.

## What the gate ran (this machine, 2026-11-06)

`PASS_NATIVE_CSSOM_STYLE_K` (gate `lib/kotoba.cssom/scripts/check-style-k-native-macos.py`, receipt in `measurements.json`) and, inside it, `PASS_NATIVE_STYLE_K_QEMU` (observer `check-native-style-qemu.py`, profile `style` of `build-native-desktop-macos.py`, state `MACOS_NATIVE_STYLE_K_QEMU_CANDIDATE`). **Run**, not read: native macOS Amu `e13a2054...` / `amu-full-root` `88623412...`, QEMU 10.0.3 TCG.

* **Grid: 403 cases**: 34 hand-derived + 1 (input at bound), 93 component trees with the real sheet, 93 the same with a synthetic user-agent sheet, 120 seeded random, 27 capacity (one on each side of each bound), 22 semantic refusals, 14 malformed streams. 354 run, 49 are refused with the expected code (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13).
* **Kernel against reference: 374 cases equal** (sum or refusal code); the 29 not run through the reference are the malformed/raw streams, the capacity "past" cases, the 16384-byte input pair and the non-ASCII selector. All 403 equal the case table (status, element count, hand-derived sum). The reference equals the 34 hand-derived sums and 21 refusals.
* **Sheet equivalence**: the native hash of `(styles)` equals the hash of the grid's sheet text (15 rules, 835 bytes).
* **Negative controls (4 rebuilt kernels, builder exit 1, observer FAIL)**: intern fold (3 cases differ from the table, 3 from the reference), selector specificity (3 / 6), match descendant mask (2 / 20), cascade order (4 / 24). Each anchor occurs once.
* **Bounds chosen**: 128 elements, depth 32, 8 classes per element, 4 per compound, 8 compounds per selector, 256 compounds, 128 selector entries, 512 declarations, 16 properties, 511 strings, 4096 pool bytes, 16384 input bytes; window 61440 bytes.
* **Text bytes, kernel-v1 (cumulative compile, every export reached)**: intern_k 17,393; selector_k +28,773 (46,166); match_k +25,904 (72,070); cascade_k +27,188 (99,258) over 412 code lines = 257 bytes per code line (Q6 scalar slices: about 160). Kernel-v3 image of the profile: text segment 2,606,592 bytes against 2,471,936 for the `imgsig` profile built the same day (+134,656, includes the entry's fw_cfg glue); estimated margin 484,000 bytes; 54 modules locked (50 + the four).
* **x86_64-aiueos-user-v1**: refused for every module, with a 0-argument and a 2-argument entry, `E2101 unknown or unsupported form 'kernel-load-u32-4k' (byte 53)` (no region accessor exists there). A six-parameter function is refused on kernel-v1 with `E7102` detail 1.
* Pipeline cost, not measured on hardware: the whole grid (403 cases, about 800 KiB through fw_cfg) ran inside one QEMU boot.

Files: `measurements.json` (the receipt without input pins). Re-run: `python3 -I lib/kotoba.cssom/scripts/check-style-k-native-macos.py --amu ... --amu-full-root ... --amu-source ... --owner-repo-root ... --qemu ... --firmware ... --output NEW` (about 12 minutes; `--reuse-baseline DIR` skips the baseline build).


## Code against documents (reported, nothing in a document edited)

* `core.cljk:8031` `inherited-properties` says it is "the whole of what `unset` needs"; the hosted engine does not inherit values in the cascade at all: `layout.cljk`
  carries `(or (:color st) (:color inherited))` per property (7672, 12565, 18158). This slice applies the 37-name list to every property, which is
  the engine's own statement of what inherits, not what layout does today.
* `core.cljk:3586` docstring and CSS Selectors 4: `#a#b` is two ids; the code keeps `(first ids)`. Transcribed as the code (`first-id-only-*` cases).
* `core.cljk` `parse-simple-selector` silently skips characters it does not know (`a%`); this slice refuses them.
* `core.cljk` `selector-parts` accepts a leading or trailing combinator and `a > > b`; this slice refuses them (status 12).
* The task text says the trees come from `ui_components_test.kotoba`; that file holds the rendered HTML of each component as string literals, not the
  Hiccup values, so the trees here are those strings parsed (a fragment with two roots gets a synthetic `div`). The test is expected to print 42 (not re-run here).

## Not verified

* No CPL3 execution; the region code runs in the kernel image of the QEMU profile only. `x86_64-aiueos-user-v1` refuses it at the first region form.
* The reference could not be compared with the hosted `core.cljk`; fidelity rests on the hand-derived cases and the code read.
* `layout.cljk`, `@layer`, `@scope`, media queries, shorthands, inline style, `var()` are not modelled; no per-property initial value exists.
* Real elapsed time of the pipeline on hardware, and a draw list: nothing here produces one.
