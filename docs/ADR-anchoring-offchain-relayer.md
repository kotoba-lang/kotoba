# ADR — Anchoring & slashing: the off-chain relayer boundary

- Status: Accepted (documents current behaviour + the operating-entity boundary)
- Date: 2026-06-22
- Context: enterprise security review (item **d**) — "anchoring / slash の
  on-chain 経路を本番化、または 'off-chain relayer 前提' を契約上明記"
- Related: [`SECURITY-ARCHITECTURE.md`](./SECURITY-ARCHITECTURE.md) (R2a/R3d),
  [`ADR-sealed-cold-tier.md`](./ADR-sealed-cold-tier.md),
  [`SECURITY-AUDIT-PACKAGE.md`](./SECURITY-AUDIT-PACKAGE.md) (RR-8)

## Decision

Kotoba **builds** the on-chain payloads for tamper-evidence anchoring and for
custody slashing, but **does not submit them on-chain itself**. Transaction
signing, on-chain settlement, and DID/on-chain origination are
**etzhayyim-exclusive** (the operating-entity boundary, per the project
`CLAUDE.md` and ADR-2605231525). The EVM/BTC surface in `kotoba-auth` is
**read + verify only**.

This ADR does **not** change that boundary — it records it explicitly and gives
operators the contractual language to use while on-chain enforcement remains
out of band.

## The build-here / submit-elsewhere seam

| Capability | Kotoba builds (in-repo) | Submitted by (out of repo) |
|---|---|---|
| Audit-chain anchoring (R2a) | `audit.anchorPayload` → `AnchorBridge.commitRoot` calldata committing the audit-graph head to Base (`kotoba-server` + `kotoba-evm`) | off-chain relayer (operator / etzhayyim) |
| Custody slash (R3d) | `key.reportUnreceiptedRelease` → `CustodyUnreceiptedRelease` warrant + pinned evidence (`kotoba-custody` `audit`, `kotoba-dht`, `kotoba-server`) | off-chain relayer → `MishmarBondEscrow` (Solidity, Council-gated) |

Everything cryptographic and accountability-bearing (signed CommitDag, signed
custody grants, warrants, anchor calldata) is produced and verifiable in-repo.
What is deferred is purely the **on-chain submission/execution** step.

## What this guarantees today (without on-chain submission)

- **Internal tamper-evidence:** the CommitDag is Ed25519 author-signed and
  `audit.verifyChain` detects any break in the chain. An operator cannot
  *silently* rewrite history that a verifier has already observed.
- **Non-repudiable custody grants:** an unreceipted release produces a
  self-signed warrant identifying the accused DID with pinned evidence.

## What is NOT guaranteed until anchoring is submitted on-chain

- **Externally-anchored immutability.** Until `commitRoot` calldata is actually
  mined on Base, a verifier who has *not* independently retained a prior audit
  head cannot prove the operator did not rewrite the chain wholesale and re-sign
  it. The guarantee is "tamper-evident to anyone holding a prior head," not
  "tamper-proof against the operator."
- **Economic slashing.** The warrant is built and evidenced, but no bond is
  actually slashed until the relayer submits to `MishmarBondEscrow`. The
  deterrent is only as strong as the relayer's liveness and the bond's existence.

## Residual risk (RR-8)

A malicious or compromised operator who also controls the relayer can withhold
anchoring and slash submission. Mitigations available now:

1. **Independent head retention.** Customers/auditors periodically pull and store
   `audit.anchorPayload` (or the audit-graph head) out of band; any later
   divergence is provable. This is the cheapest, strongest immediate control.
2. **Independent relayer.** Run the anchoring relayer under a party distinct from
   the data operator (separation of duties).
3. **Anchoring SLA + monitoring.** Alert if no `commitRoot` is observed on-chain
   within the agreed window.

## Contractual / SLA language (use until on-chain submission is productionized)

Recommended clauses for an enterprise customer security addendum:

> **Audit anchoring.** The Provider commits the audit-log head (`commitRoot`
> calldata produced by `audit.anchorPayload`) to the Base chain via an
> anchoring relayer at least every **N hours**. The Customer may independently
> retain the anchor payload; the Provider warrants that the on-chain anchor,
> once submitted, matches the retained head.
>
> **Anchoring relayer independence.** The anchoring relayer is operated by
> **[independent party / escrow agent]**, separate from the data-plane operator.
>
> **Custody slashing.** Unreceipted key-release warrants
> (`CustodyUnreceiptedRelease`) are produced and evidenced by the system;
> on-chain bond slashing via `MishmarBondEscrow` is executed by
> **[Council / etzhayyim]** as the settlement authority. Until executed, the
> warrant is admissible evidence but carries no automatic economic penalty.
>
> **Limitation.** Tamper-evidence is cryptographic and continuous; externally
> anchored immutability is effective only from the first on-chain `commitRoot`
> the Customer can observe or has independently retained a prior head for.

## Triggers to revisit (productionize on-chain)

Re-open this ADR to move submission in-house only if the operating-entity
boundary changes. Until then, the controls above are the contract. Productionize
when:

- a regulatory requirement mandates operator-independent immutability, or
- the Council authorizes a kotoba-resident relayer key (which would cross the
  current etzhayyim-exclusive boundary and needs its own ADR).

## Consequences

- No code change in this repo: the boundary stands. This ADR + the audit package
  RR-8 entry are the deliverable for review item **d**.
- Enterprise deployments must adopt the contractual language and at least control
  #1 (independent head retention) to claim meaningful immutability.
