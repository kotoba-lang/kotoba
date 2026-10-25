# ADR 0277: HTTP request EDN nominal-record migration

- Status: Accepted
- Date: 2026-08-04
- Depends: provider ADR 0234/0276; compiler ADR 0208 / compiler#525

## Context

ADR 0276 established the nominal-record pattern in the combined HTTP package.
The earlier request-only package still duplicated `Header` and `HttpRequest`
schemas and used raw construction/projection primitives at 24 source sites.

## Decision

Define `Header` and the six-field `HttpRequest` with `defrecord`; use generated
qualified refs, `->Header`, exact-literal `map->HttpRequest`, keyword access,
and record destructuring. Preserve all six exports and `main = -9002`.

This is an authored-source migration only. W4 recursive data and Component AOT
claims remain unchanged.

## Evidence

- KIR interpreter oracle: `main = -9002`
- compiler merge: `3ebb7ffa0cfa91463fbe75d0f0bfc7e77d95d94c`
- wasm SHA-256:
  `ad45dbea1d41849fc5b7301ae51925326ecc365c4fe39d359552c250f8f0d304`
- source SHA-256:
  `5e3feee02330b37ee07f0c7743b7647df215638374e61433ea4cba3d3c79117c`
- provenance seal:
  `5fb09d5b9e0bb0f88d0a6adad63896601f9133e3053df6306b9148350e711615`
- Registry tests pin digest, exports, nominal declarations, and the absence of
  raw `record-new`, `record-get`, and namespace `:schemas`.

## Consequences

The provider-wide residual drops by another 24 explicit low-level operations.
The remaining older HTTP packages can be migrated independently with the same
bounded pattern.
