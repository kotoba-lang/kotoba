# identity

Portable EDN model for identity subjects, attestations, and evidence references.

This repo is the shared substrate for identity-facing kotoba-lang libraries. It
does not verify documents, run biometrics, or score compliance risk.

## Passkey-first, chain-neutral principals

`identity.principal` separates the stable subject from every mechanism that
controls or addresses it:

- the principal is a DID or `urn:kotoba:principal:*` logical subject;
- a verified WebAuthn P-256 passkey is a replaceable controller;
- a smart account is a CAIP-10 linked account, not the subject itself;
- ERC-4337 accounts declare ERC-1271 verification and ERC-6492 when they are
  counterfactual; and
- an HD/EOA wallet may be linked for payment or custody, but is never the
  default identity root.

No chain is selected implicitly. Base appears only when a caller explicitly
links an `eip155:8453:*` account; Ethereum, another EVM chain, or a non-EVM
native account can be linked without changing the principal. The namespace is
pure data and validation: WebAuthn ceremony verification, chain signature
checks, persistence and capability admission stay in their existing owners.

A pending credential or account description is not proof. Only verifier-backed
`:verified` controllers can control a structurally valid document, and even
that fresh authentication does not grant a Kotoba capability.

## External trust adapters

`identity.adapters.eas` verifies host-decoded Ethereum Attestation Service
records against an explicit chain/contract coordinate plus mandatory schema and
attester allowlists. Revoked, expired, future-dated, mismatched, or unanchored
records fail closed.

`identity.adapters.human-passport` composes that EAS boundary with Human
Passport's current score schema. It pins the scorer, independently reapplies a
deployment minimum, checks the attested passing flag, and expires otherwise
non-expiring score attestations after 90 days. The result is a scoped
`[:identity :sybil-resistance]` claim and Sekisho evidence—not a general Kotoba
trust score and not KYC.

`identity.passport` is Kotoba's own answer to the same question, with no
single attester to trust (ADR-2610072000 in com-junkawasaki/root). Stamps are
signed claims in four classes (one allowlisted issuer, a k-of-n ceremony
quorum, a vouch from someone whose passport passes, or a Bitcoin / Ethereum /
Base / Filecoin fact the host re-derives). Each carries a nullifier, and
first-claim-wins over a ledger every witness applies with `registry-apply` is
the dedup: one credential backs one human, and vouch budgets are ledger rules.
A content-addressed policy fixes weights, class caps (vouches and chain facts
alone can never reach the threshold; `policy-problems` refuses a policy where
they could) and the threshold, so anyone can recompute `score`. A majority of
the policy's witnesses signs the resulting record, and `->identity` emits the
same scoped `[:identity :sybil-resistance]` claim and Sekisho evidence as the
Human Passport adapter. Pure: the host supplies Ed25519 verification,
SHA-256 and chain reads. Gitcoin's EAS score can still count, as one chain
stamp among others.

`identity.adapters.erc8004` models the current draft's separate Identity,
Reputation, and Validation registries. Registration creates an `:agent`
subject. Reputation and validation create scoped trust claims only from
explicitly allowlisted clients/validators; low results remain structured
refusals. The historical Etzhayyim monolithic `ERC-8004-shaped` contract is not
treated as compatible with this adapter.

All three namespaces are pure verification/composition boundaries.
`identity.adapters.evm` is the reference JVM host for pinned, read-only EAS and
Human Passport access: it verifies `eth_chainId`, calls the configured EAS and
Schema Registry contracts, and strictly decodes their ABI payloads. Run
`kbb -M:live-human-passport` for the non-mutating Base proof. The
historical official sample is intentionally expected to fail closed as expired.
Pass `--uid <attestation-uid>` (or set
`HUMAN_PASSPORT_ATTESTATION_UID`) to require a current attestation to pass
against the exact Itonami policy. On 2026-08-28 the read-only proof accepted
`0x0c57d851…ffd8f5c`: official schema/attester, scorer 335, score 273090,
threshold 200000, six stamps, and no chain write.

The same JVM host provides coordinate-driven ERC-8004 registry calls and bounded
registration-document retrieval for HTTPS, `ipfs://` through an explicitly
configured gateway, and base64 JSON `data:` URIs. The draft expects per-chain
singleton deployments but does not define canonical addresses, so no registry
is selected ambiently. Once coordinates are configured,
`identity.adapters.ledger/persist-trust-bundle!` atomically commits a fully
verified subject, evidence, attestations, and scoped claims.

`identity.trust-policy` keeps verified evidence separate from ambient
authorization. It currently activates one exact Itonami action,
`identity.sybil-step-up`, binds the EAS recipient to the authenticated
Principal account, and explicitly grants no capability. Kotobase EAS action
admission and Murakumo Identity/Reputation admission are active in their
service repos. Murakumo Validation remains explicitly deferred until an
official governed deployment exists. The decision and remaining boundaries are recorded in
`docs/adr/2608281000-external-trust-is-scoped-evidence-not-ambient-authority.md`.

`identity.directory` defines the portable organization directory used by
cloud-itonami: domain-scoped users and groups, lifecycle status, delegated
administrator roles, and active-seat counting.
