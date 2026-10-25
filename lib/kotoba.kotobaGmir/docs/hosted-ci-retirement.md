# Hosted CI retirement — 2026-10-22

The owner requires Kotoba / Amu selfhost execution and a native CDCI
controller. The previous `.github/workflows/ci.yml` is obsolete.

Removed source blob: `5ae16fb1d666ce44e25570e16cce8902632e1930`.
The sole declared job installed Java 21 and Clojure CLI, then ran the hosted
test runner. No replacement placeholder or native gate is added.

Baseline main: `a891d4328132058d31756935a8a1d51630526fcc`.
The patch changes only workflow registration and policy/provenance documents.
All GMIR implementation, instruction data, dependency descriptors and corpus
are unchanged. No compiler, validator, encoder, generator or native program
is executed, and no tests are added or run.

Main protection and branch rules are read separately before and after
merging. No protection or required-context mutation is part of this change.
Removal of a hosted job does not imply native qualification.

## Actual remaining dependencies

- Complete canonical GMIR module: the existing compatibility projection is
  not admitted, and its empty `i64-value?` host-region projection is a real gap.
- Byte capability kind signatures/discriminators in the owning contract,
  complete KIR lowering and both ISA encoders, typed request/result handling,
  byte-preserving provider / FS2 and whole callers. Existing kind IDs remain
  unchanged at 0–7 in this patch.
- Complete native positive/refusal/resource corpus, exact artifact evidence,
  reviewed owning main/pins and actual self-rebuild.

The shared checkout's existing gmir.cljk edit and broken worktree metadata
are preserved. No unrelated forest maintenance plan is applied.
