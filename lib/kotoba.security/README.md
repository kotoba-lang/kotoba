# kotoba-lang/security

`kotoba-lang/security` is the governance and assurance layer for the Kotoba
language, runtime, package, and operating-system substrate. It does not replace
implementation-owned ADRs in `kotoba-lang/kotoba-lang`, `kotoba-lang/kotoba`,
or `kotoba-lang/aiueos`; it turns those design decisions into auditable security
claims, standards mappings, test gates, and open gaps.

## Scope

This repository owns:

- the repository-wide assurance rule, mandatory report fields, critical caps,
  and [current security heatmap](docs/security-assurance-model.md), with its
  machine-readable authority in
  [security-assurance-model.edn](policy/security-assurance-model.edn);
- security architecture and threat model summaries across Kotoba language,
  Wasm execution, package distribution, identity, storage, and audit;
- standards mappings for NIST CSF 2.0, selected NIST SP 800 controls, DoDAF
  2.02 architecture products, and post-quantum cryptography migration;
- a crosswalk from SOC 2 Trust Services Criteria and ISO/IEC 27001:2022
  Annex A onto the evidence this repository actually holds
  ([control-crosswalk.edn](policy/control-crosswalk.edn),
  `src/kotoba/security/crosswalk.cljk`), which separates design evidence from
  operating evidence so that a Type I claim cannot be mistaken for a Type II
  one;
- control evidence checklists that point back to implementation tests,
  conformance fixtures, ADRs, and run receipts;
- security acceptance gates for safe Kotoba, package locks, aiueos manifests,
  cryptographic envelopes, and release evidence packets;
- executable gates: a safe-release evidence gate over the evidence index and
  exception register (`src/kotoba/security/release_gate.cljk`) and a FIPS/PQC
  crypto policy over envelopes and the crypto inventory
  (`src/kotoba/security/crypto_policy.cljk`, `policy/crypto-policy.edn`).
- package admission, signed release evidence, origin assertions, sealed
  egress, key hierarchy, threat-model and vulnerability-response executable
  assurance. Package shape and registry semantics remain in
  `kotoba-core-contracts`; this repository decides whether evidence is safe
  enough to admit.

This repository does not own:

- compiler implementation details;
- host runtime code;
- production key material;
- operational incident response authority for a deployed organization.

## Current Assessment

Kotoba's design is strong on containment:

- safe Kotoba is a Clojure-shaped, Wasm-first, capability-checked profile;
- host access is intended to be policy-derived and deny-by-default;
- package references are designed to be CID-pinned, signed, and capability
  bounded;
- aiueos enforces manifest capabilities, resource limits, and audited denials;
- private data is intended to put confidentiality at object encryption rather
  than peer trust or selective replication.

The initial assurance design now covers the NIST-class operating concerns that
language design alone cannot cover:

- governance roles, decision classes, cadence, and release sign-off;
- incident response severity, playbooks, and evidence preservation;
- continuous monitoring signals, metrics, alert rules, and retention;
- seeded risk, exception, key, crypto, and evidence registers;
- key lifecycle states, crypto periods, separation, and revocation;
- FIPS validation non-claim and deployment-boundary evidence requirements;
- SBOM/SLSA release artifact requirements;
- operational evidence packet requirements.

Remaining compliance evidence is explicit:

- package lock enforcement, signer revocation, key expiry, registry
  verification, and release admission have executable gates; production
  deployment receipts are still environment-specific evidence;
- PQC is designed as a crypto-agility and hybrid migration path, not yet
  implemented end-to-end;
- continuous monitoring and IR drills need live deployment evidence;
- formal verification and side-channel defenses are not present;
- FIPS validation is not claimed without a named validated module boundary.

## Documents

- [Security Architecture](docs/security-architecture.md)
- [Architecture Review 2026-07-01](docs/architecture-review-2026-07-01.md)
- [Standards Assessment](docs/standards-assessment.md)
- [Security Governance](docs/governance.md)
- [Incident Response](docs/incident-response.md)
- [Continuous Monitoring](docs/continuous-monitoring.md)
- [Risk Management](docs/risk-management.md)
- [Key Lifecycle](docs/key-lifecycle.md)
- [Key Operations (kagi)](docs/key-ops-kagi.md)
- [FIPS Validation Strategy](docs/fips-validation.md)
- [FIPS Product Non-Claim](docs/fips-non-claim.md) (**no FIPS validation claim**)
- [On-call / Pager](docs/on-call-pager.md)
- [SBOM and SLSA Provenance](docs/sbom-slsa.md)
- [Operational Evidence](docs/operational-evidence.md)
- [PQC Roadmap](docs/pqc-roadmap.md)
- [DoDAF Viewpoints](docs/dodaf-viewpoints.md)
- [Evidence Gates](docs/evidence-gates.md)
- [ADR: Shared Security Adoption v3](docs/ADR-shared-security-adoption-v3.md)
- [Hybrid Envelope Test Vectors](docs/hybrid-envelope-vectors.md)

## Attestation and certification readiness

`policy/control-crosswalk.edn` maps SOC 2 TSC common criteria (CC1-CC9, 33
criteria encoded) and a subset of ISO/IEC 27001:2022 Annex A onto the claims in
`registers/evidence-index.edn`. It holds clause numbers and **our own
descriptors** -- no requirement text from either standard is reproduced, and
`:control/descriptor` must not be quoted as if it were.

```sh
kbb --backend sci --classpath src scripts/check-crosswalk.cljk          # position
kbb --backend sci --classpath src scripts/check-crosswalk.cljk --gaps   # the controls that are short
```

Measured 2026-08-23:

