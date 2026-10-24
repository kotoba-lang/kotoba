# Account links against a self-managed Principal

Status: admission core implemented; production authority adapters and migration pending.

A stable Principal is distinct from a login credential, a chain-qualified account,
controller keys and vault encryption keys. `identity.authority/admit-link` binds
an account proof and an existing controller proof to exactly the same canonical
operation, including Principal, genesis, prior head/version, audience, nonce,
purposes and expiry. Unknown fields fail closed. Login, payment and payout links
cannot grant recovery or controller authority.

The host supplies cryptographic controller/account verifiers and a verifier for
both finality and freshness of the pinned authority head. Those ports must return
literal true. Descriptive evidence, an email, a server receipt or a quorum over
another block does not suffice. No fallback is supplied when a port is absent.

Admission produces `pending-commit`, consumes the nonce and increments the
version in one proposed transition. Persist with CAS or certified consensus;
activate only after independently verifying the new committed head. The library
does not invent a DID method, a CID, a quorum or storage durability.

Production adapters still required: WebAuthn/PRF custody, EVM EOA and contract
account proofs (including chain RPC verification), Inga authority admission and
final/current certificates, and durable atomic persistence. Existing Itonami User
DIDs and memberships and Torihiki positions must retain their identifiers during
migration. Kagi vault unlock is a separate action; kagitaba is an item model, not
a storage transport. A Node receives only the selected Wi-Fi item encrypted for
that Node, never the vault master key.

The focused SCI regression suite passed 24 tests / 78 assertions on 2026-10-07,
including two actual Node Ed25519 signatures and tampering. This is core/host-port
qualification, not a real EVM/WebAuthn, independent quorum, recovery or production
vault qualification. No production Principal has been migrated by this change.
