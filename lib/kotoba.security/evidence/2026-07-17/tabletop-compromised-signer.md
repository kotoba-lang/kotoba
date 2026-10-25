# Tabletop: Compromised Package Signer

Date: 2026-07-17  
Kind: IR tabletop (design exercise + linked technical simulation)  
Severity exercised: SEV-1  
Owners: operations-owner, crypto-owner, package-owner  
Linked technical evidence: `revoked-signer-simulation.edn`,  
`alert-compromised-signer.edn`, EV-0009

## Scenario

A package-signing key used for release manifests is believed compromised
(laptop theft / paste of private key into a ticket). The key id is
`sim-compromised-package-signer-2026q3` in the technical simulation register.

## Playbook steps exercised (docs/incident-response.md)

1. **Mark compromised/revoked** in key register — simulated by setting
   `:key/status :revoked` on the synthetic key.
2. **Reject future packages** signed only by that key — simulated by
   `bb scripts/simulate-revoked-signer.bb` which runs
   `key-lifecycle/check-signer-for-new-artifact` and **denies**.
3. **Find manifests/lockfiles using the signer** — tabletop only; inventory
   path is package registry + lockfile grep (no production packages yet).
4. **Rebuild or quarantine** — tabletop: quarantine; rebuild from trusted
   source once replacement key is active.
5. **Publish replacement lock records and advisory** — tabletop: draft
   advisory outline only (not published externally).

## Alert sample

- SEV-1 `trusted-signer-verification-failure` with run-id, component,
  package CID, key id, policy, decision `:deny` (see
  `alert-compromised-signer.edn` / `.json`).

## Gaps found

- No live pager / on-call routing (R-005 residual).
- No production package-signing key exists yet (R-002 residual) — drill used
  synthetic research-demo keys only.
- No automated lockfile blast-radius query wired to CI.

## Closure for tabletop

Root cause (simulated): private key exposure.  
Fix path: revoke → deny new artifacts → issue replacement in kagi → re-sign.  
Regression evidence: `key_lifecycle_test` + simulation script exit 0 on deny.  
Postmortem linked as EV-0008 / EV-0009 in evidence-index.
