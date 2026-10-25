# ADR 0017: Verify aggregate variants and sealed callable boundaries

## Decision

Pin kotoba-native aggregate ABI v7 and independently widen only the public
variant-boundary predicate: a case payload may be `:i64`, `:bool`, or an
independently admitted recursive record schema. A record remains one pair-chain
handle, so the enclosing variant remains one tag/payload pair handle.

The producer contract must also state closed ordinal callable dispatch,
four-argument bounded `apply`, no arbitrary address, and a closed module graph
with neither ambient nor unresolved symbols. Reading those facts does not widen
the verifier's independently derived KIR predicates.

## Evidence

The verifier accepts, re-emits, and re-verifies a library export consuming a
record-payload variant. The same verified KIR reaches both x86-64 and AArch64
machine encoders. Duplicate schemas, unsupported payloads, reordered cases,
arbitrary addresses, open-ended variadic parameters, and unresolved linkage
remain rejected.
