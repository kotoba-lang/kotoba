# ADR 0020: Bounded canonical document values

Status: accepted

Kotoba document values are immutable tagged trees rather than JavaScript
objects. They admit null, bool, i64, finite f64, bounded string, bounded
keyword, vector, and keyword-keyed map nodes. Validation is whole-value and
fail-closed: depth 8, 256 nodes, 32 items per container, and 65,536 aggregate
UTF-8 bytes. Map keys are unique and canonically ordered. Cyclic or shared
arrays, non-finite numbers, host objects, functions, prototypes, and malformed
tags are rejected.

Constructors, lookup, scalar access, association, dissociation, and merge are
pure. Updates return newly frozen values; merge is deterministic with the
right-hand map winning. No operation grants authority or touches ambient
JavaScript. Generated helper identifiers use the `doc` prefix so the backend
does not introduce or reference the forbidden ambient `document` global.

This backend implements the restricted-JavaScript half of compiler ADR 0028.
Typed-Wasm descriptor and host admission remain compiler responsibilities.
