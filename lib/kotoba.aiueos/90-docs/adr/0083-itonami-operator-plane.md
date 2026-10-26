# ADR-0083 — Operator fragment reaches live itonami.cloud from the hosted daily shell

Date: 2026-08-22

## Status

Accepted for a **discriminating slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` **P4**. **P4 is green only when
`kbb -M:session operator` prints `AIUEOS_OPERATOR_OK`:** grant deny is 403
`:operator-grant-required` with zero HTTP to itonami, and grant allow GETs
`https://itonami.cloud/api/health` and `/api/fleet/metrics` from the session
process with status 200 and host `itonami.cloud`.

This file records the attempt. The receipt from `kbb -M:session operator`
is the measurement. A host curl is not this gate.

## Context

P2 is green on QEMU (ADR-0082, aiueos `f9f6f222`). Root P4 is the industrial
operator plane: itonami.cloud is the governed-actor cloud, not kotobase, not
murakumo. Search found the existing surface `network-awai/cloud-itonami` on
`https://itonami.cloud`. No new west repo.

Consumer gates (`session smoke`, `phone-bind smoke`, `bare-metal cloud`) must
stay green **without** itonami credentials or `itonami.cloud` in
`resources/aiueos/cloud_live.edn`. Operator policy is a separate file.

## Decision

1. **Same DADS SPA.** Fragment `#operator` (alias `#itonami`) is another view
   of `apps/session`, not a second document.
2. **Grant first.** Component `:operator/itonami`. Deny imports
   `:itonami/operator` so `grant.broker/verify-one` returns
   `:unresolved-capability`, published as `:operator-grant-required`. Allow
   drops that import. Deny never calls `provider/perform!`.
3. **Live HTTP is the session process** against
   `resources/aiueos/operator_itonami.edn` (`net-allow #{"itonami.cloud"}`,
   host-bound SPKI pin measured 2026-08-22 by
   `kbb -M:cloud-live pin https://itonami.cloud`).
4. **Inventory, not a DNS ping.** Allow GETs `/api/health` and
   `/api/fleet/metrics`. `/api/network-awai/cloud-itonami/state` is recorded
   as the CACAO-gated surface (401 without a credential is reachability, not
   a finished govern write). Consumer smoke does not run these legs.

Not executable, and stated here rather than at the end:

- **`kbb -M:session smoke` does not green P4.**
- **A host curl is not this gate.**
- **P5 a real machine, WM/IME/virtio-gpu 2D, and TLS CertVerify remain.**
  The Chrome OS-shaped desktop goal is not complete.

## Consequences

The hosted JVM profile can show a live itonami inventory in the daily shell
when the operator grant is present, and must not open that socket when it is
absent. CACAO propose→govern write is still a later credentialed path.
P5, WM/IME/virtio-gpu 2D, and CertVerify remain. The goal is not complete.
