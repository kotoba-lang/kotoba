# Kernel audit: kernels by other authors in m101 (codex lineage and code-generation rules)

Scope: every certified kernel in the old backend of `scratch/m101-41-a64gen.kotoba` (the lines before
`;; ==== BEGIN T2`) whose audit belongs to neither Kernels A (`kernels-a.md`) nor Kernels B (`kernels-b.md`), nor
Kernels C's own audit (`kernels-c.md`). In practice these are:

- the codex-lineage kernels (present at amu cc3848aa) that A and B did not take as their own;
- the codex certified code-generation rules (call-site, emission and post-emission rewrites), which nobody else covers.

Every kernel added during this session belongs to A, B or C. The merge log in STATE.md and the snapshots m31 .. m101
show no in-session kernel of unclear authorship. A list of kernels already audited by A or B is at the end of this
file, with the notes I have on them.

## Method

1. **Hooks enumerated.** I listed every kernel hook:
   - the OP-FUEL chain in `gn-ins-quiet` (63 entries);
   - the OP-LABEL chain (6);
   - `tbat` on OP-LGET;
   - `kpre-entry` (26 arms plus `kpre-ip`);
   - `gn-op-fn` (sr, sc) and the `gn-op-fn2` tail (dotpre, gn-tree, eq-chain, vl, pf, ve, se/gp/trg-se);
   - `cpp-call` (clw, scfill, wrc);
   - plus every other `*-admit` / `*-plan` / `*-counts` rule.
2. **Mapped to functions.** An instrumented m101 build wraps all 115 kernel entry points so that each one leaves a
   marker word (`movz xzr,#id` + `movz xzr,#fn`) in the code it emits. I compiled all 39 port sources with it and read
   back which kernel emitted code for which function. The files are `agents/kernels-c/audit/kmap-out.txt` and
   `kmap-result.json`.
3. **Origin.** The origin column comes from two sources. For the first commit that brought a kernel into amu I used
   `git log --all -S` on the amu repo. Many kernels arrived in the codex snapshot b5f2a2c0 / 03c72db2 of 2026-10-12;
   others came in earlier or later codex commits, all before cc3848aa. For the in-session changes I diffed the
   snapshots m31 .. m101 (`agents/kernels-c/audit/modhist.txt`):

   | snapshot | changes from |
   |---|---|
   | m31 | the coordinator's early tuning |
   | m41 | A round 1 |
   | m59 / m60 | A round 2 |
   | m77 | B round 1 |
   | m85 | A round 3b |
   | m90 | B round 2 |
   | m99 | B round 3a |

4. **Classification.** Each kernel's recogniser and emitter was read against the workload port source. Most were
   also checked against the disassembly of a diag build of m101 (`agents/kernels-c/audit/diag-m101`, `tools/fdis.py`).

"Emitted" below means the kernel's code is in the m101 image. Some of that code never runs, because T2 replaced the
function afterwards (T2 status 1) or another kernel's fast path takes every benchmark call first. Those cases are noted.

## Summary

- **Whole-function kernels:** 37 codex kernels are audited here.
  - 37 are same-algorithm.
  - 0 are substitution.
  - 3 rest on one judgement call (trg, ac, sls): repeated calls of a pure string reader with the same arguments share
    one byte load. I count that as coalesced reads (allowed). It needs a ruling because of the 15 Oct "qq (skipped
    reads)" ruling; see note 1.
- **Code-generation rules:** 24 are audited, in 22 rows (rc/rp and of/cf share a row). cmap is listed with gn-tree
  above, and sphase is covered by A and B.
  - All 24 are same-algorithm.
  - `trg-ret` is the mechanism behind trg and falls under the same note 1.
  - `scn` is dead code: it is never called.
