# ADR 0167: T8.3 ops entropy real-bytes + Component (draw-size policy)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0164 ops publisher policy, ADR 0165–0166 http/secret Components

## Context

Http and secret cleared ops `:signed-wasm` via thin Components. Residual T8.3
asked for process/scoped-fs/git/**entropy** real-bytes/Component path. Entropy
is the purest remaining ops kit: CSPRNG is host-injected; only draw-size
policy is embeddable.

## Decision

### Artifacts

| package | kind | role |
|---|---|---|
| `entropy-draw-v1.wasm` | `:wasm-module` | pure `entropy-draw-ok(n)` — n ∈ [1,64] |
| `entropy-draw-v1.component.wasm` | `:wasm-component` | embeds core via wit (`wasm-tools component embed/new`) |

`:class :ops` (broader than `:ops-network`; publisher policy accepts both).

### Policy surface

`ops-network-kit-names` gains `:entropy`. Packaging bar + Component gate
apply unchanged (`ops-network-publisher-policy-satisfied?` /
`ops-signed-wasm-ready-allowed?`).

### Readiness

- entropy `:signed-wasm :ready`
- kit `:wasm-aot :partial`, `:signed-content-addressed-package :ready`
- host CSPRNG (`provider.entropy-transport`) remains the draw authority

### Non-claims

- Not a replacement for host OS CSPRNG
- Not process/scoped-fs/git pilots (follow-up)
- Not compiler-AOT of full kit request/result EDN

## Evidence

- digest match module + Component
- `ops-signed-wasm-ready-allowed?` true for entropy + Component entry
- production-signed-allowed? true for entropy readiness

## Related

- Reliability WBS T8.3
- ADR 0151 entropy kit contract
- ADR 0164–0166
