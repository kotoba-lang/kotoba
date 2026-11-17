# kotoba-client-runtime.js delta review (KOTOBA-159), 2026-11-18

Reviewer: Claude (claude-sonnet-5-5), not blind: this reads the 2026-10-29 and 2026-11-16 reviews first.

## Scope

Two commits changed the runtime after the previous reviewed revision `7b7b5ba1b` (sha256 of that file recorded in
`local-changes.json` history):

- `5a49411f5` AWAI-3001: scoped snapshot consent (`scope`, `receive-snapshot`, circuit-relay addresses).
- `ae0a75e39` AWAI-3059: `nearby` endpoint transport and consent text.

Reviewed head: `origin/main` at `ecbfc15b1`, `src/kotoba-client-runtime.js`, 1118 lines, 60,879 bytes,
sha256 `0926b63b9a80c956e9758fed2cf3159cf8a02f7edf4d3424c2b991dbb7897fc6`. Method: read the 207-line diff, ran the
runtime test set on Node 26.0.0 (all pass: broker-review, consent-host, peer, nearby, memory-state, mount-navigation,
review-20261116), and probed the new validators with synthetic inputs.

## Result

No new High or Medium defect. The changes keep the trust-critical paths intact: `prepareClientOperationRequest` and
`clientEndpointAllowsRequest` refuse `transport` endpoints, `clientRuntimeConnectSrc` excludes them, and both peer kinds
go through the same pre-consent payload snapshot, budgets, deadline and abort signal. Every new dialog field is derived
from the frozen operation, not from guest input.

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| D1 | Circuit-relay addresses (`/ip4/H/tcp/P/p2p/R/p2p-circuit/p2p/PEER`) and the `receive-snapshot` `listen-address` accept loopback, link-local (169.254.169.254) and public hosts. Probed: all return no problems. Extends P1 to the relay hop and the listener. | Low | owner decision, with P1 |
| D2 | `scope` (`snapshot-cid`, `max-transfer-bytes` up to 256 MiB, `allow-read-back`) is displayed and passed to the adapter in the frozen operation, but the broker enforces none of it. It is enforced only if the host peer adapter does. `max-transfer-bytes` also exceeds the 1 MiB request/response budgets, so the broker's byte budgets do not bound a transfer. | Low (design) | confirm: adapter must enforce, record per host |
| D3 | `nearby` connect/send show an opaque peer token, so the dialog cannot tell the user which device. Trust comes from the app's pairing, as the source comment says; consent alone does not identify the device. | Info | confirmed design |
| D4 | A long `scope` or address list renders into the same dialog text as R5; no new truncation guard. | Low | with R5 |

Confirmed design facts: nearby operations have no origin, so they add nothing to the CSP and the network-level barrier
for them is the host adapter, not `connect-src`; scoped peers are limited to protocol `/awai/yataverse/1.0.0`.

## Reviewed revision for vendoring

The file at sha256 `0926b63b…fc6` (commit `ecbfc15b1`, or the later main that still has this digest). Open owner
decisions: findings 1, 7, 8, 9, P1, R3, R4, R5, D1, D2. Consent is still guaranteed only for `restricted-wasm-v1` apps
whose host ships the static CSP; the 2026-11-16 caveat on R6 (Chromium 156 only) is unchanged.

## Not covered

No real libp2p or nearby adapter was run; D2 is about what the adapter must do, not a test of one. No browser run of
the new dialog. Node is not run in CI.