| Framework | Encoded | Evidenced | Not mapped | design / impl / operating |
|---|---|---|---|---|
| SOC 2 TSC (Security) | 33 | 24 | 9 | 13 / 11 / **0** |
| ISO/IEC 27001:2022 Annex A | 13 of 93 | 8 | 5 | 2 / 6 / **0** |

Neither is ready, for two different reasons that must not be conflated:

- **Type I / Stage 1** is short because 9 TSC criteria have no evidence assigned
  at all -- control environment (CC1.1, CC1.4), external communication (CC2.3),
  fraud risk (CC3.3), human user provisioning (CC6.2), physical access to the
  mac-mini fleet (CC6.4), media disposal (CC6.5), recovery (CC7.5), and business
  continuity (CC9.1). These are documents and procedures, not code.
- **Type II / Stage 2** is short because **no claim in this repository carries
  operating strength**. Every workstream in
  `registers/remaining-operational-gaps.edn` is `:external-operation-required`
  and `:operational/readiness` is `:not-qualified`. `type-ii-readiness` reads
  that register directly and cannot be talked out of it by filling in the
  crosswalk -- `crosswalk_test.clj` proves this with a control that grants every
  claim operating strength and still gets `ready? false`.

`:unevidenced` is 0 today, and that is a property of how the first crosswalk was
written (only claims that exist in the evidence index were mapped), not a
statement that 24 criteria would satisfy an auditor. Extending the crosswalk
will make `:unevidenced` rise; that is the gap becoming visible, not a
regression.

## Registers

- [Control Crosswalk](policy/control-crosswalk.edn) (SOC 2 TSC / ISO 27001 Annex A)
- [Risk Register](registers/risk-register.edn)
- [Exception Register](registers/exception-register.edn)
- [Key Register](registers/key-register.edn)
- [Crypto Inventory](registers/crypto-inventory.edn)
- [Evidence Index](registers/evidence-index.edn)
- [Architecture Review Findings](registers/architecture-review-findings.edn)

## Verify

Run the tests and gates from the repo root (CI runs the same commands):

```sh
kbb -M:test                       # release-gate, crypto-policy, key-lifecycle, hybrid gate, adapters
kbb --backend sci --classpath src scripts/check-safe-release.cljk
kbb --backend sci --classpath src scripts/check-crypto-inventory.cljk
kbb --backend sci --classpath src scripts/check-hybrid-admit.cljk
kbb --backend sci --classpath src scripts/check-key-register.cljk --require-active
bb scripts/check-key-register.bb      # shape + forbid private PEM (key_lifecycle)
kbb --backend sci --classpath src scripts/check-key-lifecycle-drill.cljk
kbb --backend sci --classpath src scripts/check-key-rotation-drill.cljk --write
kbb --backend sci --classpath src scripts/simulate-revoked-signer.cljk --write --deliver
kbb --backend sci --classpath src scripts/emit-alert.cljk --smoke
kbb --backend sci --classpath src scripts/monitoring-heartbeat.cljk
```

### Pager webhook (optional real sink)

File sink always works (canonical alert map). Webhook POSTs vendor-adapted
bodies (Slack Incoming Webhook / PagerDuty Events API v2 / generic) selected by
`KOTOBA_SECURITY_ALERT_SINK` or URL heuristics. See
**[On-call / Pager](docs/on-call-pager.md)** and
[`registers/on-call-roster.edn`](registers/on-call-roster.edn).

```sh
# Local mock (no secrets)
kbb --backend sci --classpath src scripts/mock-webhook-sink.cljk --port 9876
export KOTOBA_SECURITY_ALERT_WEBHOOK='http://127.0.0.1:9876/alert'
# optional: force Slack shape against mock
export KOTOBA_SECURITY_ALERT_SINK=slack
kbb --backend sci --classpath src scripts/emit-alert.cljk --smoke

# Production vendor (only if URL exists in kagi/Keychain — never invent)
export KOTOBA_SECURITY_ALERT_WEBHOOK='https://hooks.slack.com/services/...'
# or PagerDuty:
# export KOTOBA_SECURITY_ALERT_WEBHOOK='https://events.pagerduty.com/v2/enqueue'
# export KOTOBA_SECURITY_PAGERDUTY_ROUTING_KEY='…'
kbb --backend sci --classpath src scripts/emit-alert.cljk --smoke
```

Env template (empty values only): [`.env.pager.example`](.env.pager.example).

Unset webhook → scripts report `webhook skipped` honestly and still exit 0 if
the file sink succeeds. See [Continuous Monitoring](docs/continuous-monitoring.md).

### FIPS non-claim

**This repository does not claim FIPS 140 validation.** Product-facing
statement and module-boundary checklist: [docs/fips-non-claim.md](docs/fips-non-claim.md).

`bb scripts/check-safe-release.bb --release` enforces the release evidence
packet strictly (kotoba-lang/kotoba#265): every required claim —
`:conformance-results`, `:package-verification`, `:sbom`, `:provenance`,
`:key-status-snapshot`, `:risk-review` — must be backed by evidence in
`registers/evidence-index.edn` or covered by an unexpired, owned entry in
`registers/exception-register.edn`, otherwise it exits non-zero.

## Primary Design Inputs

- `kotoba-lang/kotoba-lang/docs/adr/ADR-safe-capability-language.md`
- `kotoba-lang/kotoba-lang/docs/adr/ADR-kotoba-package-cid-lock.md`
- `kotoba-lang/kotoba-lang/docs/adr/ADR-kotoba-rad-git-sovereign-repo.md`
- `kotoba-lang/kotoba/docs/SECURITY-ARCHITECTURE.md`
- `kotoba-lang/aiueos/SECURITY.md`
- `90-docs/adr/2606271600-kotoba-stack-equivalences.edn`
