# ADR 0224: Private native handles and string-index admission

## Status

Accepted

## Decision

Native target admission permits :vector-i64, :vector-f64, and :string-index
across private function boundaries only. Any function carrying one of these
types remains inadmissible when exported from a kexe.

The five bounded string-index operations are admitted at their exact KIR
arities. They remain excluded from the CLJS provider-only slice.

## Rationale

Each value is one context-owned machine-word handle, so private Kotoba
functions can pass it without a new representation. The public kexe ABI has no
way to construct, validate, inspect, or release these handles, so exporting one
would create an unowned and unverifiable boundary.

kotoba-native lowers string-index operations into existing vector, string, and
pair primitives. This keeps graph lookup and update decisions in Kotoba
machine code and introduces no host graph callback, Rust component, or context
ABI revision.

## Consequences

- private traversal helpers may carry a bounded CID index;
- public entry and library exports remain scalar/string ABI surfaces;
- malformed arities fail target admission before backend emission;
- the native verifier must independently re-derive the same private/exported
  distinction.
