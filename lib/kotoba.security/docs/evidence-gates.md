# Evidence Gates

Status: proposed baseline
Date: 2026-07-01

## Language Profile

Run from `kotoba-lang/kotoba-lang` and implementation workspace as applicable:

```sh
test -f lang/profile.edn
test -f lang/package.edn
test -f lang/conformance/manifest.edn
test -f lang/package-conformance/manifest.edn
bb scripts/check-package-contract.bb
cargo test -p kotoba-clj --test lang_profile_conformance
cargo run -p kotoba-cli -- -e '(+ 1 2)'
cargo test -p kotoba-cli --test public_cli
cargo test -p kotoba-cli wasm_cli_tests
cargo run -p kotoba-cli -- wasm safe-policy examples/kotoba-shell-hello/src/policy.kotoba
cargo check -p kotoba-clj
```

## Security Claims Requiring Evidence

| Claim | Evidence |
|---|---|
| `eval` is not runtime authority | negative conformance and subset tests |
| host imports are policy-derived | safe-build policy tests, embedded import audit |
| per-resource graph/model grants work | per-cid capability tests |
| effects are transitive | interprocedural effect tests |
| Wasm memory is bounded | memory-page policy tests and runtime traps |
| builds are deterministic | reproducible core and component CID tests |
| packages are safe to execute | package-conformance lock and signature tests |
| aiueos denies missing capabilities | manifest verify/run tests and audit events |
| private data is ciphertext-first | sealed-store and custody receipt tests |
| PQC migration is ready | crypto inventory and hybrid envelope tests |
| governance is operating | signed review notes, risk/exception updates, release security note |
| incident response is ready | completed tabletop or live drill with postmortem |
| monitoring is active | alert configuration, sample events, detection coverage report |
| key lifecycle is enforced | key register, revocation tests, expired-key rejection |
| FIPS claim is valid | fips-boundary.edn, module certificate, provider rejection tests |
| SBOM/SLSA release evidence exists | SBOM files, provenance statements, release packet |

## Assurance Design Gates

These gates prove the governance and evidence design exists:

```sh
test -f docs/governance.md
test -f docs/incident-response.md
test -f docs/continuous-monitoring.md
test -f docs/risk-management.md
test -f docs/key-lifecycle.md
test -f docs/fips-validation.md
test -f docs/sbom-slsa.md
test -f docs/operational-evidence.md
test -f docs/architecture-review-2026-07-01.md
test -f registers/risk-register.edn
test -f registers/exception-register.edn
test -f registers/key-register.edn
test -f registers/crypto-inventory.edn
test -f registers/evidence-index.edn
test -f registers/architecture-review-findings.edn
```

## Missing Implementation Gates

- Generate SBOM for Rust, Clojure, npm, and Wasm artifacts.
- Generate SLSA/in-toto provenance for release builds.
- Verify package signer expiry and revocation.
- Verify registry record signatures.
- Verify CACAO chain and Kotoba Grant intersection at runtime.
- Verify hybrid PQ envelope test vectors.
- Run fuzzing for EDN readers, package manifests, WIT boundary, and host ABI.
- Run secret scanning on all publishable repos.
- Run threat-model regression checklist for new host imports.
- Run IR tabletop and record postmortem.
- Run monitoring alert simulation and record detection evidence.
- Run expired/revoked key rejection tests.
- Run FIPS-provider policy rejection tests for non-FIPS providers.
