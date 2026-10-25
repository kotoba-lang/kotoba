# ADR 0276: HTTP kit EDN nominal-record migration

- Status: Accepted
- Date: 2026-08-04
- Depends: provider ADR 0242; compiler ADR 0208 / compiler PR 525

## Context

The HTTP EDN package already exposed the intended typed ABI, but its Kotoba
source described records twice: once in the namespace `:schemas` map and again
through repeated `record-new` / `record-get` primitives. The request has six
fields, so the previous five-argument callable limit also prevented an honest
`defrecord` migration.

## Decision

1. Define `Header`, `HttpRequest`, and `HttpResponse` with `defrecord`.
2. Use generated qualified schema refs, `->Header`, `map->HttpRequest`,
   `map->HttpResponse`, keyword projection, and map destructuring.
3. Keep all twelve exports and the `main` result (`-9242`) unchanged.
4. Build from the tree merged as compiler commit
   `3ebb7ffa0cfa91463fbe75d0f0bfc7e77d95d94c`,
   which admits records up to 32 fields while keeping the callable function ABI
   bounded at five parameters.

The migration removes all 44 explicit low-level record construction/projection
sites from this package. It is a source-surface improvement, not a claim that
host I/O or Component AOT residuals are complete.

## Evidence

- KIR interpreter oracle: `main = -9242`
- wasm SHA-256:
  `05e0ffaea4d3df1ed63842ce52755d6c154e65ef78232a24f442ad783c36ede9`
- source SHA-256:
  `ed3743162f62557ea1ba857af6c6f7a3713674067a76f541a718ebea090dd299`
- provenance seal:
  `b6f8c03deac72dd2635f9c7432af2f754d75070347d9bb4a0e2908119c97b783`
- Registry test pins the artifact digest, exports, nominal declarations, and
  absence of `record-new`, `record-get`, and manual `:schemas`.

## Consequences

The source now reads in domain terms and the compiler owns the mechanical
schema registration. Remaining packages can migrate independently using this
package as the first provider-wide nominal-record pattern.
