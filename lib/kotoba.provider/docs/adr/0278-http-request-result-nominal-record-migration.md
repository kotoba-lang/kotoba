# ADR 0278: HTTP request/result nominal-record migration

- Status: Accepted
- Date: 2026-08-04
- Depends: provider ADR 0231/0235/0276/0277; compiler ADR 0208 / compiler#525

## Context

After the combined and full-request packages migrated, two earlier HTTP
packages remained the joint largest raw-record users: the request skeleton and
result EDN packages each contained 22 explicit construction/projection sites.

## Decision

1. Define nominal `Header` plus `HttpRequest` or `HttpResponse` records in each
   independently compiled package.
2. Use generated qualified refs, exact-map constructors, keyword projection,
   record destructuring, and direct `->Header` construction.
3. Preserve every export and both `main = -9002` oracles.
4. Keep W4 recursive-data and Component AOT qualification unchanged.

## Evidence

- KIR interpreter oracles: both `main = -9002`
- compiler merge: `3ebb7ffa0cfa91463fbe75d0f0bfc7e77d95d94c`
- request wasm/source/provenance:
  - `ba9b54f779cc60b1b381b56fe20033eec99e7880edd7854649d5ea444f946cbb`
  - `ebe2b6b5a78d844eba6de6f9edc3cb8cf344f3f5c20555b42923c6425cc0b113`
  - `d4b2c2737fe96433d186e86b28e53e54b53640ce9ae6b673dafe84a28d16e7c6`
- result wasm/source/provenance:
  - `4962953a64acd40856e648bddae6e7c64ee017822938edefb65cc9c34219ffe0`
  - `bd07b861fa9718cf6093dc4a98a15865cebec9cff1257b2788c998b0d2f9ce49`
  - `2823d4f51c24009a99bdf001c6e7f3655890996552bc128bd01f4e4ad9f67ad0`
- Registry tests pin digests, exports, nominal declarations, and absence of raw
  record operations/manual schemas.

## Consequences

This slice removes another 44 explicit low-level record sites. The authored
HTTP sources increasingly share one readable domain vocabulary even though
each artifact remains independently deployable and content-addressed.
