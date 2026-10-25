# ADR 0008: W6 Pages bulk pure-path kotoba oracle

- Status: Accepted
- Date: 2026-07-28

## Context

ADR 0007 landed Pages Direct Upload pure multi-step plans in
`cloudflare.deploy`. W6 oracle pattern (deploy_core / module encode) needs
byte-level parity for the new asset-path validators and content-type map.

## Decision

Add `kotoba/pages_bulk_core.kotoba` with:

- `validate-asset-path` (bare error tags)
- `pages-upload-token-path`
- `content-type-for-path`
- `missing-hash?` / `hash-known?` (arity-limited membership probe)

Parity gate: `test/cloudflare/pages_bulk_kotoba_parity_test.cljk`.

## Related

- ADR 0007 pages bulk Direct Upload
- ADR 0004 / 0006 deploy oracles
