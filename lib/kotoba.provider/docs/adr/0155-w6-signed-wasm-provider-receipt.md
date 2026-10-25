# ADR 0155: T8.3 remainder first slice — signed Wasm provider receipts

- Status: Accepted
- Date: 2026-07-28

## Context

T8.3 asks for network/secret **signed** reference providers. ADR 0154 landed
**signed kit EDN package receipts** only. Full production path still needs:

1. content-addressed **Wasm** (or Component) bytes
2. publisher signature over that digest + kit binding
3. readiness `:signed-wasm :ready` only when real AOT packages exist

Emitting AOT Wasm Components for every kit is XL (compiler packaging, host
grant binding, CM linking). We need an honest intermediate that:

- defines the **Wasm receipt API** (digest / sign / verify / kit chain)
- proves round-trip with a **fixture** empty module (`\0asm` + version)
- **never** flips readiness `:signed-wasm` or `production-signed-claim?`

## Decision

### Layers (updated)

| layer | claim | status |
|---|---|---|
| Unsigned kit EDN SHA-256 | content-address of package text | landed (#35) |
| Signed kit EDN receipt | host sign over kit digest+resource | landed (#36 / ADR 0154) |
| **Signed Wasm provider receipt** | host sign over **Wasm bytes** digest + kit resource (+ optional kit-edn digest chain) | **this ADR** |
| Production AOT signed Component | real package + readiness gate | **still pending** |

### API (`provider.kit-package`)

- `sha256-hex-bytes` / `wasm-artifact-digest`
- `wasm-provider-receipt` / `wasm-signing-input`
- `sign-wasm-provider-receipt` / `verify-wasm-provider-receipt`
- `chain-kit-and-wasm-receipts` — bind kit EDN digest before signing Wasm
- `empty-wasm-module-bytes` — synthetic fixture only (`:artifact-kind :fixture-synthetic`)
- formats: `:kotoba.kit-package.wasm/v1` → `:kotoba.kit-package.wasm-signed/v1`

### Non-claims

- Does **not** set readiness `:signed-wasm` to `:ready`
- Does **not** set kit `:signed-content-addressed-package` or `:wasm-aot` to ready
- Does **not** claim production identity (hosts inject `sign-fn` / `verify-fn`)
- Fixture empty module is **not** a provider implementation

### Next (still open)

- Emit real content-addressed Wasm/Component packages (compiler wasm-aot path)
- Bind host grants to signed digests for HTTP/secret reference providers
- Only then flip readiness `signed-wasm` where checklist is complete

## Evidence

- `src/provider/kit_package.cljk` wasm receipt path
- `test/provider/kit_package_test.cljk` sign/verify + forgery + production gate still false

## Related

- ADR 0152–0154 kit packages / readiness / kit EDN receipts
- Reliability WBS T8.3
