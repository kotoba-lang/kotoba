# ADR 0272: T8.2 object deny-fixtures → :ready (pure validate-*)

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0153; ADR 0271 object audit ready

## Context

ADR 0271 flipped object/storage **audit** via mem-transport on-call, and
explicitly left object **deny-fixtures** at `:partial`. Deny paths only
threw generic messages without stable error keywords or pure validators
(contrast process `validate-spawn` / secret `validate-name`).

## Decision

1. Ship pure validators on `provider.object`:
   - `validate-get-stream` / `validate-put-block` / `validate-cas`
   - keywords: `:object/binding-not-allowed`, `:object/empty-key`,
     `:object/empty-digest`, `:object/empty-next-etag`,
     `:object/empty-expected-etag`, `:object/bad-payload`, …
2. Invoke paths call validators and `deny!` with `{:code …}` before transport.
3. Kit-readiness object `:deny-fixtures :ready`. Keep `signed-wasm :pending`.

## Evidence

- Pure validator unit tests; invoke deny code assertions; readiness tripwire

## Related

- Completes T8.2 object residual after 0271 (signed-wasm still open)
