# ADR 0006: Verify private string-index native lowering

## Status

Accepted

## Decision

The verifier admits the five string-index KIR operations only at arities
0, 1, 2, 2, and 3 respectively. It independently records the language bounds
of 128 entries and 65536 aggregate UTF-8 key bytes.

:string-index, :vector-i64, and :vector-f64 may cross only private native
function boundaries. Any kexe export accepting or returning one is rejected.

## Rationale

The native backend represents a string index as a context-owned vector handle
and emits its semantics from existing vector/string/pair primitives. The
verifier must recognize that internal one-word value without ratifying it as a
public host ABI.

The verifier does not import the backend's arity table or bounds. Re-derivation
keeps artifact verification independent of the producer it checks.

## Consequences

- no host graph callback, Rust runtime, or context ABI revision is trusted;
- malformed string-index expressions fail closed;
- helper handles cannot escape through public artifacts.
