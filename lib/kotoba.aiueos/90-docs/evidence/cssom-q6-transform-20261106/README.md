# CSSOM Q6 slice 4: CSS transforms (census group G05) in fixed point (JUN-929 / C2b-4)

Date: 2026-11-06. Base: kotoba `main` at `45e971a98` (branch `claude/jun-929-q6-transform`). Source files added under `lib/kotoba.cssom`; no `.cljk` is changed.
Decisions in force: ADR-0287 and amendment 1 (Q6 lengths, D4 multipliers, round half up `floor(x + 1/2)`, scalar i64, at most five parameters per
function, products below 2^46, no floats / records / strings / `/` / `rem` / `mod` in the arithmetic core).
Every claim is tagged **[M]** measured (a command ran, its output is below or in the gate receipt), **[R]** read from source, or **[E]** estimate.
Tools: the pinned native Amu macOS binaries (`amu-cli.macho` sha256 `e13a2054...2b02`, `amu-full-root.macho` sha256 `88623412...a229`); Python 3.15.0
only as a one-off oracle / generator and as the gate driver. No JVM, nbb or babashka.

## 0. What this slice is, in one paragraph

Census group G05 is 95 strong float hits, all in `layout.cljk` 17593-18130 (`identity-matrix`, `matrix*`, `round-4`, `transform-*`, `apply-element-transform`,
`flow-rotation`). This slice replaces them with two scalar-i64 `.kotoba` modules: `cssom.trig-q6` (sin, cos, tan of an angle) and `cssom.transform-q6` (the 2D affine
matrix algebra). **The native f64 dialect has no sin / cos / tan, so there is no native runtime oracle**; the reference is DATA produced once by Python
(`math` for the trig table, `fractions.Fraction` for the matrix algebra), pinned by sha256, and the gate compares the fixed-point result with that data.
Verdict string of the new gate: `PASS_NATIVE_CSSOM_TRANSFORM_Q6` [M, section 9].

## 1. Mismatches between the task / census text and the code (code beats docs; reported, nothing edited)

1. **There is no 4x4 matrix in `layout.cljk`.** The task text asks for a 4x4 multiply, 2D/3D constructors, invert and decompose "as far as layout.cljk needs them". Read
   from source [R]: the matrices are 2D affine, six numbers `[a b c d e f]` composed by `matrix*` (17595); `transform-function-matrix` (17664) returns `nil` for
   `matrix3d`, `perspective`, `rotate3d`, `rotateX`, `rotateY` and the whole declaration is then dropped; `translate3d`, `scale3d`, `translateZ`, `scaleZ`, `rotateZ` are accepted as their 2D projections. There is no
   inverse and no decomposition: `flow-rotation` (17943) inverts a signed permutation by its determinant +-1, and the only root is `sqrt|det|` for the font size (17854).
   So the port has no 4x4 multiply, no invert, no decompose. That would be code `layout.cljk` does not contain.
2. **The census proposed scales are narrower than what fits.** G05 row: coefficients Q17 with `|c| <= 8` (raw 2^20), coordinates Q6 `<= 8192 px` (2^19 raw), estimate "0.125 px worst at 8192 px".
   With the 2^46 product budget, coefficients up to `|c| < 64` (raw < 2^23) and coordinates / translations up to 65536 px (raw <= 2^22) fit, so that is what is implemented
   (a tan limit of 8 would refuse `skewX(83deg)`, which is plausible CSS). The census error estimate holds for rotate * scale (measured 8.25 Q6 ulps = 0.129 px at the 8192 px class) and is **exceeded for
   skew * rotate** (24 Q6 ulps = 0.375 px at the same class, because the skew coefficient reaches 11 in the sample and amplifies the coefficient error) [M, section 5].
