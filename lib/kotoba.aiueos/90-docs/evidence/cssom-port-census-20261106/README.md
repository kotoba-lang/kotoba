# CSSOM render-closure port census for the user-domain, fixed-point target (JUN-134 / JUN-135 / JUN-855)

Date: 2026-11-06. Base: kotoba `main` at `e5f6d60a8`. Analysis and prototypes only; no source file of the libraries is changed.
Input decisions: ADR-0287 and its Amendment 1 (pull request #1248, read from branch `claude/jun-855-adr0287-fixed-point`, not yet on `main`),
`render-closure-size-20261105/README.md`, evidence #1246 (user targets refuse floats, `E7101` detail 33 / 36).

Every claim is tagged **[M]** measured (a command or program was run and its output is in this directory), **[R]** read from source, or **[E]** estimate / proposal.
Tools: `rg` (ripgrep; `ugrep` is not installed), Python 3 only as a scanner and driver, the pinned native Amu macOS binaries
(`amu-cli.macho` sha256 `e13a2054...2b02`, `amu-full-root.macho` sha256 `88623412...a229`, from `wt/claude/amu-merged` at `385bab04`).
No JVM, nbb or babashka was run. "Hosted oracle" below means either the existing native f64 `.kotoba` slices run on macOS arm64, or IEEE doubles (Python `float`
equals Java/JS `double` for `+ - * /`), never the cljk code itself.

## 0. Headline numbers

| | number | tag |
| --- | --: | :-: |
| Float-bearing hits in the closure (double / parse / `Math/` / float literal / typed f64 op), comment- and string-stripped scanner | **229 hits on 144 distinct lines** (layout 177, core 41, text 7, color 3, htmldom 1; see 2.1) | M |
| ... of which `Math/` calls | 34 (layout 32, text 2, core 0) | M |
| ... of which already f64 inside a `#?(:kotoba ...)` branch of `cssom.core` | 11 | M |
| Secondary real-number evidence: `(/ ...)` 55, `(long ...)`/`(int ...)` 71, `quot/rem/mod` 27, `number?`-style tower checks 36 (round/floor/ceil identifiers 10 not included) | 189 | M |
| Regex literals in cssom core+layout / htmldom / css / html | 107 / 11 / 15 / 3 = **136** (106 distinct in all scanned files incl. dom-gpu and text) | M |
| ... classes (a) hand scanner / (b) `bounded_regex` / (c) other | 96 / 39 / 1 | M (classifier is a heuristic, see 3) |
| Real code in the closure (comments and string contents removed) | **14,807 non-blank lines, 458 KB**, out of 1.94 MB / about 30k source lines | M |
| User-target text segment | **4096 bytes**, hard cap on every user target (`E7104`) | M + R |
| One 34-line fixed-point block-width solver | 5874 code bytes (user-v1 refuses it) | M |
| Measured text cost of that solver | 2.6 text bytes per code byte, 170 bytes per line | M (one point) |
| Estimate of the whole closure at that ratio | about 1.2 MB of text, 290 times the user text cap | E |
| 1,000,000-sample differential, Q6 vs existing f64 `block_width.kotoba` | 0 violations of 1/128 px, max difference 1 unit of 1/128 px, negative control 29,450 | M |
| Percent rounding, f64 oracle vs exact rational | 1114 / 1,233,197 differ (integer percent), 7391 / 122,908,097 (0.01 % steps); all are exact `.5` ties | M |

**Three findings change the plan, not just the cost:**

1. **No user target can hold a renderer, independent of floats.** All of `x86_64-aiueos-user-v1` to `v5` refuse strings (`E7101` detail 16), records and vectors (`E7102` detail 1), cap functions at five parameters
   (`E7102`), have no store primitive (`kernel-store-u32` is `E2101`), expose only a 64-byte request via `kernel-load-u32`, and emit **one 4096-byte text page** (`E7104`, seed/74 line 1891). [M]
   A 90-line CSS solver already overflows it. The ADR text speaks of "typed limits for heap-shaped code"; the text cap is not mentioned and is by itself decisive.
2. **The code, not the source, is what has to be ported: 14.8k code lines (458 KB), not 30k lines / 1.9 MB.** Docstrings and comments are 76 % of the bytes. [M]
3. **The "f64 hosted oracle" is itself inexact at exact ties.** Because `pct/100.0` and `x * 1.15` are not exact in binary, the hosted layout rounds or truncates one pixel low at exact
   decimal boundaries (29 % of 50 px = 14.5 gives 14). A fixed-point port that is arithmetically *correct* will differ from the oracle there. The bound has to be written as "equal except on exact ties", and an owner decision is needed on
   whether to match Blink or the oracle there (Blink's behaviour was not measured). [M]

## 1. Reproduction

Everything is regenerable from this directory (`scripts/`; they locate the libraries relative to the repository, and use `AMU_CLI` / `AMU_FULL_ROOT` for the compiler binaries):

```sh
python3 scripts/census.py sites-raw.tsv      > float-site-matrix.txt      # per file x category matrix
python3 scripts/groups.py sites-raw.tsv float-sites.tsv float-groups.tsv  # 229 / 144 / 199
python3 scripts/regex.py  regex-sites.tsv    > regex-matrix.txt
python3 scripts/heap.py   heap-census.tsv
python3 scripts/corpus.py corpus-literals.json
python3 scripts/trunc_oracle.py              > trunc-oracle.txt
python3 scripts/run_probes.py probe-results.tsv       # dialect probes, 132 compiler runs
python3 scripts/run_prototypes.py prototype-results.txt   # native macOS differential gates
```

The scanner (`scripts/strip.py`) removes `;` comments and blanks the contents of string and regex literals, so words such as the CSS keyword `double` in a docstring or in `"double"` property sets do not count.
Raw greps over-count, which is why both are given (all run from `lib/`, Linux/macOS `rg`):

| command | core.cljk | layout.cljk | htmldom | color.cljk | dom.cljk | surface.cljk |
| --- | --: | --: | --: | --: | --: | --: |
| `rg -c '\bdouble\b\|Math/' FILE` (lines, raw) | 22 | 51 | 2 | 4 | 0 | 0 |
| `rg -c '\(double[ )]\|Math/' FILE` (code-shaped) | 3 | 37 | 0 | 0 | 0 | 0 |
| `rg -c --pcre2 '(?<![\w.])[0-9]+\.[0-9]+(?![\w.])' FILE` (lines with a decimal literal, raw) | 60 | 263 | 2 | 2 | 0 | 0 |
| scanner, strong hits (F1+F2+F3+F9) | 41 | 177 | 1 | 3 | 0 | 0 |

ADR-0287 says "JUN-854 counted 58 float sites in cssom (`double`, `Math/`) and 4 in dom-gpu". **I could not reproduce 58**: raw is 73 lines for cssom (22 + 51, most are the word "double"), code-shaped is 40, and dom-gpu has 3 scanner hits, all in `host/color.cljk`
(`dom.cljk` has none). The census below supersedes that number (CLAUDE rule "code first": reported, the ADR text is not edited).

## 2. Float sites

### 2.1 Where, by file and kind [M] (`float-site-matrix.txt`, every row in `float-sites.tsv`)

| file | F1 double/parse | F2 Math/ | F3 float literal | F9 typed f64 | F4 `(/ ..)` | F5 `(long ..)` | F6 quot/rem/mod | F8 number? tower |
| --- | --: | --: | --: | --: | --: | --: | --: | --: |
| cssom/core.cljk | 18 | 0 | 12 | 11 | 4 | 4 | 3 | 15 |
| cssom/layout.cljk | 19 | 32 | 126 | 0 | 46 | 51 | 14 | 20 |
| htmldom/core.cljk | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| domGpu/dom.cljk, dom.kotoba, browser/surface.cljk | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| domGpu/host/color.cljk | 3 | 0 | 0 | 0 | 5 | 0 | 2 | 0 |
| browser/text_edit.kotoba | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| text/text.cljk (+ .kotoba, bounded_regex.kotoba) | 4 | 2 | 1 | 0 | 0 | 15 | 6 | 1 |
| **total** | 45 | 34 | 139 | 11 | 55 | 71 | 27 | 36 |

`Math/` by function [M]: `ceil` 11, `round` 7, `floor` 4, `tan` 4, `PI` 3, `cos` 1, `sin` 1, `sqrt` 1, `abs` 1, `pow` 1. The F9 sites are the existing f64 code inside `#?(:kotoba ...)`
(`css-decimal-f64`, `parse-media-length`, core.cljk 743-761, 5259-5260): the earlier port work already uses floats and has to move to fixed point too.
Surface, DOM and text-edit contain no float at all. The hosted code is dynamically typed: 36 `number?`/`integer?` checks branch on long versus double (for example `calc-result->number` returns a long when whole, otherwise a double,
core.cljk 1052-1060), a distinction that disappears in a fixed-point port. [M/R]

### 2.2 Groups [M counts, E proposals] (`float-groups.tsv`, `float-groups.json` has the full text)

Scale rule used: every product of two scaled operands is below 2^46. Lengths are **Q6** (1/64 px, the Blink LayoutUnit scale), `|raw| <= 2^30` (2^24 px); a factor multiplying a length must have `|raw| <= 2^15` (Q10), or the length is limited to 2^28 raw.

| group | hits | lines | what | needed range and precision | proposed scale | oracle error bound |
| --- | --: | --: | --- | --- | --- | --- |
| G01 decimal parse | 31 | 26 | text to number | px integer in 1564/1565 (cases.edn); unitless up to 6 digits; max 99999 px [M] | Q6 lengths, Q10 factors, 6 fraction digits kept | 2^-7 px per literal [M, 15 cases] |
| G02 percent / em | 22 | 16 | `percentage-of`, em, tracks | percent all integer, max 200; em 1 digit [M] | percent Q10, basis Q6 <= 2^25, one `quot` | equal except exact .5 ties; 1114/1,233,197 and 7391/122,908,097 pairs, 0 non-tie [M] |
| G03 calc | 4 | 4 | add/sub/mul/div | long-or-double result [R] | Q6, factors Q10 | 2^-7 px per op, nesting capped (E) |
| G04 colour | 3 | 2 | hex/rgb/hsl | floats 0..1 hosted; kernel wants u32 rgb [R] | 8-bit channels, hue Q6, s/l Q10 | +-1 per channel (E, not measured) |
| G05 transforms | 95 | 32 | 2D matrices, sin/cos/tan | round-4 output; **native f64 has no sin/cos/tan** [M] | coefficients Q17, local coords Q6 <= 8192 px | 2^-16 per coefficient, 0.125 px worst at 8192 px (E) |
| G06 line-height / metrics | 22 | 21 | multipliers, advances, ceil | fractional font sizes (13.3333) [R] | fs Q6, multiplier Q10, `>>16` | oracle one px low in 183/128,256 pairs (0.14 %) [M]; 0.6 and 1.2 clean [M] |
| G07 flex/grid/table/multicol | 22 | 18 | factor distribution | doubles for grow/shrink/fr [R] | Q6 space, Q10 factors, largest remainder | <= 1 px per item (E) |
| G08 aspect-ratio | 6 | 4 | replaced size | quotient of two ints [R] | keep integer pair, `quot` | exact |
| G09 vertical-align / inline | 2 | 2 | halves, % | | as G02 | 2^-7 px |
| G10 form step validation | 3 | 3 | `mod steps 1` tol 1e-9 | unbounded decimals [R] | defer; exact decimal rationals | behaviour change |
| G11 opacity / style numbers | 8 | 6 | opacity clamp, grow/shrink | 0..1 [R] | Q10 | 2^-11 per level |
| G12 proximity sentinels | 4 | 4 | `##Inf`, `(double hops)` | ordering only [R] | i64 sentinels | exact |
| G13 text number formatting | 7 | 6 | `fixed`, `format` | not render path [R] | defer | exact |
| **total** | **229** | **144** | | | | |

What this says about the port order: G01, G02, G03, G06, G07, G08 are plain integer arithmetic once the scale is chosen (107 hits, 89 distinct lines) and can be done with `quot` and shifts only. G05 (transforms)
needs trigonometry that the native f64 dialect does not have, so it needs its own fixed-point `sin/cos/tan` and a table-based oracle comparison. G04 changes the interface (u32 colour). G10 and G13 are outside the render path.

### 2.3 What a fixed-point oracle bound has to look like [M]

* Add/sub of Q6 values is exact; one rounding per multiplication or division; half of an odd Q6 raw loses 2^-7 px (the block-width gate showed exactly that and nothing larger).
* `percentage-of` (layout.cljk:3939) is `(long (Math/round (* basis (/ pct 100.0))))`. On a native macOS loop `prototype/pct_oracle.kotoba` computed it with f64 ops and compared with `floor((H*basis + 5000)/10000)`:
  integer percent 0..300 x basis 0..4096: **1114 of 1,233,197** differ; 0.01 % steps 0..300 % x 0..4096: **7391 of 122,908,097**; with the tie test `H*basis mod 10000 = 5000` excluded: **0** differ.
  First three integer-percent cases: 29 % of 50, 29 % of 750, 29 % of 850 (each is x.5; oracle rounds down).
* `(long (* multiplier font-size))` (layout.cljk:4817): 2-decimal multipliers 0.00..5.00 x font size 1..256 give 183 of 128,256 pairs one pixel low in doubles (for instance 0.29 x 100 = 28.999999999999996); `0.6` and `1.2` are clean for 1..4096 (`trunc-oracle.json`).
* Consequence: the oracle bound for lengths consumed as integers is "equal, except where the exact value is a half or an integer and the double product misses it by an ulp"; for Q6 results it is 2^-7 px per rounded operation.
  The conformance corpus compares against Blink via a real browser (`lib/kotoba.cssom/conformance`, 853 cases) mostly by line structure; it cannot arbitrate these ties offline.

## 3. Regex literals [M] (`regex-sites.tsv`, `regex-summary.json`, `regex-matrix.txt`)

Counted with the same comment/string-stripping scanner: a `#"` literal that sits in code. Raw `rg -c '#"'` (lines, includes docstrings): core 43, layout 67, htmldom 11, css 15, html 3.

| file | literals | distinct | (a) scanner | (b) bounded_regex | (c) other | calls: `re-find` / `re-matches` / `re-seq` / `re-pattern` / `str/replace` / `str/split` |
| --- | --: | --: | --: | --: | --: | --- |
| cssom/core.cljk | 39 | 37 | 29 | 10 | 0 | 3 / 28 / 7 / 2 / 7 / 0 |
| cssom/layout.cljk | 68 | 39 | 46 | 21 | 1 | 7 / 28 / 3 / 1 / 7 / 27 |
| htmldom/core.cljk | 11 | 11 | 6 | 5 | 0 | 1 / 4 / 1 / 0 / 1 / 2 |
| css/{core,utility,build}.cljk | 15 | 14 | 12 | 3 | 0 | 1 / 8 / 1 / 0 / 5 / 1 |
| html/core.cljk | 3 | 3 | 3 | 0 | 0 | 3 / 0 / 1 / 1 / 4 / 0 |
| **scope total (asked files)** | **136** | | **96** | **39** | **1** | |
| domGpu host/color.cljk, text.cljk (closure, outside the ask) | 10 | 9 | 8 | 2 | 0 | |

Layout: 68 literals, 39 distinct (the progress note's "67 occurrences across 39 patterns" counts lines; line 4413 holds two literals). `kotoba.lang.bounded-regex` supports **only** a group-free subset: top-level alternation, `^`/`$` anchors,
`* + ?`, `.`, bracket classes, `\d \w \s` and their negations (ASCII only), at most 60 pieces; it refuses `( ) { }`, lookaround, flags, backreferences and gives matching, `regex-find-index`, `regex-match-end` and `regex-count`
but **no captures, split or replace** [R, `bounded_regex.kotoba` header]. Feature totals over the 136 literals [M]: plain 75, capture group 44, alternation inside a group 26, non-capturing group 23, inline flag `(?i)`/`(?s)` 22,
word boundary 2, lazy 2, lookahead 2, counted repeat 1, hex escape 1, lookbehind 1.

Classification rule (heuristic, in `scripts/regex.py`): (c) backreference, `\p{}`, lookbehind. (b) no group, counted repeat, lookaround, boundary, lazy, flag or unicode class, **and** the literal is used only in a test/find/match (not `re-seq`, `split`, `replace`).
(a) everything else. Every (b) literal is also (a): a scanner over `string-code-point-at` can replace any regex here, because every grammar is a tokenizer.

Five representative cases:

| class | where | pattern | use |
| --- | --- | --- | --- |
| (b) | `layout.cljk:3882` | `\s*-?[0-9]*\.?[0-9]+%\s*` | `re-matches`; 7 pieces, group-free; note `\s` is ASCII-only in bounded_regex, the host `\s` includes Unicode spaces |
| (b) | `core.cljk:1130` | `-?\d+` | `re-matches` (also lines 1492, 4551, 5713, 6388 and `layout.cljk:6219`) |
| (a) | `layout.cljk:674` | `\s+` | `str/split`; 27 such splits in layout; a whitespace splitter loop (about 10 lines) covers all of them |
| (a) | `layout.cljk:3937` | `\s*(-?[0-9]*\.?[0-9]+)%\s*` | capture of the number before `%`; needs a scanner that returns the span (the same decimal grammar recurs at layout 4742, 4830, 12502, 12538, 17624 and core 4521, 5226, 9078) |
| (a) | `core.cljk:2826` | `\[\s*(name)\s*(?:(~=\|\|=\|\^=\|\$=\|\*=\|=)\s*(?:"..."\|'...'\|bare))?\s*\]` | attribute selector with 5 captures and alternation: a small state machine |
| (c) | `layout.cljk:18004` | `(?=\s)\|(?<=\s)` | zero-width split between whitespace and non-whitespace: not expressible in either; a scanner emits boundaries directly |

Also (a) but worth a note: `core.cljk:2913` `(?i):(not|is|where|has)\(((?:[^()]|\([^()]*\))*)\)` needs one level of balanced parentheses (a depth counter), and `core.cljk:6144` is an e-mail pattern with `{0,61}` counted repeats that should leave the render closure.
The bounded-regex route has an existing precedent: `cssom.core` already requires it for 2 call sites (core.cljk:443-450, 6065). [R]

## 4. Heap-shaped data and the dialect that exists today

### 4.1 What the closure builds [M counts, `heap-census.tsv`]

| construct (stripped code) | cssom core | cssom layout | htmldom | domGpu (dom, dom.kotoba, color) | surface | text (text.cljk, text.kotoba, bounded_regex) |
| --- | --: | --: | --: | --: | --: | --: |
| top-level `defn` | 359 | 312 | 59 | 55 | 24 | 136 |
| map literals `{`  | 155 | 312 | 16 | 10 | 37 | 9 |
| set literals `#{` | 112 | 90 | 43 | 4 | 0 | 2 |
| `assoc/update/merge/dissoc` family | 66 | 196 | 5 | 22 | 23 | 0 |
| `conj/into/vec/mapv/concat/...` | 147 | 418 | 48 | 15 | 10 | 44 |
| keyword-as-function lookups `(:k m)` | 466 | 1557 | 22 | 22 | 57 | 26 |
| seq HOFs (`map filter reduce sort-by group-by ...`) | 238 | 415 | 33 | 16 | 12 | 11 |
| `loop`/`recur` | 283 | 142 | 54 | 0 | 0 | 110 |
| `atom swap! reset! volatile!` | 4 | 6 | 0 | 0 | 0 | 11 |
| string ops (`str subs str/...`) | 796 | 248 | 58 | 22 | 5 | 93 |
| typed collections (`typed-set-new`, `typed-list-*`) | 80 | 0 | 0 | 0 | 0 | 16 |

Shapes (unbounded in principle unless a bound is cited):

* **Document tree** (`kotoba.wasm.dom`): node maps with children vectors. The typed `:document` form in `dom_core.kotoba` is bounded by construction: each vector at most 32 elements, seven tail batches, 256 operations in all [R, dom_core.kotoba:81-83]. Node count has no bound stated in the hosted `dom.cljk`.
* **Style map per node**: `node-style` (layout.cljk:2827-3479) returns one map with about 143 distinct keys [M, heuristic count]; a record of that width does not fit the native record slice (see 4.2).
* **Cascade**: sorted rule lists, specificity, selector ASTs (nested vectors of maps), counters map threaded through the tree walk, custom-property environment (map). Unbounded by input.
* **Layout output**: a vector of op maps (`{:op :rect :x ... }`, `:node` ops with optional `:hit` rect lists). The consumer budget is 259 draw ops [R, ADR-0287]; the producer has no cap of its own.
* **Inline layout**: line boxes, fragments, run lists; 142 `loop` sites iterate over text. Unbounded by text length.
* **Closures as data**: the theme map carries host functions (`:measure-text`, `:font-metrics`, `:avg-advance`; 34, 11 and 3 mentions in layout.cljk). Function values do not exist in user targets.
* **Bounded already**: `bounded_regex` (60 pieces, i64 bitmask), the `:document` vectors (32), `margin_collapse` (two extrema), `block_width` (13 scalars in, 4 out).

### 4.2 What the dialects admit [M] (`probe-results.tsv`, sources in `probes/` and `prototype/`, compiler = `amu-full-root.macho --target`)

| probe | host `amu check` | kernel-v1 object | user-v1 | user-v2 / v5 |
| --- | --- | --- | --- | --- |
| scalar `:i64` arithmetic, `loop/recur`, helper `defn`, keywords, bit ops, `i64-shift-*` | ok | ok | **ok** | ok (needs a 2-argument `main`; a zero-arity entry is `E7102` detail 2, which masks every other verdict in those columns) |
| i64 product of two 2^46 values (`t03`) | ok | ok | ok | | 
| `quot` | ok | ok | **ok** | ok |
| `rem`, `mod` | ok | ok | **`E2101`** | `E2101` |
| `/` | `E2101` | `E2101` | `E2101` | `E2101` |
| string literal, `string-length`, `string-code-point-at` | ok | **`E7101` detail 16** | **`E7101` detail 16** | `E7101` detail 16 |
| record (`:schemas`, `record-get`) | ok | `E7102` detail 1 | `E7102` detail 1 | `E7102` detail 1 |
| vector as parameter (`:vector-i64`) | | `E7102` detail 1 | `E7102` detail 1 | `E7102` detail 1 |
| `typed-vector-new` | `E2101` | `E2101` | `E2101` | `E2101` |
| f64 (`f64-lt`, `f64-mul`) | ok | **ok** | `E7101` detail 9 (33 / 36 for arithmetic, per #1246) | `E7101` |
| function with 5 / 6 parameters | | ok / `E7102` | ok / `E7102` detail 1 | |
| `kernel-load-u32` (request region) | `E2101` | ok | `E2101` | **ok** |
| `kernel-load-u8/u16/u64`, `kernel-subregion` | `E2101` | ok | `E2101` | `E2101` |
| `kernel-store-u32` | `E2101` | ok | `E2101` | **`E2101`** |
| 16 / 18 tiny functions (text size) | | | ok / **`E7104` detail 4394** | v2: ok / `E7104` (4490); v5: 16 already `E7104` (4113) |
| 34-line fixed-point block-width solver | ok, `prototype-results.txt` | ok, text 6226 B | **`E7104` detail 5874** | |
| decimal px parser over the 64-byte request (`px_parse_q6_user`) | | text 4240 B | | **ok** (v2, v5) |

Reading the compiler: user ELF is `(> (xg-pos g) 4096)` then `E7104` [R, seed/74 line 1891]; `xu-input-lib` declares only `kernel-load-u32` (and `kernel-local-model-call` for v3) [R, seed/74 1812]; the header comment says
"zero-argument scalar slice ... no heap, no runtime" [R, 1770, 1923]. The existing kernel-object route (`browser-frame.kotoba`) shows the pattern that does work today: words in a bounded u32 state window,
`kernel-subregion` + `kernel-load/store-u32`, at most five parameters, "Remove this layout when native has maps" [R].
The host-native macOS profile is far richer (strings, records, typed lists/sets, `:document`) and runs the existing f64 `cssom/*.kotoba` slices: all three native tests print 42 [M]. That profile is not a user target.

**What I could not determine here:** whether the planned per-window arena (ADR-0287) has any compiler support; there is no allocator, no `kernel-store-*` and no multi-page text in any user target, so the arena and the draw-list region
written by the renderer have no expression today. The ADR's "shared regions" boundary needs `store` primitives and a larger text segment first. I did not boot anything under QEMU: user-target results are compile verdicts, not CPL3 executions.
The "i64 product rule" (2^46) is not in the compiler I searched (seed/21-check, 74, 75 and `docs/adr`): `t03` compiles a product of two 2^46 values on user-v1, and on the host `2^62 * 2^40` wraps silently to 0 (measured with `amu run`). I treated 2^46 as the owner's rule.

## 5. Proposed first port slice

**Slice 1: Q6 lengths with block-width and margin collapse, scalar i64 only.** It is the smallest vertical that exercises every part of the approach: decimal parsing from bytes, exact percent rounding, the long-vs-double collapse, the range guard
replacing `finite?`, the five-parameter limit, the single result register, the text cap and an f64 oracle that already exists and passes natively.

Modules (new files under `lib/kotoba.cssom/src/cssom/`; nothing is wired into `layout.cljk` yet):

| file | content | f64 oracle |
| --- | --- | --- |
| `length_q6.kotoba` (`cssom.length-q6`) | Q6 constants and guards, `resolve-px`, `resolve-percent` (exact half-up rational), kind codes | `length.kotoba` (native f64) and `layout.cljk` `percentage-of` (3939) |
| `parse_px_q6.kotoba` | `[+-]digits[.digits][px]` and `%` scanner over request bytes, 6 fraction digits | `prototype/px_parse_q6_host.kotoba` (15 cases against Decimal) |
| `block_width_q6.kotoba` | `solve` and `solve-constrained`, inputs packed 2 x 31 bit per i64, `sel` picks one of four outputs | `block_width.kotoba` (native f64, existing) |
| `margin_collapse_q6.kotoba` | positive/negative extrema state packed in one i64 | `margin_collapse.kotoba` (native f64, existing) |
| `block_style_q6.kotoba` | bridge from resolved style lengths to the solver (percent against the containing width) | `block_style.kotoba` (native f64, existing) |

Oracle choice: **the four existing native f64 `.kotoba` modules** (165 source lines, they run on macOS arm64 and print 42 today [M]), not the cljk and not the conformance corpus. The corpus needs a real browser and a JVM/nbb runner, and mostly compares
line structure. Stage 2, after the slice is wired into layout, is the conformance ledger as a local one-off oracle under the AGENTS.md rule (recorded as data, not in CI).

Gate shape (copy of `lib/kotoba.html/scripts/check-ui-components-native-macos.py`): new `lib/kotoba.cssom/scripts/check-block-q6-native-macos.py`:

1. pin the Amu digest and the sha256 of every input, require native macOS arm64, empty `PATH`, `LANG=C`;
2. write a KSL2 source lock (`scripts/runnative.py` here is the working model) and `amu compile ENTRY --source-lock` the test `lib/kotoba.cssom/test/native/block_width_q6_vs_f64.kotoba`
   (the 1,000,000-sample differential from `prototype/q6_vs_f64_test.kotoba`), run it, require stdout `42\n` and an empty stderr;
3. negative control: replace a mutation anchor (`half (i64-shift-right remaining 1)` becomes `... 2)`) and require a **non-42** result (here 29,450 violations) [M];
4. add the percent block: exact rounding vs oracle must differ **only** on tie cases (the `H*basis mod 10000 = 5000` test) and the tie list must equal a pinned count (7391, 1114);
5. AIUEOS compile gate: `amu-full-root.macho compile --target x86_64-aiueos-user-v2` for the scalar entry points that fit, requiring `:ok true`, and a refusal control (six parameters must be `E7102`);
6. emit `receipt.json` with all digests, the compile verdicts and the counts. It does not claim CPL3 execution.

Measured prototype results (`prototype-results.txt`) [M]:

| check | result |
| --- | --- |
| existing f64 `test/native/{block_width,margin_collapse,block_style}.kotoba` | 42, 42, 42 |
| Q6 block-width vs f64, 1,000,000 Q6-grid samples | 0 violations of 1/128 px; max difference 1 unit of 1/128 px; 1,000,000 valid on both sides |
| negative control (`half` shifted by 2) | 29,450 violations |
| Q6 px parser (host twin of the user-v2 program), 15 cases | 42; ties beyond the 6th digit truncate (`0.0078125px` gives 0, documented) |
| user-v2 / v5 compile of the px parser | ok |
| user-v1 compile of the packed 5-parameter solver | `E7104` detail 5874 (over the 4096 text cap) |
| same solver on kernel-v1 object | ok, text 6226 B (170 B per source line) |

The range-guard branches (`invalid`) were not exercised by the random draws (all 1,000,000 samples were valid on both sides); the gate must add explicit overflow cases.

Risks, most severe first:

1. **Text cap.** A 4096-byte user text page cannot hold even the solver (5874 B). Either the user target needs a larger or multi-page text segment, or the renderer is not a user ELF in the current sense. This blocks every slice larger than a parser, regardless of fixed point. (M)
2. **No stores, strings, records or regions in user targets.** The renderer cannot write a draw list, read a document, or keep a style map. The ADR's shared-region boundary needs compiler work first (new primitives, new target version). (M)
3. **Oracle ties.** Exact fixed-point arithmetic disagrees with the f64 oracle on exact half/integer boundaries (0.09 % of integer-percent pairs). Decide whether the contract is "equal to the oracle" (not achievable without floats) or "within the bound, ties exact". Blink was not measured. (M)
4. **Five-parameter limit and one result register** force packing of 13 inputs and 4 outputs (layout.cljk:1502 documents a function that reached Clojure's own 20-positional-parameter limit, which cannot be expressed here). Packed words hide errors; the gate must fuzz the packing. (M)
5. **Dynamic typing disappears.** 36 tower checks (`number?`, long vs double) and 143-key style maps must become fixed schemas. (M)
6. **Trigonometry** has no native f64 oracle (no `f64-sin/cos/tan`); transforms (95 hits) need a table-based oracle. (M)
7. **Host hooks** (`:measure-text`, `:font-metrics`) are closures; the native replacement is a font table in a region, which the user targets cannot read beyond 64 bytes. (R)
8. **Overflow policy.** The host wraps silently on i64 overflow (measured); the guards must be explicit, and the compiler accepted an unguarded 2^46 x 2^46 product. (M)
9. **Existing `:kotoba` branches in `cssom.core`** (176 lines) target the typed host dialect with f64 and typed sets; they are not a head start for user targets. (M/R)

## 6. Could not determine

* Whether any user target will gain stores, strings or a larger text segment (no plan found in `docs/adr` or `seed/`); user-v3 and user-v4 were not probed separately (v2 and v5 stand for the family).
* Real CPL3 execution of any program above (compile verdicts only; the Mac has `qemu-system-x86_64` but I did not boot an image).
* The Blink-correct result at the exact-tie cases of section 2.3.
* The per-document bounds (node count, nesting depth, text length): the hosted code has none, and the ADR's 259-op draw budget is the only output bound I found.
* The 58-site figure in ADR-0287 (not reproducible, see section 1).
* Colour and flex/grid error bounds (G04, G07) are proposals, not measurements; transform bounds are analytic.
* The source of the "i64 product rule" (2^46); not found in the compiler sources searched.

## 7. Document / code mismatches (reported, nothing edited)

1. ADR-0287 Amendment 1, "58 float sites in cssom ... 4 in dom-gpu": not reproducible (section 1); layout has 177 and core 41 strong hits, dom-gpu 3.
2. ADR-0287 Consequences cites "the user-target compile limits seen in ADR-0019 for heap-shaped code" as unmeasured; measured here: the 4096-byte text cap, no strings/records/stores, five parameters. ADR-0019 line 50 only records the typed-values refusal.
3. `render-closure-size-20261105/README.md` says none of the cssom modules is canonical `.kotoba`: four are (`length`, `block_width`, `block_style`, `margin_collapse`: 165 source lines plus three native tests, JUN-135), though none is required by `layout.cljk` [M: no `require`].
4. The same README sizes the closure by source bytes (1.78 MB); code bytes are 458 KB (14.8k lines) [M]. Its 0.76 and 3.4-4.1 B/B bracket was for whole graphs and dense kernel code; the one cssom-shaped point measured here is 2.6 B per code byte.
5. `shared-browser-native-progress.md`: "67 regex occurrences across 39 patterns" is right for lines and distinct patterns (68 literals, one line has two).

## 8. Files

* `float-sites.tsv` (428 rows, each with group), `float-groups.tsv`, `float-groups.json`, `float-site-matrix.txt`
* `regex-sites.tsv` (146 rows), `regex-summary.json`, `regex-matrix.txt`
* `heap-census.tsv`, `closure-code-size.json`, `corpus-literals.json`, `corpus-summary.txt`, `trunc-oracle.json`, `trunc-oracle.txt`
* `probe-results.tsv` (132 compiler runs), `probes/` (31 sources), `prototype/` (8 Kotoba sources), `prototype-results.txt`
* `scripts/` (measurement drivers; Python is a scanner and process driver, all code that is compiled is Kotoba)
