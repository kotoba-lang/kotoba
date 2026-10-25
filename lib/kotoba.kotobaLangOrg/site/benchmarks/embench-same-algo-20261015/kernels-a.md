# Kernels A: audit against KERNEL-POLICY.md ("same algorithm only")

Scope: every old-backend kernel Kernels A wrote or changed in rounds 1 to 6. Commits are in the shared repo; branches
are `claude/cosci-kernels-20261014` (rounds 1 and 2), `-r3-` / `-r3b-` / `-r3b-crypto-` / `-r4-` / `-r5-` / `-r6-20261015`.
"m97" means the kernel is in W/scratch/m97-41-a64gen.kotoba. Where Kernels A only tuned a kernel that an earlier agent
wrote (codex), the row covers the kernel as it now stands, and the original commit is named.

Classes: **S** = same-algorithm, **X** = substitution, **U** = unsure (treated as X under "when in doubt").

Policy items cited: A1 instruction selection / scheduling / register allocation / unrolling; A2 SIMD for element-wise
work done on every element; A3 interleaving independent iterations of the same loop and call; A4 hoisted / batched fuel
and bounds checks with exact accounting and fallback; A5 compile-time switch lowering of a constant decision tree;
A6 program data kept in registers or a temporary copy while the function runs, every read and write still done
(possibly coalesced) in program order. N1 closed form instead of iterations; N2 simulation on another structure, final
state written back; N3 new run-time data structures replacing the source's access pattern; N4 reuse across
repetitions or calls; N5 a different algorithm with the same output.

## Summary

- **Substitutions (X): 4.**
  - slre set entries in the round-6 matcher (r6 branch only, not in m97).
  - The ac-coefficients end-of-block bitmask (m97).
  - The ud init closed-form row sum (m97).
  - AES on the crypto unit (parked, never merged).