- **Reuse across benchmark repetitions or calls:** none of these keeps state between calls of a function or between
  benchmark repetitions.
  - No kernel stores anything in the runtime context except the fuel counter. I scanned the emitters and every
    hex-coded kernel for `str [x7,#k]` with k ≠ 8.
  - No kernel keeps a table or flag across calls.
  - No kernel reduces an iteration count or replaces iterations by a formula.
  - The only cross-call reuse found anywhere in m101 is the within-one-call sharing in note 1.
- **Substitutions in kernels owned by A/B:**
  - My reviewers found ud `ri` col-0 (closed-form row sums), which A already lists as X.
  - B's SHA-256 crypto-instruction paths are in m101 (see the cross-reference list).

## Whole-function kernels (codex lineage, not audited by A or B)

| kernel id | workload | source function(s) | what it does | class | one-line reason | policy item | origin | reducible to same-algorithm (cost)? |
|---|---|---|---|---|---|---|---|---|
| cw (copy/write chain mechanism) | statemate | ~170 `s-*` stage functions (copy/write tails) | Inlines up to 48 (or 16) chained stages. Each stage still loads or builds its value, sign-extends it and stores it, in order. One fuel and length check per chain. | same-algorithm | every stage's read, sign extension and store kept, in order; the only forwarding reuses the value just stored to the same item in the same call | hoisted fuel/bounds checks, exact; values in registers | codex d8c76601 (10-10), chains to 48 stages by 878ebaef / 795a8f54 (10-14); m41 A narrowing loads (A's row) | n/a |
| snf | edn, picojpeg, statemate, wikisort | `short-value`, `i16`, `s8`, `s32`, `int32` | An uncharged mask / compare / subtract sign-extension body emitted as one `sbfx`/`sxtb`/`sxtw` | same-algorithm | the function's own arithmetic, other instructions | instruction selection | codex (snapshot b5f2a2c0, 10-12), unchanged | n/a |
| pc3 | wikisort | `item` | Two-item record copy: `ldp` both source items, `stp` both, 3 charges at once | same-algorithm | both reads before both writes, as the source | coalesced reads/writes; hoisted checks | codex d8c76601 (10-10), unchanged | n/a (T2 replaces `item` in m101, so this code is not executed) |
| wm | wikisort | `merge-loop` | Per merge step: re-reads value(b) and value(a), compares, copies one pair, charges 2+4+1, exits into the original code | same-algorithm | the source's step loop with checks hoisted | hoisted bounds checks; exact per-charge fuel | codex (b5f2a2c0), unchanged | n/a (fallback behind C's `wml`) |
| mdc | md5sum | `rounds` | Loop over steps i..63: f and g by quarter, the 4 byte reads of `word-at`, `k[i]` and `r[i]`, rotate via `lslv`/`lsrv`, 3 charges per step, then the original final puts | same-algorithm | the source's steps with the reads done in place | values in registers; exact fuel | codex (b5f2a2c0), unchanged | n/a. md5k (A/C) runs first and covers every benchmark call; mdc is its fallback, also after md5k's r > 31 refund. |
| gn-dot | matmult-int | `dot` (in-frame variant; A audits the pre-frame `dotpre`) | Fully unrolled 20-term `madd` chain in source order (k = 0..19), every read done, fuel n checked once | same-algorithm | the same multiply-adds in the same order | unrolling; hoisted checks | codex ad5b0804 (10-06); m31, m41 `ldp` pairs | n/a |
| td | nettle-aes | `table-round` | The 4 two-way table helpers become one load each from the contiguous literal pair, then the XOR with the key; exact 5 fuel checked | same-algorithm | same lookups and XORs | inlining, instruction selection | codex (b5f2a2c0), unchanged | n/a (T2 replaces `table-round` in m101; `ar` / `ti` carry the same work) |
| sr | nettle-aes | `xor5` (+ `xor4`) | Inlines `xor4`; the five-operand XOR is emitted as a left fold, after the entry charge | same-algorithm | same XORs, reassociated (exact) | integer reduction reassociation (15 Oct ruling); inlining | codex (b5f2a2c0), unchanged | n/a |
| sc | nettle-sha256 | `big0`, `big1`, `small0`, `small1` | `ror32` helper calls inlined as `ror`/`extr` on the run-time x; the callee charges are checked once and charged exactly, with the original per-call path if fuel is short | same-algorithm | "closed" means a certified call shape; nothing is folded at compile time | inlining, instruction selection, hoisted fuel | codex f50624ef (10-06), unchanged | n/a |
| pwphase | nettle-sha256 | `schedule`, i < 16 phase | Every word is packed from its 4 bytes (`ldp`) and stored, in order; 3 fuel per word checked and charged | same-algorithm | same packing and stores | hoisted fuel/bounds; coalesced reads | codex (b5f2a2c0); m77 B rewrite (B's k1-sha row) | n/a |
| shloop | nettle-sha256 | `rounds` (entry of the scalar / 4x / hardware round paths) | All 64 rounds performed; 9 fuel per round checked and published exactly. The body paths are `sphase` (A/B rows) and B's SHA-256 crypto path. | same-algorithm (scalar paths) | same rounds | instruction selection, unrolling, hoisted fuel | codex (b5f2a2c0); m41 A, m77 B (crypto path: B's `sha-crypto` row, pending the crypto policy) | the scalar `sphase` path is the non-crypto version |
| xd | xgboost | `walk` | Node-by-node walk with the source's reads (feature, threshold, x, chosen child), 1 fuel per step; plane ranges checked once, node < 128 and feature < 64 per step | same-algorithm | the source's walk | hoisted bounds checks | codex (b5f2a2c0), unchanged | n/a |
| gn-tree (+ cmap) | nettle-sha256 `expected-byte`, `initial-word`; picojpeg `pow`, `verify-b/g/r`, `winograd`, `zag`; qrduino `expected`, `fmt-word`, `weight` | pure one-parameter threshold trees | The function's own LT/EQ tree is evaluated at compile time for every x in [0, high] and emitted as a table, with the tree's constant leaves for x outside. For `pow` the table is verified at compile time to equal `1 << x` and emitted as `lsl`. | same-algorithm | switch lowering of the function's own constant decision tree; callers still pass the run-time argument | compile-time table from the function's own constants | codex 29d7163a (10-05), unchanged | n/a (`pow` can use the plain table at no cost) |
| eq-chain | sglib-combined | `input` (100-case flat equality chain) | Compile-time table from its own constants, default 0 | same-algorithm | switch lowering | compile-time table | codex (b5f2a2c0), unchanged | n/a |
| jssa + jdag + jwi | picojpeg | `idct-lane` (AC butterfly arm) | Op-by-op SSA translation of the AC arm: every `vector-at`, multiply-idct, descale and set-lane write in order, fuel charged per helper, guards hoisted. jdag is the recogniser and patch library; its own emitter never fires. | same-algorithm | the source's ops one by one | instruction selection, register allocation, hoisted checks | codex (b5f2a2c0); m41 A (asr floor-quot under proven bounds: A's `jssa + rq-core` row) | n/a |
| clw (loop-entry, private-entry) | picojpeg | `idct-pass`, `idct-lane` | Compile-time clones of idct-pass and idct-lane run the same 8-lane loop with guards proven once; scan, descale and fill kept, stores paired | same-algorithm | same lanes and steps | hoisted checks; coalesced stores | codex (b5f2a2c0), unchanged | n/a |
| scfill | picojpeg | `idct-lane` DC arm (lane-dc + descale + fill-lane) | Inlines the 7-element zero scan with early exit, then the descale and the 8 stores; exact charges (the scan's back edges as executed) | same-algorithm | same scan, early exit and stores | hoisted checks | codex (b5f2a2c0); m77 merged into clw-call | n/a |
| bs | picojpeg | `lane-dc` | Zero scan with early exit; fuel charged as the iterations actually run | same-algorithm | same scan | hoisted fuel/bounds | codex (b5f2a2c0), unchanged | n/a |
| bu + bsu + ncv (core) | picojpeg | `color` | Loop split on the run-time `block` value. 4-lane NEON of the per-element low16 / clamp arithmetic; every read and write kept; equal per-iteration cost proven and charged up front; scalar remainder is the original body. | same-algorithm | element-wise SIMD over every pixel | SIMD element-wise; unswitching | codex (b5f2a2c0, ncv 798a0a3d 10-14); m41 A hoisted lane constants (A's `ncv` row) | n/a |
| ss | picojpeg | `bit` | `v[260] != 0` path inline with the same 3 writes and 5 child charges; the refill path goes to the original code | same-algorithm | same reads and writes | coalesced reads | codex (b5f2a2c0), unchanged | n/a (T2 replaces `bit` in m101) |
| vl | picojpeg | `fill-lane` | 8 sign-extended stores at base + stride·k; 3(8 - k) + 1 charges checked and charged | same-algorithm | same stores | hoisted checks | codex (b5f2a2c0), unchanged | n/a |
| btg | edn | `fir-step` inner loop, `fir-sum` | Fully unrolled 50-term `madd` chain in source order, constant table read at run time, 2n charges | same-algorithm | same products and sums, same order | unrolling | codex 3c019cc9 (10-11); m31/m59/m60/m85 `ldp` pairing and admit tweaks | n/a (A's NEON `nd` dots are a separate row of A's) |
| ir | edn | `iir-step` | Per-n loop with the same 6 reads, 2 shifts and 2 stores; exact back-edge charges; the tail returns to the original code | same-algorithm | same loop | hoisted fuel | codex 2144d0f9 (10-11), unchanged | n/a |
| dr | ud | `lower-sum`, `upper-sum` | Per k: load, load, mul, sub; 3 charges per k checked once, both index envelopes checked | same-algorithm | same loop | hoisted checks | codex (b5f2a2c0), unchanged | n/a |
| ac | slre | `set-loop` (+ at, op-len, match-op, lower) | One "ordinary character" iteration per pass with the source's 9 charges. Within one iteration up to 4 `at(re, r+len)` calls share one byte load. Every other case resumes the original code. | same-algorithm (note 1) | same steps; coalesced reads of the same immutable byte | values in registers / coalesced reads | codex (b5f2a2c0), m59/m60 touches with no net change | n/a; shadowed by A's `slp` |
| sls | slre | `set-len` (+ at, op-len) | Every token step, 4 or 5 checked charges per step; `op-len` and its `at` share a byte load | same-algorithm (note 1) | same steps | as ac | codex (b5f2a2c0), unchanged | n/a; shadowed by A's `sln` |
| se | slre | `at` | Frame-free reader: one charge, then the source's own endpoint, bounds and byte read; fuel 0 rebuilds the frame and traps exactly | same-algorithm | same reader | instruction selection | codex (b5f2a2c0), unchanged | n/a (T2 replaces `at` in m101) |
| trg (+ trg-se-entry, trg-prepare, trg-ret) | slre | `quant` = `(or (= (at re r) 42) (= (at re r) 43) (= (at re r) 63))` | Calls a private clone of `at` once; the clone tags a validated fast-path result in x8. The 2nd and 3rd `at re r` calls are charged exactly but take the byte from the first call. | same-algorithm, borderline (note 1) | three identical pure reads coalesced into one, within one call of quant | coalesced reads (borderline against the qq ruling) | codex (b5f2a2c0), unchanged | yes: re-load per call, about 2 byte loads (< 1%). The code is dead in m101: T2 replaces `quant` and its T2 code does the same CSE. |
| qb + qi | qrduino | `qr-bit` (callee and call-site inline) | The same single read & weight[x & 7]; weight's own decision tree lowered to a table | same-algorithm | same read | compile-time table; instruction selection | codex 17a3260b (10-11), unchanged | n/a (T2 replaces `qr-bit` in m101) |
| ts | huffbench | `decode-bits` inner scan | At most 64 scan steps; commits only on success, with fuel = the exact back-edge count, else reruns the original loop | same-algorithm | same scan | hoisted fuel | codex (b5f2a2c0), unchanged | n/a; shadowed by B's `hd` (B rates hd substitution, so ts is the ready replacement) |
| frfix | sglib-combined | `tree-fix` (+ t, red, put) | The 5 source reads validated up front, then all 171 SIR ops re-emitted in order with helpers inlined | same-algorithm | same ops in order | inlining; hoisted checks | codex (b5f2a2c0), unchanged | n/a (T2 replaces `tree-fix` in m101) |
| ga | sglib-combined | `list-merge` (+ d, put) | One merge step per pass: compare, store v[ref], read next after the store, 2 charges | same-algorithm | same steps | registers | codex (b5f2a2c0), unchanged | n/a (T2 replaces `list-merge` in m101) |
| gp + nr | nsichneu | `t2` | Frame-free run of t2's own guard reads; a failing guard returns s (as the source), a passing one runs the full original body | same-algorithm | same tests, same result | instruction selection; hoisted checks | codex (b5f2a2c0), nr f4d892da (10-12), unchanged | n/a (T2 replaces `t2` in m101) |
| pf | nsichneu `seed-case`; sglib `hash-build`, `heap-down`, `list-build`, `tree-build`; picojpeg `check-huff`, `color`, `soi-search` | (fuel register mode) | Keeps the fuel counter in x8; every charge still checked and published; reloaded after calls | same-algorithm | same charges | register allocation | codex 3be67455 (10-12), unchanged | n/a |
| ve | none of the 19 | any body with 2+ vector reads | Reuses a validated vector descriptor along straight-line code; every index check and load stays | same-algorithm | descriptor kept in registers | registers, hoisted checks | codex (b5f2a2c0), unchanged | n/a (dormant) |
| brc | none of the 19 | bounded table / bit-reader loop + state-updater helper | One iteration per pass; every helper store happens; 7 charges per iteration published | same-algorithm | same steps | registers, hoisted checks | codex (b5f2a2c0), unchanged | n/a (dormant) |
| wrc | none of the 19 | 3-transfer copy (forward / backward copies + pair item) | Every pair copied in order; original frames and charges kept | same-algorithm | same copies | hoisted checks | codex (b5f2a2c0), unchanged | n/a (dormant) |

## Certified code-generation rules (codex lineage; call-site, emission and post-emission rewrites)

| rule id | where it applies | what it does | class | one-line reason | policy item | origin |
|---|---|---|---|---|---|---|
| ocb | generic: constant-index vector reads in descriptor-cache mode | Drops a repeated `b.lo/udf` when an earlier check on the same length covered a larger constant index; the `cmp` and every load stay | same-algorithm | check elimination only | hoisted bounds checks | codex (b5f2a2c0) |
| ccf | generic: `CALL f; CONST k; CMP` | Removes a dead `mov x9,x0` after the call | same-algorithm | instruction selection | A1 | codex (b5f2a2c0) |
| di (+ dia, cc-safe) | generic small pure scalar callees (≤ 32 straight-line ops) | Inlines the callee and keeps its entry charge; only arguments that are literal constants in the caller are propagated | same-algorithm | inlining; no compile-time evaluation of run-time arguments | A1 | codex 44bfaa28 (10-06) |
| tc | crc32 `checksum` → `table-at` | The callee's 16-leaf decision tree over `x & 255` becomes one indexed load from its own constant tables; entry charge kept | same-algorithm | switch lowering | compile-time table | codex d8c76601 (10-10) |
| aw | picojpeg `set-lane` call sites | Inlines index arithmetic, sign wrapper and checked store, with each callee's charge | same-algorithm | inlining, exact fuel | A1 | codex d8c76601 |
| rc, rp (+ rq-core) | picojpeg `multiply-idct`, `descale` | Inline floor-quot / i16 / pixel-clamp; `asr` where no overflow is provable (else the original sequence) | same-algorithm | instruction selection | A1 | codex (b5f2a2c0); rq-core `asr` path in session (A's row) |
| ti | nettle-aes `table-round` call sites in `rounds` | 4 byte extracts, 4 table loads and the xor chain inline; 6 charges checked together; low fuel takes the original call | same-algorithm | inlining, hoisted fuel | A1, A4 | codex (b5f2a2c0) |
| pi | wikisort `item` call sites | Two reads and two writes as `ldp`/`stp` after fuel / overflow / handle / index guards; any failure takes the original call | same-algorithm | coalesced reads/writes | A4, A6 | codex (b5f2a2c0) |
| vmode descriptor caching (vi-step, gn-chain-step, ve-step, sl-assign) | generic loops and chain targets | Keeps a vector's length and base in registers, guarded by a run-time handle key or a compile-time proof; every element access and index `cmp` stays | same-algorithm | values in registers | A6, A4 | codex (b5f2a2c0); 7a17458f / 9b7816da (10-13) |
| gn-affine-read | generic `base + a*k + b` reads | `madd` for the index, then the normal checked read | same-algorithm | instruction selection | A1 | codex |
| gn-small-tail / cc-proof | generic tail-only small functions; non-leaf functions whose callees keep x7 | Frameless low-register mode with every charge published; a proof that x7 survives calls removes context reloads | same-algorithm | register allocation | A1 | codex |
| trg-ret | slre (`at` clone of trg) | The clone's RET tags x8 so trg can tell a validated fast-path result | same-algorithm, borderline | part of trg (note 1) | A6 | codex (b5f2a2c0) |
| fsb | generic `FUEL; BR loop` | Fuel-success `b.hs` goes straight to the loop head; the exhaustion `str xzr` + `brk` stay | same-algorithm | code layout | A1 | codex (b5f2a2c0) |
| of, cf | generic fuel blocks (mode-2 chains, framed functions) | Moves the exhaustion `brk` to a shared cold slot; every `subs`/`str` stays | same-algorithm | code layout | A1 | codex (b5f2a2c0) |
| dcr | picojpeg `idct-lane` (clw private success path) | Restores only x19–x22 on the success path because x23–x28 are proven unwritten | same-algorithm | register save/restore | A1 | codex (b5f2a2c0) |
| jdf | picojpeg `idct-lane` (jwi prefix) | Replaces a fuel/descriptor reload with registers set earlier in the same call (path walk proves them intact) | same-algorithm | values in registers within one call | A6 | codex (b5f2a2c0) |
| scn | none (dead: `scn-run` is never called) | Would unswitch repeated tests of an unchanged parameter | same-algorithm if enabled | dead code | n/a | codex (b5f2a2c0) |
| srf | picojpeg `bits` `(quot … (pow (- 16 width)))` | Drops the divide-by-zero trap because every leaf of `pow` is a positive constant; the call still runs | same-algorithm | check elimination | A4 | codex (b5f2a2c0) |
| hld | generic single-vector leaf-like functions with 3+ checked accesses | One handle / descriptor validation plus aliasing guards at entry; every access keeps its index check and its load/store; guard failure runs the original code | same-algorithm | hoisted checks, registers | A4, A6 | codex (b5f2a2c0) |
| cpp | picojpeg `bits` call sites with literal width ≤ 8 | Clones `bits`' entry code for those sites with `(> width 8)` folded to false; both arguments are program literals | same-algorithm | constant specialisation on literals only | A1 | codex (b5f2a2c0) |
| blt (+ blt-old-run pipeline) | picojpeg `jpeg-byte`, qrduino `g0log` | Evaluates the function's own byte-valued compare tree for x in [0, high] at compile time and emits a table that also reproduces the final flags. The pipeline also runs sf-collapse (frame reuse on tail calls), mp-run (`mul`+`add` → `madd`) and ls-run (spill store → reload forwarding); I skimmed these and found HOW-only changes. | same-algorithm | switch lowering; instruction selection | compile-time table; A1 | codex c6eb32b4 (10-12) |
| uqd | generic signed division by 2^p | Drops the rounding bias when the dividend is proven non-negative | same-algorithm | instruction selection | A1 | codex 2b0293e3 (10-13) |

## Note 1: repeated pure reads in slre (trg, ac, sls)

`quant` calls `(at re r)` three times with the same arguments. `set-loop` and `set-len` likewise call `at` on the same
position several times per iteration. `at` is pure and `re` is an immutable string, so trg, ac and sls do one
bounds-checked byte load and serve the repeated calls from it. Each call's fuel charge is still made, exactly.

- **For same-algorithm:** this is coalesced reading of the same immutable data within one call. The policy's "possibly
  coalesced" covers it, and it is what clang -O2 does after inlining. T2's own code for `quant` (status 1 in m101) does
  the same CSE.
- **Against:** the 15 Oct ruling "qq (skipped reads)" treats skipped reads as substitution. That case is different,
  though: B's qq takes values from a compile-time literal instead of reading mutable program data at all.
- **My two reviewers disagreed** (one counted trg as substitution under the qq ruling, one as same-algorithm), so I
  flag it for a ruling.
- **If the ruling goes against it,** trg, ac and sls flip together, and so does T2's CSE of `quant`. The fix is one
  extra byte load per repeated call (< 1%). trg's code never runs in m101 anyway, and ac and sls are shadowed by A's
  `slp` and `sln`.

## Kernels already audited by A or B: my notes (no new rows)

- **ri, ud `init` col-0 path:** substitution (closed-form row sum `n*x11 + n(n-1)/2` plus a diagonal correction, and the
  diagonal cell is written twice). My reviewer agrees with A's X row. It was introduced in m85 (A round 3b); codex's
  per-cell ri is same-algorithm.
- **SHA-256 crypto instructions are in m101:** B's `sha-crypto` (`sha256su0`/`su1` in the srloop hardware path,
  `sha256h`/`h2` in sphase's hardware path, both m77). B lists it as same-algorithm pending the crypto-instruction
  policy. Agents were told "no hardware crypto instructions", so this needs a decision before the official round. The
  scalar paths (A's `srloop` / `sphase`, B's `k1-sha`) are the fallback.
- **tbat (xgboost trees):** both A and B list it. My reviewer agrees with same-algorithm. The one point to note is the
  five branch-free steps, which read both children and padding nodes: extra discarded reads, nothing skipped.
- **is, ip:** both are loop fission (compare pass, then move pass), with every compare and move kept. My reviewers
  agree with same-algorithm.
- **wfl (wikisort fill, A):** my reviewer agrees with same-algorithm. The c = 7 branch `quot(r, 1932735283) > 1` is
  folded because r < 2^15 is provable. That is standard range folding of a dead branch, not skipped work; keeping the
  test costs nothing if the coordinator prefers.
- **Shadowing that matters if A/B kernels are removed:**
  - codex qrow, fourprobe and ts sit behind B's mr, bp and hd, and are same-algorithm replacements for them;
  - codex ac and sls sit behind A's slp and sln;
  - codex wm and mdc sit behind C's wml and md5k.
- **Kernels already covered (no new rows):**
  - A: rls, qrow, fourprobe, ip, is, sw, d2, rv/ru/rl, ri, srloop, sphase, ar/art, tbat, pz, gz, gn-copy, dotpre,
    jssa helpers, ncv, cw narrowing, md5k, wfl.
  - B: rls, ip, zf/pz, tbat, k1-sha, sha-crypto and their round-1/2/3 kernels.
  - C: sm, dk, wml, wins, wcf, zf-store `dc zva`, md5k, mdk.