3. **The task text lists `pow` among the G05 `Math/` calls; it is not there.** The G05 strong `Math/` hits are tan 4, PI 3, cos 1, sin 1, sqrt 1, abs 1, round 1 (the `round-4`) [M, `float-sites.tsv`];
   the one `Math/pow` of the census is in group G13 (`fixed`, text number formatting). Strong hits per enclosing definition are in `coverage-g05.tsv` (95 in total, none unmapped).
   `flow-rotation`'s four `(/ x det)` sites are secondary hits (division), not strong; they are ported anyway (`flow-rotation`).
4. **Hosted behaviour that the port deliberately does not reproduce** (a documented difference, not a bug): `rotate(1e9deg)` is computed by the host (any real), here refused beyond 32 turns;
   `skew(90deg)` gives `tan = 1.6e16` in doubles and a degenerate matrix, here refused for `|tan| >= 64`; coordinates beyond 65536 px and intermediate translations beyond 65536 px are refused, not wrapped.
5. `layout.cljk`'s `transform-number` accepts exponent forms (`1e3`); a D6 integer from the host scanner cannot carry one. The number scanner is the host's (see section 8).

## 2. Method

### 2.1 Fixed point and domain [R/M]

| value | scale | range (raw) | why |
| --- | --- | --- | --- |
| matrix coefficients a b c d, tan, sin, cos results | Q17 (1.0 = 131072) | `|raw| < 2^23` (`|c| < 64`) | product of two < 2^46; 13x finer than the oracle's own 1e-4 rounding (`round-4`) |
| translations e f, coordinates, lengths | Q6 (1/64 px) | `|raw| <= 2^22` (65536 px) | coefficient x coordinate < 2^45 |
| angle | `(unit, v)`: unit 1 deg, 2 grad, 3 rad, 4 turn; `v` = D6 integer (millionths of the unit) | `|angle| <= 32 turns` | `|v| <= 11,520,000,000 deg / 12,800,000,000 grad / 201,061,929 rad / 32,000,000 turn` |
| a CSS `<number>` (scale(), matrix()) | D6 in, Q17 out (`coef-of-number`) | `|v| <= 2^30`, result `|c| < 64` | one rounding |
| internal trig | Q30 | `|x| <= 2^30` | `mulq` keeps every multiplication below 2^46 |

Out of domain: **every function answers the sentinel `-2^62`** (`invalid`), which is not a valid pack, so it propagates. Nothing wraps, truncates or reduces silently.

### 2.2 sin, cos, tan: exact reduction + polynomial in Q30

Chosen over CORDIC (sequential table + 30 iterations, no gain in accuracy) and a table with interpolation (needs arrays; the user targets have no store). A polynomial is pure arithmetic.

