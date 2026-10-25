# Bootstrap Attestation — ooyake reconcile-live / authoritative promotion

**Actor**: ooyake 公 · **ADR**: 2606021600 · **Gate**: §4 G4 + roadmap R1 · **Mode**: BOOTSTRAP (Council < quorum)

## Authorization

Per the etzhayyim bootstrap-phase governance precedent (constitutional ADRs are
accepted under *proposed* status by **Seat 1 (Founder, Lv7)** alone during the
Bootstrap Council RFP — see `COUNCIL.md`, ADR-2605192300 §"bootstrap Council 権限境界
(3-of-5, Phase 2 まで limited)"), and given the organization currently has **a single
participant** (Seat 1) so a 3-of-5 Council multisig is *physically* unconstructable,
the Founder hereby grants a **provisional bootstrap authorization** to release the
ooyake `reconcile` authoritative-promotion path that ADR-2606021600 otherwise gates
on Council Lv6+ ≥3.

- **Granted by**: Seat 1 — Jun Kawasaki (Lv7, Founder)
- **Date**: 2026-06-02 (recorded in the authoring session)
- **Instrument**: provisional, bootstrap-phase. **Re-ratification REQUIRED** by a
  Council Lv6+ 3-of-5 multisig the moment the Council reaches quorum (Seats 2–5
  filled after the 2026-06-19 RFP). Until then this stands under *proposed* status,
  exactly as the constitutional-ADR-during-RFP precedent.
- **Cryptographic attestation**: the Lv7 signing key (macOS Keychain
  `service=etzhayyim, account=DID_PRIVATE_KEY_ED25519`) signature is to be appended
  by the operator out-of-band; this document is the human-readable record of the
  authorization given in session. No agent extracted or used the private key.

## Scope (what this authorization covers — and what it does NOT)

**Covers** — promotion of units whose provenance is an **official government code
register** already verifiable without a live fetch:

- 47 都道府県 — ISO 3166-2:JP + 全国地方公共団体コード (2-digit) → `:authoritative`
- JP 市区町村 in the bundled dataset — 全国地方公共団体コード (from
  `etzhayyim-project-states`, citing 地方自治法 / e-Gov) → `:authoritative`

These flip `:sourcing :representative` → `:sourcing :authoritative` and
`:verification-status :unverified-seed` → `:maintainer-verified`, each carrying
`:gov.unit/attestation` = this record.

**Does NOT cover** (stay `:representative`, honest — G5):

- The 456 global municipalities with names+websites but **no official code** — not
  promotable without source verification.
- The full JP 1,718-municipality long tail (only 71 are bundled) — needs a fuller
  authoritative dataset, not fabricated here.
- The 172 ISO3 country stubs (code-only placeholders).
- Any **live network fetch** of external registries — that remains its own
  capability; this attestation authorizes promotion of already-bundled official-code
  data only. Live `mode="live"` fetch stays gated pending Council ratification.

## Controls (unchanged, all still in force)

G3 observational mirror · G4 public-data-only · G5 non-fabrication (only official-code
tiers promoted; everything else stays representative) · G6 no personal data · G9
read-side only · G10 never a target-list. The promotion is READ-SIDE (re-classifies
ooyake's own atlas datoms); it touches no government record.

## Re-ratification trigger

When the Bootstrap Council reaches **3-of-5 Lv6+**, this provisional authorization is
presented for ratification (`COUNCIL-PROPOSAL-reconcile-live.md`). If ratified, it
becomes permanent; if rejected, the promoted units revert to `:representative` and
the `:gov.unit/attestation` datoms are retracted (datomic as-of history preserves the
full trail).