- **Unsure (U): 3.**
  - The picojpeg whole-block NEON IDCT, which takes DC-only lanes through the AC butterfly (m97).
  - The edn NEON dot products, which reassociate the integer sums (m97).
  - SHA-256 on the crypto unit (Kernels A's version is parked; Kernels B's version is in m97 and is B's to audit).
- **Everything else is S.** Each of these performs the source's own reads, writes and decisions in the source order,
  with fuel batched exactly and a fallback to the function's own code.
- **Reuse across calls or repetitions:** only the round-6 set entries (N4: one activation reuses a set's table across
  bar-loop calls). No other kernel memoizes anything.

## Table

| kernel id | workload | source function(s) | class | one-line reason | policy item | commit | same-algorithm version feasible? (expected cost) |
|---|---|---|---|---|---|---|---|
| blp (matcher core) | slre | bar-loop, bar, plus-loop, plus-end, doh, bracket-search | S | each bar-loop iteration reads its items, then charges exactly and runs the same calls (now internal) and puts in source order; callees are inlined as internal routines with the same recursion | A1, A4, A6 | d5fe37bb (r6 branch, not merged) | already same-algorithm; the build without set entries (r6c) passed the C model and the ksl3 fuel sweep (5673 cases); vs m97 instructions 0.64x, cycles 0.66x |
| blp set entries | slre | set-len, set-loop (via get-op-len, match-set) | X | a per-activation table per set (first item matching each char) is built at run time and reused across calls; set-len and set-loop charges come from a lookup instead of the item scans | N3, N4, N1 | d5fe37bb (r6 branch, not merged) | yes: drop the entries (r6c). slre cycles about 1.47x of r6d (3.8e9 to 5.6e9), still 0.66x of m97 |
| slp | slre | set-loop (at, lower, op-len, match-op) | S | item by item from re's bytes in registers, exact per-item charge, bail to own code at an item boundary | A1, A4, A6 | 35fb73b0 (m97) | n/a |
| sln | slre | set-len (op-len, at) | S | item by item, exact charge per item | A1, A4 | f6e7cf8c (m97) | n/a |
| cin | picojpeg | copy-input (jpeg-byte, put8, put) | S | jpeg-byte (constant byte tree) lowered to a table emitted at compile time; every item is read from it and written to v (4 at a time); & 255 proven identity at compile time; fuel 1 + 3(n - i) prepaid | A5, A2, A4 | 0028231d (m97) | n/a |
| hfc | picojpeg | huff-code (bit, octet, char, put8/16, put, huff-value-base) | S | the same bit loop with the reader's cells in registers, stored at the end; bail to own code | A6, A4 | 24d4229c (m97; keep marker f23b5ec8) | n/a |
| hbt | picojpeg | bits (refill-bits, pow, octet, char, puts) | S | the call computed in registers along the source's own path, cells stored once | A6, A4 | e6429ebc (m97; marker f23b5ec8) | n/a |
| acc (decode loop) | picojpeg | ac-coefficients (huff-symbol, huff-code, bits, extend, zero-coefficients, zag) | S | per step the same symbol walk, bits, extend, run zeros and coefficient stores (through zag, a compile-time table of its threshold tree), reader cells in registers | A5, A6, A4 | 65e3f41c (m97) | n/a |
| acc end-of-block bitmask | picojpeg | ac-coefficients' zero-coefficients(k, 64) | X | a 64-bit mask of written positions (built at run time) selects the cells to zero with masked q stores, instead of zero-coefficients' zag(k)..zag(63) writes; it also rewrites cells the source does not write there | N3 (also changes the write set) | 480a64c8 (m97) | yes: (a) revert to the zag loop, picojpeg about +5 to 8% cycles; or (b) a computed jump into 64 unrolled `str xzr, [base, #8*zag(j)]` (offsets from the compile-time zag table), which does the source's exact writes in order, estimated +1 to 2% |
| cbk | picojpeg | coefficient-block (huff-symbol, bits, extend, puts), tail call to ac-coefficients | S | DC decode in registers along the source's path, stores, then the source's tail call | A6, A4 | 7abeefc4 (m97; marker f23b5ec8) | n/a |
| pjp (scalar lanes) | picojpeg | idct-pass (idct-lane, lane-dc, fill-lane, set-lane, multiply-idct, descale, pixel-clamp, floor-quot, put, i16) | S | per lane: the lane-dc scan (cbnz), then either the DC fill or the AC butterfly as the source chooses; fuel prepaid per lane | A1, A4 | 8ffc95b3 (m97) | n/a |
| pjn (NEON whole block) | picojpeg | idct-pass at i = 0 (as above) | U | eight lanes at once (A2/A3), but a DC-only lane goes through the AC butterfly, whose result equals fill-lane's, instead of the source's fill branch; the charges come from each lane's own nonzero mask | A2/A3 vs N5 (DC lanes) | 2ea49148 (m97) | yes: also compute the DC fill per lane and select it by the lane-dc mask (bsl), so each lane takes the source's branch. Under 1% of picojpeg |
| ncv (hoisted constants) | picojpeg | color (four-lane low16 color loops; base 798a0a3d by codex) | S | element-wise color arithmetic, 4 pixels per NEON step; Kernels A only hoisted the lane constants | A2, A1 | 73264e3e (m97) | n/a |
| jssa + rq-core / ufill | picojpeg | idct-lane helpers (multiply-idct, descale, floor-quot, fill-lane) | S | floor-quot by 2^s as asr only where value bounds prove it exact (otherwise the original sequence); unrolled column fill | A1 | b5e03963, dd8924db (m97) | n/a |
| sw | picojpeg | zero-coefficients (zag) | S | the source's zero writes through zag's compile-time table, frameless entry | A5, A1, A4 | e6c4ce17, 60e46422 (m97) | n/a |
| wml | wikisort | merge-loop (copy-forward, item, value, put) | S | the same merge steps (both pairs read, the source's branch, one stp per pair), then copy-forward | A1, A4 | e78dabc4 (m97) | n/a |
| wins | wikisort | insertion (insertion-inner, value, item, put) | S | the same insertion moves and compares, in order | A1, A4 | d7b44663 (m97) | n/a |
| is | wikisort | insertion-inner | S | counted probe loop (every comparison still made), indexed moves in the original descending order | A1, A4 | 82b8c241, 86734302 (m97) | n/a |
| wfl | wikisort | fill (put, int32, prelude rem) | S | the LCG step per item in a register (the v[1830] cell written once at the end: coalesced writes), the c dispatch hoisted as loop-invariant, each pair stored | A6, A1, A4 | 6d26e5d4 (m97) | n/a |
| hst | huffbench | sort-table (sort-insert) | S | the same insertion sort steps in order; may be shadowed by Kernels B's st | A1, A4 | 04937c07 (m97) | n/a |
| ip | huffbench | sort-insert | S | counted probes, two indexed load/store pairs per move, original order | A1, A4 | 82b8c241, d9a49e3d (m97) | n/a |
| ri (loop) | ud | init (row/column fill and row sums) | S | bottom-tested row loop: each item stored, each added to the row sum | A1, A4 | 2da54e8f (m97) | n/a |
| ri straight-line col 0 | ud | init entered at col 0 | X | items stored by stp, but the row sum is n * x11 + n(n-1)/2 plus a diagonal correction instead of the per-item adds | N1 | a0918463 (m97) | yes: keep the stp stores and do the n adds (branch-free). ud about +1 to 3% |
| rv / ru / rl | ud | forward / backward sums, upper, lower | S | the same loops before the frame, entry charge joined to the prepaid cost | A1, A4 | 86734302 (m97; kernels pre-existing) | n/a |
| lu | ud | lu (lower, upper) | S | factorization unrolled at compile time for the admitted n: same reads, msub/sdiv and stores per step in order; pivot 0 / -1 bails to own code at that step | A1, A4 | ed349ccd (m97) | n/a |
| uf / ub | ud | forward, backward (their sums, at, put) | S | straight-line rows with the source's operations; backward reads its six divisors first (none of them is written by the call) | A1, A4 | 89673c94 (m97) | n/a |
| srloop | nettle-sha256 | schedule loop (sigmas, mask32) | S | the same schedule words, sigmas exact in the low word, two words per iteration | A1 (unroll) | a8b818c0, 8bc5bdd1 (m97) | n/a |
| sphase (scalar) | nettle-sha256 | four-round chunk (big sigmas, ch, maj) | S | the same rounds; maj reuses the previous round's a^b (algebraic CSE); masks as 32-bit adds | A1 | a8b818c0 (m97) | n/a |
| sha crypto (A's version) | nettle-sha256 | rounds and schedule | U | sha256h/h2/su0/su1 compute the same FIPS 180-4 rounds and schedule (instruction selection), pending the user's decision on crypto instructions | A1 vs crypto policy | 76e4eb26, 52eab90e (r3 branch, parked; Kernels B's own version is in m97) | the scalar sphase/srloop above is the same-algorithm version (about 2x the cycles of the crypto path) |
| ar (+ last round) | nettle-aes | rounds (table round, last round, box, byte-at, or4, write-word) | S | the source's T-table lookups and XORs, two rounds per iteration, the last round and the output as the source writes them | A1 (unroll), A4 | 6f808dd9, ac112605, 988e7437 (m97) | n/a |
| aes crypto | nettle-aes | rounds | X | AESE/AESMC (AESD/AESIMC) replace the source's T-table lookups (the tables were checked at compile time to be the standard ones): a different computation with the same output | N5 | 6437f216 / 261dccf4 (parked, never merged) | the ar kernel is the same-algorithm version (cycles about 1.9x of the crypto path) |
| md5k | md5sum | rounds (f/g/h/i steps, mask32, put) | S | the 64 steps unrolled with the source's operations and its four stores in order | A1, A4 | e71e780a (m97) | n/a |
| dotpre | matmult-int | dot (the inner product) | S | the same multiply-adds in order, charges prepaid; may be shadowed by Kernels B's mmx | A1, A4 | f28fac84 (m97) | n/a |
| pz | tarfind | clear (zero fill) | S | the zeros the source writes, stored 2 to 8 items per instruction in ascending order; may be shadowed by Kernels B's zf | A2, A4 | e1afb272 (m97) | n/a |
| pz dc zva | tarfind | clear | S | the same cells zeroed per 64-byte line (instruction selection); dropped at the coordinator's request | A1 | f5967190 (dropped) | n/a |
| gz | statemate | clear-bits (zero fill) | S | the same zero stores, four items per stp q, ascending | A2 | 33a263b0 (m97) | n/a |
| cw narrowing loads | statemate | certified copy chains (chains by codex: 795a8f54, 878ebaef) | S | one store per stage kept; a stage's read narrowed in the load (ldrsb/ldrsh/ldrsw); forwarding from x9 replaces a reload of the value just stored | A1, A6 | 1eed2294 (m97) | n/a (the chain mechanism itself belongs to codex and needs its own row in their audit) |
| gn-copy-entry | md5sum (and other copies) | copy loops | S | the same item copies, 64 bytes per iteration when the destination cannot feed a read of the same chunk | A2 | f1a0c31b (m97) | n/a |
| tbat walk | xgboost | tree walk (per node) | S | node by node walk, bottom-tested, leaf/range tests merged, per-node charges fused; Kernels B later rewrote tbat | A1, A4 | 222af3cd, dec20580 (m97 as rewritten by B) | n/a |
| tbat five levels | xgboost | tree walk | S | if-conversion: both children read, next node chosen by csel, levels counted; same decisions (extra reads only) | A1 | f9d67a02 (dropped) | n/a |
| fo | edn | fir-step (fir outer: table dot per row) | S | the rows in order, each the source's dot loop; the NEON form is the nd row below | A1, A4 | 8493149e (m97) | n/a |
| d2 | edn | fir-red-inner | S | the same two-sum loop, frameless entry | A1, A4 | 359d0f6d, a479517e (m97) | n/a |
| dct | edn | dct-row | S | the 8 loads, butterflies and 8 stores in the source's order, straight-line | A1, A4 | 3520eabf, 988e7437 (m97) | n/a |
| frs | edn | fir-red-step (fir-red-inner) | S | the calls in order, each the source's dot steps | A1, A4 | 659601cf (m97) | n/a |
| nd (NEON dots) | edn | fir-step rows, fir-red-step sums | U | smull/smlal lane sums plus a final reduction: the same products, but the dot's sum is reassociated (exact mod 2^64), a reordering of dependent work | A2 vs "no reordering of dependent work" | 8734e5f4 (m97) | yes: (a) scalar madd chain, edn cycles about 2.2x of now; or (b) interleave independent rows (A3), each row keeping its own sequential accumulation, estimated 1.2 to 1.4x of now |
| rls | qrduino | runs (all-runs per row/column) | S | per element the same bit test, run counter and bw update, branch-free; may be shadowed by Kernels B's qa | A1, A4 | 1c87ff11 (m97) | n/a |
| qrow | qrduino | mask-row | S | per x the same predicate and xor, charges batched per row after a preflight; may be shadowed by Kernels B's mr | A1, A4 | 1c87ff11 (m97) | n/a |
| fourprobe | qrduino | blocks-row | S | per column the same four probes (all read, short-circuit outcome via cmp/ccmp) and the exact short-circuit charge tally; may be shadowed by Kernels B's bp | A1, A4 | 1c87ff11 (m97) | n/a |

## Not shipped (prototyped in round 5, never committed)

| kernel id | workload | source | class | reason |
|---|---|---|---|---|
| set-loop / set-len 16-byte runs | slre | set-loop, set-len | S | SIMD over the items each call scans; slower than scalar, dropped |
| ac lookahead decode | picojpeg | huff-code walk in ac-coefficients | U | compares all 16 code lengths at once (the source stops at the first); no gain, dropped |
| cbk scalar lookahead | picojpeg | DC huff-code walk | S | the same per-length compares without the per-bit shifts; no measurable gain, dropped |

## Substitutions and unsure rows: same-algorithm replacements (no code changed yet)

1. **slre set entries** (r6, not merged): remove them. The r6c build (matcher core only) is the same-algorithm
   version. On top of m97 it measured instructions 30.7e9 (m97 48.2e9) and cycles 5.6e9 (m97 8.5e9). Projected slre
   K/C: about 1.16 instead of about 0.80. It passed the C-model tests and the ksl3 fuel sweep (5673 cases); a full validation and the remaining heavy
   difftests still need running on it.
2. **ac end-of-block bitmask** (m97): replace it with zag-ordered zero stores, either the old loop (picojpeg +5 to
   8%) or a computed jump into a fully unrolled store sequence (offsets from the compile-time zag table, estimated
   +1 to 2%).
3. **ud init col-0 path** (m97): add the items one by one (estimated ud +1 to 3%).
4. **pjn DC lanes** (m97, unsure): select the source's DC fill per lane by the lane-dc mask (under 1% of picojpeg).
5. **edn NEON dots** (m97, unsure): if a reassociated integer sum is not allowed, keep each row's accumulation
   sequential. Run independent rows interleaved (A3) to keep most of the gain (estimated edn 1.2 to 1.4x of now).
   The fully scalar fallback is about 2.2x of now.
6. **AES / SHA crypto** (parked): nothing to reduce. The scalar table and round kernels are already the
   same-algorithm versions.

## Status after the coordinator's decisions (branch `claude/cosci-kernels-sa-20261015`, patch `agents/kernels/a-sa-vs-m101.patch`)

| row | decision | now |
|---|---|---|
| blp set entries | drop them | not in the patch: 0c9d2b38 is the matcher core alone (r6c), same-algorithm |
| acc end-of-block bitmask | fix | 4e2a4232: zero-coefficients' own stores zag(k)..zag(63) in order (computed branch into 64 unrolled str xzr, offsets from zag's compile-time table): S |
| ri straight-line col 0 | fix | d82684b7: one straight-line block per row (computed branch on row), every item stored and added to the row sum: S |
| pjn (NEON whole block) | fix | bb525d95: the source's DC fill computed and selected per lane by the lane's own mask: S |
| nd (NEON dots) | ruled allowed (integer reduction reassociation) | S, unchanged |
| sha crypto | pending the user's decision | unchanged (parked) |
| aes crypto | substitution | never merged |

## Round 7 (branch `claude/cosci-kernels-r7-20261015` on m103, patch `agents/kernels/a-r7-vs-m103.patch`)

| kernel id | workload | source function(s) | class | one-line reason | policy item | commit | same-algorithm version feasible? (expected cost) |
|---|---|---|---|---|---|---|---|
| ptb (transformed-blocks, fused) | picojpeg | transformed-blocks; inlined: idct-pass x2 (idct-lane, lane-dc, fill-lane, set-lane, multiply-idct, descale, pixel-clamp, floor-quot, i16, put), color (put8, i16, pixel-clamp), put16, rem; coefficient-block stays a call | S (one judgment call, see the note) | per iteration every lane, lane-dc scan result, DC fill (computed and selected per lane), multiply, descale, color pixel and put8 of the source is performed in NEON with the source's charges summed exactly (prepaid against the worst case, else the iteration's rest runs as the source's calls); the rows pass's output rows stay in registers as the columns pass's input, and color takes the columns pass's bytes as they are stored | A2, A3, A4, A6; plus inlining, store-to-load forwarding and the removal of the rows pass's 64 stores that the columns pass overwrites before any other read (the columns pass's own reads of them are served from registers) | fd166d8b | n/a. Note: if forwarding the rows pass's stores into the columns pass is not accepted as "possibly coalesced" writes (A6), the fix is to keep those 64 stores (sxtl + stp after the rows pass; checked against the C model; +12 to 14 cycles per block in isolation, about +4% picojpeg cycles) |
| acc huff walk | picojpeg | ac-coefficients' huff-code walk; bits | S | the same compare per length (code <= maximum[i], maximum[i] != 65535, now cmp / ccmp), the same bit reads and refills in order, charges counted from the length reached; bits' quotient of its non-negative 16-bit result by pow(16 - size) is a shift | A1, A4 | ee39ba29 | n/a |
| cbk huff walk | picojpeg | coefficient-block's DC huff-code walk; bits | S | as acc huff walk | A1, A4 | ee39ba29 | n/a |
| blp set scans, literal items | slre | set-len, set-loop, match-op (inside the matcher kernel); bar-loop's path for a literal item | S | set items inside re's bytes are read in order by ldrb, with the source's tests (']', '\', '-', result) merged by ccmp and the charges counted after; set-loop's d2 and the next item's condition at are the same byte, read once (coalescing identical reads, ruling 15 Oct); a lowercase letter not followed by a quantifier takes a straight path with the same reads, tests and charges in the source's order | A1, A4, A6 | 66deac55 | n/a |
