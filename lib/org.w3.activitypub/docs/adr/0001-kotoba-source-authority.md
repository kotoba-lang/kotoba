# ADR 0001: Kotoba is the production source authority

- Status: Accepted
- Date: 2026-07-21

## Context

The former `src/activitypub/core.cljc` implementation depended on a Clojure
runtime and did not prove behavior at the restricted JavaScript and typed
WebAssembly boundaries. ActivityPub constructors also accept heterogeneous
documents, so host coercion would weaken the safety boundary.

## Decision

`src/activitypub.kotoba` is the sole production source. Public constructors
use the bounded canonical document ABI and fail closed for malformed host
values or unsupported shapes. Collection `items` must already be a canonical
vector rather than relying on an unbounded host sequence conversion.

The source is compiled by `kotoba-lang/compiler`. Production does not use a
JVM. CI executes the reference KIR interpreter, restricted JavaScript, and
typed WebAssembly and checks observable semantics, the typed ABI, effects,
resource bounds, and rejection behavior. Artifact hashes serve only as
provenance and integrity evidence.

## Consequences

- ActivityPub behavior has one authoritative implementation.
- JavaScript remains an untrusted target behind the generated boundary.
- Unsupported host values are rejected rather than silently normalized.
- Adding production `.clj`, `.cljc`, or `.cljs` files fails CI.
