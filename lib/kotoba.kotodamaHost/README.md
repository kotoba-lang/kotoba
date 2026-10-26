# kotoba-lang/kotodama-host

Host runtimes and SDK surface for Kotodama.

This repository owns:

- EDN host component boundaries
- CLJC validation for actor lifecycle, dispatch, config, and SDK facade shapes
- checked WIT artifacts generated from EDN/CLJC authority

It does not own the portable inference runtime. Inference lives in
`kotoba-lang/inference`.

## Rust Status

The former Rust desktop/KAMI host scaffolds and shared Rust host config have been
removed from this repository. Native hosts should live in adapter repositories
and consume Kotoba/Kotodama contracts through the SDK surface.

The default path should not contain `Cargo.toml`, `Cargo.lock`, `.rs`, or Rust
toolchain files.
