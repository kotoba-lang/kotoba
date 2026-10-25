# ADR 0269: T8.2 ops-kit audit dimension → :ready (EDN audit wire)

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0153 kit ready checklist; ADR 0257–0268 EDN audit + host surfaces

## Context

T8.2 first pass scored ops kits `audit :partial` while host audit hooks were
still thin. ADR 0257–0264 shipped pure W4 EDN request/reply audit wraps,
production/test factories, and roundtrips; ADR 0260–0268 added guest host
surfaces with inject. That is the documented host audit plane for ops kits
(0153: “host audit hook or explicit N/A”).

Entropy stays `audit :n/a` (CSPRNG draw; EDN audit of request size remains
available via factories without claiming semantic payload audit).

## Decision

1. In `kit-readiness-v1.edn`, set **`:audit :ready`** for:
   http, secret, process, scoped-fs, git.
2. Keep entropy `:n/a`; leave non-ops residual `:partial` kits unchanged.
3. Evidence points at `provider.edn-codec` wraps/factories/roundtrips + guest
   host packages.
4. Does **not** flip `:wasm-aot :implemented` or production host-I/O claims.

## Evidence

- Unit tests assert readiness audit scores for the five kits

## Related

- T8.2 checklist second pass; T8.3 residual remains host I/O by design
