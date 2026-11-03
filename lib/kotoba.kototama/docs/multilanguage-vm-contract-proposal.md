# Multilanguage VM contract: first profile proposal

Status: **proposal**, JUN-792. This document does not change the normative
`spec/kototama-vm-v1.edn`, assert implementation conformance, or introduce a
new accepted profile. Its purpose is to make the first contract reviewable
before implementing a language frontend.

## Boundary and identities

Kototama defines a transition and its observable outcome, state, events and
receipt; it is not defined by one compiler or execution engine. The existing
program envelope is tagged canonical DAG-CBOR, and its identity is the CID of
those canonical bytes. Amu and other tools may produce an admitted program;
an interpreter and an AOT engine may execute it. Compilation to native code
does not itself establish VM conformance.

Keep three separate claims and their evidence:

1. **Source translation**: a named frontend version, source language version,
   supported subset, compiler options and source inputs produce a program CID.
   Its tests compare the source behavior with the program behavior within the
   explicitly supported subset. Undefined or implementation-defined source
   behavior must not silently become a portability claim.
2. **Program admission**: an engine independently validates the canonical
   bytes against a named, versioned program profile. It rejects malformed,
   non-canonical, unknown and out-of-profile input, including unreachable
   parts. A frontend's claim is not admission or authority.
3. **Execution**: a named engine version and target implement a declared VM
   profile, with evidence and omissions. Compare semantic outcomes, resource
   consumption and permitted effects; a native artifact identity may differ
   from the canonical program CID and is not proof of semantic equivalence.

No language name alone establishes support. In particular, C pointers and
object layout, Rust ownership and panic behavior, Java runtime facilities and
JavaScript dynamic behavior require their own explicit mappings and evidence.
LLVM IR or Wasm is another input with its own semantics and version, not proof
that all programs in a source language are supported.

## First candidate: closed pure i64

Use the existing Amu `kototama.pure-i64-aot/v1` as the starting implementation
to compare, not as a claim of whole-VM conformance. Its documented scope is
canonical program input, i64 parameters/results, empty guest effects and
imports, no guest heap, bounded frames, acyclic direct calls, and a
zero-argument exported entry. It supports a limited expression set and
explicitly refuses unsupported input. The host transport used to return a
result is not a guest capability.

The candidate contract must pin the exact input encoding and accepted forms,
signed i64 wrap, division and remainder behavior, left-to-right evaluation,
branch selection, trap classes, and resource limits. In particular, it must
pin canonical expression charges and fuel exhaustion behavior, rather than
substituting native instruction counts. Translation must preserve source
behavior for the declared subset; it must not assume source-language overflow,
evaluation order, traps or truthiness match the VM by default.

The existing AOT profile's executable protocol and the full VM transition and
receipt model are distinct. No state, receipt, effects, arbitrary runtime
arguments, recursion, language compatibility or cross-engine parity is claimed
from that bounded AOT path alone.

## Evidence required before an implementation claim

- Pin the normative VM specification revision, program and value profile,
  source frontend revision and options, input CID, engine revision, target,
  runtime ABI and fuel schedule. Version the vectors and retain their inputs.
- Compare an independent reference evaluation and each claimed engine on
  constants, wrap boundaries, signed division and remainder, selected versus
  unselected branches, loop/recur, direct calls and evaluation order.
- Test malformed/non-canonical encoding, unknown fields and forms, invalid
  exports and types, unreachable invalid methods, imports/effects and all
  unsupported constructs. Each must be refused, without guest effects.
- Test fuel at zero and just below, at and above the required budget, including
  loops and traps. Record any protocol difference instead of calling unlike
  results equal. Bound compilation as well as guest execution.
- Compare the observable result and trap class and, where the profile provides
  them, fuel, state, events and receipt projections. Do not require bytewise
  equality for fields that intentionally identify different engines/artifacts.
- For source translation, compare defined source cases with an independent,
  pinned oracle and include negative cases. Refuse unsupported source features;
  language coverage cannot be inferred from a few passing samples.
- Before effectful profiles, specify fresh admission and per-effect authorization,
  resource exhaustion, rollback and external-effect boundaries; test denial,
  scope, expiry and revocation. An approval or compiler annotation alone must
  not grant authority.

## Follow-on decisions

1. Compare the actual canonical evaluator and AOT implementations against the
   candidate, including their fuel and failure protocols; record discrepancies.
2. Decide whether a new versioned portable profile or a narrower conformance
   declaration over existing profiles is needed. Update normative authority
   only after those differences have an explicit resolution.
3. Choose an initial source subset and frontend after the shared profile and
   negative vectors are executable. Keep JVM/nbb out of CI and production
   build paths; an external tool used as a local reference is not a fallback.

References: `spec/kototama-vm-v1.edn`, `docs/kototama-virtual-machine.md`,
and `kotoba-lang/amu` `docs/kototama-i64-aot.md` (the latter is an
implementation-scope description, not this repository's normative spec).
