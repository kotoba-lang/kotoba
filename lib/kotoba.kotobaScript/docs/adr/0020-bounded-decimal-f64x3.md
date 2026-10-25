# ADR 0020: Bounded fixed-width decimal f64 vector parsing

Status: implemented in Kotoba Script; compiler qualification pending

`decimal-f64x3-parse` has type
`string -> [:option [:vector [:f64 :f64 :f64]]]`. It accepts at most 194 ASCII
bytes containing exactly three ADR-0019 decimal values separated by one or more
ASCII space, tab, carriage-return, or line-feed characters. Leading and
trailing ASCII whitespace are admitted. Every component independently retains
the 64-byte, finite-only, round-to-nearest-ties-even decimal contract.

Parsing is atomic: wrong arity, Unicode whitespace, commas, a malformed or
non-finite component, or either byte bound produces typed `none`; no partial
vector is exposed. Successful output is the canonical sealed heterogeneous
three-f64 vector, preserving component signed zero, underflow, and subnormals.

Qualification requires reference, restricted JavaScript, and typed Wasm parity
over real URDF `xyz` and `rpy` attributes before consumer cutover.
