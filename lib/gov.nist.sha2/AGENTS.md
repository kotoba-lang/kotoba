# AGENTS.md — org-nist-sha2

## Current source and execution contract

- Canonical implementation and tooling use `.kotoba` and Amu selfhost.
  CLJK, CLJC, Clojure, JVM/Java, NBB, Node and KBB are migration inputs;
  none is a final runtime, bootstrap prerequisite or release gate.
- CDCI may execute only Amu selfhost / Kotoba native. Its controller must also
  use that route. The retired hosted workflow has no replacement gate yet;
  missing native evidence stays open.
- Complete each namespace's public exports and transitive implementation.
  A one-block fixture, wrapper, stub or reduced corpus is not completion.
- Preserve unrelated WIP and existing corpus. Do not add or run tests unless
  the user asks to test or verify implementation.

## Hash invariants

- No host hash in `src/`: no MessageDigest, javax.crypto.Mac, shasum, host
  crypto API or external digest capability. Historical oracle sources belong
  to the retained corpus; they are not native qualification receipts.
- Preserve the unsigned byte-vector API, exact export names and arities.
  SHA-224 has its own initial state and emits seven state words; SHA-256
  emits eight. HMAC hashes a key longer than 64 bytes, zero-pads a shorter
  key, and accepts an empty key.
- Preserve all message blocks, padding boundaries and the full 64-bit
  big-endian length field. Kotoba uses literal 64-bit shifts; old CLJS int32
  restrictions are not current language requirements.
- Preserve all published vectors and length/input-shape coverage as porting
  requirements. Any corpus transfer to native must retain that coverage.
- Distinguish source review, native compilation, execution, corpus parity,
  artifact admission and downstream integration. Do not call this library
  qualified merely because a source file exists or a hosted job is gone.

## Scope

`sha2.core` has eight exports: `hex`, `hmac-sha256`, `hmac-sha256-hex`,
`sha224`, `sha224-hex`, `sha256`, `sha256-hex`, and `u32`.
`sha2.sha512` and hash subpath dispatch are separate complete components;
their migration is not implied by work on `sha2.core`.

Raw file I/O, byte capability provider/result lowering, native runtime slots,
artifact admission and callers remain owned by their respective components.
Do not add a string encoding round trip to make a byte digest appear complete.
