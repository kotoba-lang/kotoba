# ADR — CI + coverage measurement for the kotoba workspace

Status: **Accepted — implemented (PR #104 coverage, PR #105 CI)**
Context: until 2026-06-11 the ~2,100-test workspace suite was only ever run by
hand at ~150 commits/week, and no measured coverage number existed (estimates
ranged 65–75%). Root-monorepo record: etzhayyim/root ADR-2606111640.

## 1. Problem

Three gaps, all found by the 2026-06-11 portfolio maturity audit:

1. **No CI.** Regressions were only caught when a developer happened to run
   `cargo test` locally. One had in fact been sitting silently red since
   2026-06-07 (see §4).
2. **No coverage measurement.** "What is tested" was answered by guesswork
   (test-LOC ratio), not instrumentation.
3. **Toolchain trap**: the dev machines run Homebrew rust (no `llvm-tools`
   component), and `.cargo/config.toml` pins `build.target =
   aarch64-apple-darwin` repo-wide — both of which break naive
   `cargo llvm-cov` / CI invocations.

## 2. Decision

### Coverage (`scripts/coverage.sh`, PR #104)

- `cargo llvm-cov --workspace --lib` wrapped in `scripts/coverage.sh` with
  three modes: `summary` (default, per-file table), `html`
  (`target/llvm-cov/html/`), `lcov` (`target/llvm-cov/lcov.info` for CI
  upload).
- Pinned to `rustup run stable` so `llvm-cov`/`llvm-profdata` always match the
  building rustc — Homebrew rust ships no llvm-tools, and mixing a 1.95
  Homebrew rustc with 1.96 rustup tools risks profraw format mismatch.
- cargo-tarpaulin rejected: llvm-cov is toolchain-native instrumentation and
  already works with the pinned wasmtime (`= "22"`) build graph.

### Baseline (measured 2026-06-11, workspace lib tests)

| Metric | Value |
|---|---|
| Line | **78.75%** |
| Region | **79.37%** |
| Function | **76.05%** |

Honest low spots (lib-test scope): `kotoba-clj` 0% (its tests are
integration-level), `kotoba-ingest` 0%, `b2_car_store`/`b2_restore` 0% +
`b2_export` 6% + `b2_client` 38%, `kubo_store` 37%, `wasm_pregel` 47%,
`signal_xrpc` 57%, `server.rs` 69%. High spots that earlier audits
underestimated: `kotoba-signal` 98–100%, `kotoba-turn` 94–100%,
`kotoba-graph/sparql` 89%.

### CI (`.github/workflows/test.yml`, PR #105)

- `cargo test --workspace --lib` on every PR + push to `main`, ubuntu-latest,
  `Swatinem/rust-cache`, concurrency-cancel on superseded pushes.
- The job passes the runner's own host triple via
  `--target "$(rustc -vV | sed -n 's/^host: //p')"` — this overrides the
  `.cargo/config.toml` aarch64-apple-darwin pin (first CI run failed with
  E0463 `can't find crate for core` cross-compiling for a Mac target on
  ubuntu) and sidesteps its `target-cpu=native` rustflags.
- Scope is lib tests only, matching the measured-green baseline. Kubo-daemon
  integration tests and fmt/clippy gates are explicit follow-ups (the tree is
  not `cargo fmt --check`-clean yet).

## 3. Consequences

- A red CI check is now a real regression; "run the suite by hand" is no
  longer the verification story.
- Coverage changes are measurable per-PR (`./scripts/coverage.sh` locally;
  `lcov` mode is CI-upload-ready when a codecov-style sink is wanted).
- The 0%-in-lib-scope crates (kotoba-clj, kotoba-ingest, b2 paths) are the
  known frontier — they need integration-tier harnesses, not more lib tests.

## 4. Fixture rule: CACAO test fixtures must not date-rot

The first instrumented run flushed out
`pre_proxy::tests::operator_trusted_pre_roundtrip_end_to_end` failing with
`PreKey(Access(Expired))`: its CACAO hardcoded `issued_at: 2026-05-31` with
`expiry: None`, and a no-expiry CACAO inherits the 7-day `MAX_CACAO_AGE_SECS`
cap (`kotoba-auth/src/delegation.rs`) — so the test went red on 2026-06-07 and
nobody noticed (no CI). The happy-path fixture in the same file had already
been fixed for this exact bug class.

**Rule**: a fixture CACAO either derives `issued_at` from now, or carries an
explicit far-future `expiry` (`2099-12-31T23:59:59Z`). Never hardcoded
`issued_at` + `expiry: None`.

## 5. References

- etzhayyim/root ADR-2606111640 (portfolio QA wave; monorepo-side record)
- kotoba PR #104 (coverage harness + baseline + pre_proxy fixture fix)
- kotoba PR #105 (CI workflow + host-triple override)
- `crates/kotoba-auth/src/delegation.rs` — `MAX_CACAO_AGE_SECS = 7 * 24 * 3600`
