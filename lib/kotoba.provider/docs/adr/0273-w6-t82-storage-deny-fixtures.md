# ADR 0273: T8.2 storage pure deny-fixtures (validate-* parity with object)

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0153; ADR 0272 object validate-*

## Context

Object gained pure `validate-*` + stable `:code` denials (0272). Storage
already scored deny-fixtures `:ready` via contract throws, but lacked pure
validators and stable error keywords for hosts/tests to match.

## Decision

1. Ship pure validators on `provider.storage`:
   - `validate-get` / `validate-put` / `validate-delete` /
     `validate-put-value` / `validate-expected-version`
   - keywords: `:storage/bad-key`, `:storage/value-too-large`,
     `:storage/invalid-version`, `:storage/unknown-op`
2. Invoke paths call validators + `deny!` with `{:code …}` before transport.
3. Keep readiness deny-fixtures `:ready`; add evidence line.

## Evidence

- Pure validator unit tests; invoke deny for oversized put value

## Related

- Parity with object ADR 0272; signed-wasm still pending for storage/object
