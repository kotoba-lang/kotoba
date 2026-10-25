# ADR 0148: git kit contract first slice

- Status: accepted
- Date: 2026-07-28

## Decision

Add `provider.git` capability id **22**:

- pure `validate-run` (subcommand allowlist, no absolute/`..`/`~` path args)
- injectable `run` transport (`echo-transport` for tests)
- default allowlist is read-oriented (`status`, `rev-parse`, `log`, …)

No ambient git exec. Hosts that want real git compose process kit
(`allowed-commands #{"git"}`) or a dedicated transport later.

## Related

- kbb ability gap: git medium priority
- process kit ADR 0143/0144