1. **Quadrant reduction in integers.** deg, grad and turn reduce exactly (`quarter` = 90e6 / 100e6 / 250000 units, `fdiv`), so `90deg`, `100grad`, `0.25turn`, `-0.25turn`, `180deg` are exact quadrant edges and `cos = 0` exactly.
   rad reduces with `P16 = round(pi/2 * 10^6 * 2^16) = 102943708073` (pi from Machin's formula in the generator); the residual error is below 2^-17 micro-radian per quarter, 1e-9 rad at 32 turns.
2. The residual is folded to `[0, pi/4]` (exact for deg/grad/turn), converted to radians in Q30 with one multiplication by a constant rounded to 30 bits (`628821134`, `565939020`, `884279719`, `15625`-division for rad).
3. `sin` through theta^11, `cos` through theta^12 by a fixed Horner chain in `u = theta^2`, each step `1 - u*w/d` with `d` a small integer (6, 20, 42, 72, 110; 2, 12, 30, 56, 90, 132); first omitted terms are below 1e-11 on `[0, pi/4]`. Every product is `mulq(x, y, s) = round(x*y / 2^s)`, **exact** (y split at bit 15, both partial products below 2^46).
4. The quadrant and the fold swap and negate; the Q17 answer is the Q30 value rounded half up.
5. `tan = sin / cos` by a two-step long division to Q17, refused when `cos = 0` or the rounded `|tan|` reaches 2^23 raw (`|tan| >= 64`, i.e. within 0.895 degrees of 90).

### 2.3 Matrix algebra [R]

A matrix is three packed i64 (`cssom.pack-q6`, two signed 32-bit fields each): `ab`, `cd`, `ef`. `mul-ab / mul-cd / mul-ef` (3, 3, 4 parameters), `about-ef` (the `T(c) x M x T(-c)` conjugation of `apply-element-transform`
in **one** rounding), `map-x / map-y`, the corner bounding box `xs-min / xs-max / ys-min / ys-max / bbox-x / bbox-y / bbox-w / bbox-h`, `uniform-scale` (`sqrt|ad - bc|` by a 23-step unrolled bitwise integer root, `isqrt`, no loop),
`font-scale`, `origin-coord` (centre, keywords, length, percent), `flow-rotation` + `flow-ab` / `flow-cd` (the eight signed permutations coded 0..80), constants `ident-*`, `orthogonal-fallback` (1e7 px = 640,000,000 Q6).
Each output is a sum of products accumulated exactly and divided **once** (`rdiv`, half up). The oracle rounds every output to 1e-4 px (`round-4`); here the output is Q6 (0.0156 px), coarser by design (ADR-0287).

## 3. The golden data (one-time oracle runs)

| | command (run from this directory) | tool | output | rows |
| --- | --- | --- | --- | --- |
| trig table | `python3 scripts/gen_trig_golden.py .` | Python 3.15.0, `math.sin / cos / tan` (+ an independent exact series: pi by Machin, Taylor in 10^70-scaled integers, no `math`) | `trig-golden.tsv`, `trig_golden.kotoba`, `trig-golden-meta.json` | 12,609 |
| matrix table | `python3 scripts/gen_transform_golden.py .` | Python 3.15.0, `fractions.Fraction` only (no float) | `transform-golden.tsv`, `transform-golden-c.tsv`, `transform_golden_{a,b,c}.kotoba`, `transform-golden-meta.json` | 1,500 cases x 15 functions; 6,561 flow pairs; 2 x 1,000 end-to-end |
| census mapping | `python3 scripts/coverage_g05.py > coverage-g05.tsv` | reads `../cssom-port-census-20261106/float-sites.tsv` | `coverage-g05.tsv` | 95 hits |

Run date 2026-11-06, macOS-26.4-arm64 (recorded in the `*-meta.json`). These scripts are **not part of any gate**; the gate reads their output and pins it:

| file | sha256 |
| --- | --- |
| `trig-golden.tsv` | `d87da8699a9ba78dd34c2938fecb770eb8b13944259a26739b733d4a112acd7f` |
| `trig_golden.kotoba` | `0e18b7f513f2204ac426ba63bc2718bebd40dd74491f8e876babcc3f6c39bcb8` |
| `transform-golden.tsv` | `68381d0251a86aa78e1cc9b18cfa030c06dda7a880a9bc3b1155ac5ac05e73d3` |
| `transform-golden-c.tsv` | `9fd2519499c85211b2f29667f239c7c08557d6ae520324b8f3b56579eb839eb9` |
| `transform_golden_a.kotoba` | `874a07c3293629a2f95058ed74228c5bd6dad74b1d722f4727534c52c5b512a4` |
| `transform_golden_b.kotoba` | `395388cd95b08e74c5e8e4d03b401ef6c542825c9622adc52d1044d92c9e1b59` |
| `transform_golden_c.kotoba` | `bdb47d9bf77596c35cf2ea1dea2f9227b1941c430f06e82932574112684b6d3d` |

The gate also decodes every `.kotoba` data module (balanced `if` trees on the row index) and requires it to equal its TSV bit for bit, so the human-readable table and the native table cannot drift.
The host compiler refuses one module of about 1.3 MB (`EHOST native project packaging failed`), hence three transform data modules. [M]

### Grid sizes

| grid | rows | content |
| --- | --: | --- |
| trig, deg | 6,940 | every degree over +-2 turns (1,441); every 0.1 degree over one turn (3,600); the pole region 85.00..89.20 deg step 0.01 and its mirror and +180 (1,263); 16 tiny angles (1..10000 micro-degree); 1,000 random 6-digit angles over the whole domain; multiples of 45 deg +-2 micro-degree; the domain edge +-1 |
| trig, grad / rad / turn | 2,008 / 2,227 / 1,434 | integers over +-800 grad; step 0.25 rad over +-201 rad; step 1/16 turn over +-32 turns; random 6-digit angles; quadrant edges +-1; the domain edge +-1 |
| trig, outside the domain | 9 | must be refused |
| trig, tan refused | 273 | `|tan| >= 64` or `cos = 0` (166 rows have `cos17 = 0`) |
| trig, Q30 | 3,153 | every 4th row |
| matrix P1 | 1,500 x 15 | random matrices (coefficient magnitudes 2^14..2^23, translations 2^4..2^23, so about a quarter of the words are refusals on purpose): 22,500 words, 16,967 values and 5,533 refusals |
| flow | 6,561 + 162 | all 81 x 81 coded pairs and `flow-ab` / `flow-cd` for the 81 codes |
| isqrt | 16,000 | 4,000 x 4 points: random `n < 2^46`, `r^2`, `r^2 - 1`, `r^2 + 1` (invariant `r^2 <= n < (r+1)^2`, no table) |
| spec points | 31 | hand-derived numbers quoted in `layout.cljk` comments (`matrix(2,0,0,2,10,10)` vs `matrix(2,0,0,2,20,20)`, rotate by quadrant edges, `skew(45deg)`, 84.8528 px bbox, sqrt(6), the flow cases, origin centre, ...) |
| spelling | 4,097 | k/64 turn as turn, degree and gradian, `|angle| <= 32 turns` |
| end to end | 2 x 1,000 (888 / 844 compared) | rotate*scale and skew*rotate about a random origin, points up to 2^8..2^22 raw, two composition routes |

## 4. Error bounds, measured against the golden data [M]

Units: ulp of the stated scale. `sin17 / cos17 / tan17` are Q17 (1 ulp = 7.63e-6); `sin30 / cos30` Q30 (9.3e-10).

| function | rows compared | max error | stated bound (module header) |
| --- | --: | --: | --- |
| `sin17` | 12,600 | **0 ulp** (all 12,600 rows equal the correctly rounded value) | <= 1 ulp |
| `cos17` | 12,600 | **0 ulp** | <= 1 ulp |
| `tan17`, all | 12,327 | **1 ulp** | `1 + 1.6e-3 (1 + tan^2)` ulps (9 at `|tan| = 64`) |
| `tan17`, `|tan| < 1` / `< 8` / `< 32` | | 1 / 1 / 1 ulp | |
| `tan17` rows with `|tan| >= 8` / `>= 32` (max 63.657) | 1,863 / 355 | 1 ulp | |
| `sin30`, `cos30` | 3,151 | 1 ulp of Q30 each | 2 ulps |
| `sin30^2 + cos30^2 - 1` (native alone, all rows) | 12,609 | 2 ulps of Q30 | |
| deg / grad / turn spellings of the same angle | 4,097 angles x sin, cos | 0 differ by more than 1 ulp of Q17 | |
| domain refusals agreed | 9 | 0 disagreements | |
| tan refusals agreed | 273 | 0 disagreements; 0 edge rows | |

The measured tan error is far below the stated bound: the bound is the analytic worst case from the input quantisation at 2^-28 turn amplified by `1 + tan^2`; the sample does not reach it. The analytic bound is kept
because the sample (about 1,800 rows above tan 8, the densest near 89 degrees step 0.01) is not exhaustive.

Matrix algebra against the exact-rational reference (**bit-exact**: the reference is the formula on the Q-scaled inputs read as exact rationals, rounded half up once):

| function | words | mismatches |
| --- | --: | --: |
| `coef-of-number`, `mul-ab`, `mul-cd`, `mul-ef`, `about-ef`, `map-x`, `map-y`, `xs-min`, `xs-max`, `ys-min`, `ys-max`, `uniform-scale`, `font-scale`, `isqrt`, `origin-coord` | 1,500 each | **0 each** |
| `flow-rotation` (5,473 refusals and 40 nil agreed), `flow-ab`, `flow-cd` | 6,561 + 162 | **0** |

End to end (native pipeline vs the ideal REAL-valued image, no intermediate rounding, error in 1/16 Q6 ulp; bound = 16 (2 + 4 S / 2^15) for `about-ef`, 16 (3 + 8 S / 2^15) for the two-step chain, `S = |x| + |y| + |cx| + |cy|` raw):

| coordinate class (raw) | rotate*scale, max Q6 ulps | skew*rotate, max Q6 ulps |
| --- | --: | --: |
| 2^8 (4 px) | 0.94 | 0.94 |
| 2^12 (64 px) | 1.0 | 1.0 |
| 2^16 (1024 px) | 1.8 | 2.6 |
| 2^19 (8192 px) | 8.25 | 24.0 |
| 2^22 (65536 px) | 37.1 (0.58 px) | 51.7 (0.81 px) |

0 bound violations in all four pipelines (about, chain) x (rotate*scale, skew*rotate). The `about` and the `chain` routes give the same maxima (the chain differs by roundings the maxima do not reach).
**Native refusals while the ideal image is in range: 32 (rotate*scale) and 36 (skew*rotate) of 888 / 844 cases.** Exactly those cases have an intermediate translation `e'` or `f'` of the origin conjugation beyond 65536 px (checked with a one-off Python reading
of the same inputs): the limit is on the translation, not on the final point.

## 5. Sizes and the user-v1 verdict [M]

Compiled with `amu-full-root compile --target ...` on the bundled sources (the compiler does not drop unused functions; any entry that reaches one function pays for its whole bundle, dependencies included):

| input | `x86_64-aiueos-kernel-v1` text bytes | `x86_64-aiueos-user-v1` |
| --- | --: | --- |
| `cssom.trig-q6` (+ `length_q6`) | 18,360 | |
| `cssom.transform-q6` (+ `trig_q6`, `length_q6`, `pack_q6`) | 49,363 | |
| whole core, two-argument entry | 50,619 | **E7102** detail 121 (a two-argument entry; user-v1 admits only a zero-argument entry) |
| whole core, zero-argument entry | 50,956 | **E7104** detail 50,604 (the 4096-byte text cap) |
| six-parameter control (`f` with six `:i64` parameters) | refused **E7102** detail 1 | |

The expected `E7104` is confirmed: the transform core is 12.4 times the user-v1 text page. Kernel-v1 admits it. This slice therefore does not run in a user-v1 process; it is a candidate for kernel-v1 only, or for the future split / larger-page decision of the user target (see the render-closure size census).

## 6. Coverage of the 95 G05 hits

`coverage-g05.tsv` (generated by `scripts/coverage_g05.py`, a reading of which function replaces which site; 95 strong hits, 0 unmapped):

| enclosing definition | strong hits | port |
| --- | --: | --- |
| `transform-function-matrix` | 60 | `scale-ab/cd`, `rotate-ab/cd`, `skew-ab/cd`, `mk-tr`, `coef-of-number`; sin / cos / tan = `trig-q6` |
| `transform-angle` | 8 | `trig-q6` units, domain, exact reduction (the `Math/PI` constants become integers) |
| `apply-element-transform` | 8 | `about-ef`, `mul-*` |
| `identity-matrix` | 6 | `ident-ab`, `ident-cd`, `zero-ef` |
| `round-4` | 4 | one Q6 rounding per output |
| `transform-origin-point` | 4 | `origin-coord` |
| `transform-length` | 2 | existing `parse-px-q6` + `length-q6` `percent-of` (slice 1) |
| `transform-ops` | 2 | `map-*`, `bbox-*`, `uniform-scale` (`Math/sqrt` + `Math/abs`), `font-scale` |
| `orthogonal-fallback-inline-size` | 1 | `orthogonal-fallback` |

## 7. Static audit [M, gate]

`trig_q6`: 41 functions, at most 3 parameters, 11 multiplications (3 of two variables), 79 code lines. `transform_q6`: 54 functions, at most 5 parameters, 39 multiplications (36 of two variables), 157 code lines.
No `/`, `rem`, `mod`, `loop`, `recur`, string, record or `f64` token in either. The 2^46 product bound is a design argument (section 2.1), checked by the exactness runs, not proved mechanically.

## 8. What is NOT covered (and what could not be verified)

* **Parsing.** The tokenisation of a `transform` list, function-name dispatch, the `<number>` / `<angle>` scanner (including exponents), `em` / `rem` rejection and the regexes of `transform-function-pattern` are host code. This module takes
  already-scanned D6 numbers, `(unit, D6)` angles, Q6 lengths (from `parse-px-q6`) and hundredths of a percent. No D6 scanner is added (`parse-d4-q6` is D4).
* **Domain limits** (section 2.1): 32 turns, `|tan| < 64`, `|c| < 64`, 65536 px, `|det| < 2^46`, and the intermediate-translation limit. The hosted code has none of them.
* **Output precision** is Q6, not the oracle's 1e-4; the difference to the hosted `round-4` was **not** measured against the real `layout.cljk` (no JVM / nbb allowed, and no oracle for sin/cos). It is bounded by section 4 plus 1/128 px.
* **The trig golden is a sample**, not exhaustive: 12,609 rows. Behaviour between rows rests on the method (exact reduction, polynomial with a stated truncation bound) and the identity / spelling checks, not on a proof.
* **The Python `math` oracle is trusted up to its libm**; the independent exact series agreed on all 12,609 rows at Q17 and Q30 (0 disagreements recorded in `trig-golden-meta.json`).
* No 3D / perspective (not in `layout.cljk`), no glyph rotation, no stacking-context or containing-block behaviour (unchanged, not arithmetic).
* Not wired into `layout.cljk`, not run on CPL3, no browser verdict; kernel-v1 and user-v1 are compile-only (nothing was executed on an AIUEOS target).
* Native macOS arm64 only (`x86_64` AIUEOS objects are compiled, never run).

## 9. Gate and reproduction

```sh
B=/Users/junkawasaki/github/wt/claude/amu-merged/seed/bootstrap/aarch64-macos
python3 lib/kotoba.cssom/scripts/check-transform-q6-native-macos.py --amu $B/amu-cli.macho --amu-full-root $B/amu-full-root.macho --output <empty dir>
```

Prints `PASS_NATIVE_CSSOM_TRANSFORM_Q6`. It pins: the sha256 of every golden file, the TSV/module consistency, all counts of section 4 and the sizes of section 5, and runs **28 mutants** (19 of the modules
`trig_q6`, `transform_q6`, `length_q6` and `pack_q6`, 9 of the golden tables themselves: one leaf of a data function changed) that must make the verdict print 7 or a violation counter rise.
A first run of the mutant set found two controls too weak (a tan-edge rule that accepted any larger value; an end-to-end table leaf in a skipped case); both were fixed in the test / gate before pinning.
The slice 1-3 gates (`check-block-q6-native-macos.py`, `check-calc-q6-native-macos.py`, `check-flex-q6-native-macos.py`) were re-run after the change; see the pull request for their strings.
