# Kernel scope policy (user decision, 15 Oct 2026: "same algorithm only")

A certified kernel may change HOW the source function's work is executed, never WHAT work is executed.

## Allowed (same algorithm)
- Instruction selection, scheduling, register allocation, unrolling, software pipelining.
- SIMD for element-wise data-parallel operations the source performs on every element.
- Interleaving independent iterations of the SAME loop of the SAME call (no reordering of dependent work).
- Hoisting/batching fuel and bounds checks with exact accounting and fallback (as T2 does).
- Lowering a function whose body is a constant decision tree / if-chain over its argument into a
  lookup table built at COMPILE time from that function's own constants (standard switch lowering).
- Vectorizing an integer reduction (sum, xor, ...) by reassociating it: exact modulo 2^64 and done by standard
  vectorizers (clang -O2 vectorizes integer reductions too). Ruling 15 Oct (edn dot products).
- Keeping values of the program's own data in registers or a temporary copy while the function runs,
  when every read and write of the source still happens (possibly coalesced) in program order.

## Not allowed (substitution)
- Computing a result, fuel or state in closed form instead of performing the iterations
  (e.g. "tree-sum in closed form", "12N - 5*v[8] + 1").
- Simulating the algorithm on a different data structure or copy and writing back the final state
  (e.g. "whole quicksort simulated on a stack copy") when that replaces the source's own steps.
- Building NEW run-time data structures the source does not build (e.g. per-class preorder tables
  for tree walks) to replace the source's access pattern.
- Any reuse of results across benchmark repetitions/calls (memoization, "already computed" shortcuts,
  skipping work because the input repeats).
- Replacing the algorithm by a different one with the same output (different sort, different search).

When in doubt, classify as substitution.

## Audit output (one row per kernel)
kernel id | workload | source function(s) | class (same-algorithm / substitution / unsure) | one-line reason |
which allowed/not-allowed item applies | commit that introduced it | can it be reduced to a same-algorithm
version (and expected cost)?

## Rulings (15 Oct)
- Unsure cases default to substitution: B bp, mr (packed-bit SWAR), lcg (leapfrog recurrence), qq (skipped reads);
  A picojpeg IDCT DC-only lanes through the AC butterfly (replaces the source's fill branch; fix is < 1%).
- Allowed: edn NEON dot products (integer reduction reassociation, see above).
- Allowed: dead-store elimination of an item overwritten before any read on every path with no exit between
  (C statemate sm) -- standard DSE.
- Allowed: compile-time repacking of a function's own constant tables (C depthconv dk); all arithmetic still runs.
- Allowed: coalescing identical reads with no intervening write (slre trg/ac/sls) -- standard load CSE; fuel still
  charged per source call.
- SHA-256 crypto instructions (B round 1 hardware path): OFF for the same-algorithm official round (conservative;
  C -O2 does not use them; the user's crypto decision is still open). The scalar sha256 kernel is used.
- Allowed: fusing two consecutive loops of one call (loop fusion) when no dependence is violated -- every read,
  write, decision and charge of both loops still happens, each value is written before it is read, and fuel/trap
  behaviour stays exact (sha256 schedule + rounds, ruling 15 Oct). Standard compiler loop fusion.
