# ADR 0008: String-index lowers over the existing vector arena

## Status

Accepted

## Decision

Lower the bounded string -> i64 index into an opaque, private alternating
vector:

    [key-handle value key-handle value ...]

All five operations are emitted from one shared lowering used by x86-64 and
AArch64. No context callback or context ABI version is added.

The lowering independently enforces 128 entries and 65536 aggregate UTF-8 key
bytes. A rejected insertion takes the existing trapping vector-at path.

## Rationale

The language exposes only new, count, contains, get, and assoc. Internal entry
order is therefore unobservable; lookup and replacement remain equivalent to
the canonical sorted oracle value. Existing vector callbacks already provide a
bounded context-owned arena, and existing string equality/length callbacks are
enough to implement the index in emitted Kotoba code.

This avoids a Rust implementation, prevents host-owned graph semantics, and
does not require a loader change.

## Boundary

The representation is private. A raw string-index handle must never appear in
a kexe export signature. Global graph scale is provided by CID-addressed IPLD
pages; one local index remains deliberately bounded.
