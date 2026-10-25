# ADR 0145: secret-custody kit contract first slice

- Status: Accepted
- Date: 2026-07-28

## Context

W6 kbb ability gap lists **secret-custody** as high priority / partial:
ops CLIs still use ambient env for tokens (`CLOUDFLARE_API_TOKEN`,
`MURAKUMO_TOKEN_SECRET`). Standing agent policy forbids exhaustive keychain
dumps. Process/scoped-fs kits already use host-injected transports (ADR
0143–0144); secrets need the same pattern.

## Decision

| piece | role |
|---|---|
| `provider.secret` (id **21**) | typed get-only; `:allowed-names` + pure `validate-name` |
| `provider.secret-transport` | `map-fetch` / `env-fetch` (named env only) |

### Explicit non-goals

- No `list` / `dump` / `enumerate` operations
- No ambient full-env scan
- No kagi/OS keychain unlock in this slice (host may wrap a one-shot getter)

### Name policy (`validate-name`)

Reject blank, oversize, path separators, wildcards, whitespace, NUL.

## Consequences

- Ops hosts wire allowlisted names to env or sealed maps without giving
  guests ambient secret authority.
- kbb gap status → contract first slice; kagi compartment transport remains
  Next.

## Related

- ADR 0143/0144 process + scoped-fs (inject, no ambient)
- `lang/w6-kbb-ability-gap.edn` `:secret-custody`
