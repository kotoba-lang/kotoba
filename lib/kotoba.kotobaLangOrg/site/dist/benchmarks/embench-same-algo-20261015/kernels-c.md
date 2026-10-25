# Kernel audit: kernels agent C (own kernels)

This audit applies the policy in `audit/KERNEL-POLICY.md` ("same algorithm only") to the old-backend kernels that
kernels agent C wrote or rewrote. The compiler audited is m101 (`scratch/m101-41-a64gen.kotoba`).

## How the kernels were mapped to functions

An instrumented copy of m101 was built (`agents/kernels-c/audit/kmap-*`). It wraps every kernel entry so that each
kernel leaves a marker word in the code it emits. All 39 port sources were compiled with it and the markers mapped back
to functions. "Fires on" below means that kernel emitted code for that function of the official port. The functional
ports give the same map.

## Summary

All 9 rows are **same-algorithm**: none computes a result in closed form, skips an iteration, or reuses anything across
calls or benchmark repetitions. Two rows rest on a judgement call and are explained under "Borderline points":

- **sm** drops stores that are overwritten before any read.
- **dk** repacks literal tables at compile time.

## Table

| kernel id | workload | source function(s) | class | one-line reason | policy item | commit that introduced it | reducible to same-algorithm (cost)? |
|---|---|---|---|---|---|---|---|
| sm | statemate | `body` and `loop-356`: the FH_DU tail-call region (s-513 .. s-350, s-516 .. s-514) plus the controller calls inlined into it | same-algorithm | The whole region runs as one block. Every state function's tests, constant-index reads and writes, tail calls (as branches) and controller calls (inline) still execute on every pass. Fuel is checked at each cycle head against the most expensive path, then charged exactly as `sub x8,#own-cost` along the path actually taken. A failed check runs the original code. | Hoisted fuel and bounds checks with exact accounting and fallback; values kept in registers. **Borderline:** a store overwritten before any read on every path, with no exit between, is dropped (coalesced writes). See note 1. | 2b9a5a9f (merged m87); T2 keep marker 1f8aa50c | Already same-algorithm. Turning off the dead-store pass (item liveness) would cost about +25% statemate cycles (A/B: 0.449x vs 0.563x of m77). |
| dk | depthconv | `kernel-step` (32 channels: 4 taps of `F*(I+128)`, bias, scale `(acc*m + r) >> 39`, clamp to -128..127) | same-algorithm | All 32 x 4 multiply-adds, the bias, the scaling and the clamp run at run time in 4-lane int32 NEON (element-wise over the channels). Scaling is `sqdmulh` + `srshr`, an exact identity under compile-time-checked table ranges. Nothing is folded and no repetition is reused. | SIMD for element-wise operations; instruction selection. **Borderline:** the function's own literal tables are repacked at compile time into one int32 literal in load order. See note 2. | e016ab3b (merged m89); keep marker 1f8aa50c | Already same-algorithm. Reading the original i64 tables (`ld2` + narrowing, measured as dk v1) costs about 2.7x the kernel-step cycles (0.63x vs 0.229x of m87). |
| wml | wikisort | `merge-loop` (with `copy-forward`, `item`, `value`, `put` checked as packed SIR patterns) | same-algorithm | Same compares (`v[2b] >= v[2a]`), same pair stores in the same order, same copy-forward of the rest. A run loop keeps the current a and b pairs in registers and re-reads only the side that advanced. A guard (per side, `dst - T0 >= 1` or `dst - T0 + n_O <= 0`) proves no store hits a pair held in a register. Exact fuel is published at the end. | Values kept in registers with every read and write still happening (reads coalesced); hoisted fuel and bounds checks | A 0e0ee194 (m85, frameless kernel); rewritten by C 99145e4c, aliasing fix 694f4618 (m98) | n/a |
| wins | wikisort | `insertion` running `insertion-inner` | same-algorithm | Same insertion steps: shift pairs up while `j > start` and `x < v[2(j-1)]`, then store x and its index. The shift loop is unrolled two moves per back branch. Fuel is checked against the bound, and the exact count is published at `ret`. | Unrolling; hoisted checks with exact accounting | A bb083f6f (m85); unrolled by C 99145e4c | n/a |
| wcf | wikisort | `copy-forward` (`item` per pair) | same-algorithm | Every pair is read and written. Two pairs move per step through q registers. Reading the second pair before writing the first can only differ from the source when `to = from + 1`, which a guard excludes. Fuel `1 + 5(n - i)` is checked and published exactly. | Coalesced reads and writes in program order (independent accesses only); hoisted checks | C 99145e4c (m98) | n/a |
| zf-store `dc zva` path | tarfind, nettle-sha256, huffbench, md5sum, sglib-combined, xgboost (through pz `clear`, zf `fill`, rs `reset`, mdk cz) | zero fills of item ranges | same-algorithm | Inside the shared zero-fill ladder, whole aligned 64-byte lines are zeroed by `dc zva` (only when DCZID_EL0 = 4) instead of two q-register pairs. Exactly the same items get the same zeros. Head and tail stay scalar or q stores. | Instruction selection (coalesced writes) | C 03d9fef0 (m98); the ladder itself is from kernels B (m77) | n/a |
| md5k | md5sum | `rounds` (64 MD5 steps per block, then the four `put`s) | same-algorithm | Per block, all 64 steps run in registers. Each step reads its 4 message bytes (`word-at`), `k[i]` and `r[i]`, computes f, the sum and the rotate, and stores the 4 words at the end, as the source does. C's round-4 changes are instruction-level only: sums reassociated (exact mod 2^64), f by bitwise identities, rotate-left as `rorv` when `r[i]` is in 0..31. Any other `r` gives the prepaid fuel back and runs the original code before anything is stored. | Instruction selection and scheduling; hoisted checks with exact accounting | A e71e780a (m59); C 515e88b7 (m101) | n/a. Note: the codex kernel mdc also emits code for `rounds` (listed in `kernels-other.md`). |
| mdk cz | md5sum, sglib-combined, xgboost | `clear-padding` (md5sum), `clear-heads` (sglib), `clear-votes` (xgboost): `(f v i) = (if (= i N) v (f (put v (+ B i) 0) (+ i 1)))` | same-algorithm | Zeroes exactly items `B+i .. B+N-1` through the zf-store ladder, the same writes. Exact fuel `1 + 2(N - i)` is checked first and published once. Any failing guard runs the original loop. | Hoisted fuel and bounds checks with exact accounting; coalesced writes | C 515e88b7 (m101) | n/a |
| mdk ib | md5sum | `input`: `(f v i) = (if (= i N) v (f (put v i (bit-and i K)) (+ i 1)))` | same-algorithm | Stores `k & K` for every `k = i .. N-1`, computed at run time: a few scalar items, then 4 per step from two 2-lane index vectors (`and` with the mask). Same exact-fuel guard and fallback as cz. | SIMD for an element-wise operation on every element; hoisted checks | C 515e88b7 (m101) | n/a |

Not kernels: the T2 keep markers that C added (1f8aa50c on sm and dk, and the markers on wml, wins, wcf, md5k and mdk) are
`HINT #127` words placed after `ret`. They are never executed and only stop T2 from replacing the kernel.

## Borderline points

1. **sm dead stores.** The policy allows writes that are "possibly coalesced". sm's item-liveness pass drops a store
   only when every path from it overwrites the same item before any read, with no exit in between. Exits are E's RET,
   the cycle heads and their fallback, and nothing inside the block can trap, so the final state of every pass is
   unchanged. That is two writes coalesced into the later one, and the source's work is otherwise intact. If the
   coordinator treats any removed write as substitution, making `sm-dead?` always false (the item-liveness pass
   `sm-live-fn` / `sm-grow` in `kc-sm`) restores every store, at about +25% statemate cycles.
2. **dk literal repacking.** The tables are the function's own `OP-TAB` literals. The repacking only changes their
   storage width (i64 to int32, after compile-time range checks) and their order, and every arithmetic operation still
   runs per call. No closed form is used and no result is precomputed. If storage repacking is not accepted, the
   fallback is the ld2 version (about 2.7x the kernel-step cycles).

## Reuse across repetitions or calls

None of the kernels above keeps any state between calls. Each call validates its handle, checks fuel and recomputes
from the vector's current contents.
