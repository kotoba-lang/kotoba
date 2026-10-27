# ADR-0277 — The native desktop's key: device-bound, consent-bound, and never exported

Date: 2026-10-27

## Status

Accepted as a decision (owner delegation 2026-10-27: recommendations adopted). **Nothing is implemented.** It fixes the custody and persistence
design that W3 of ADR-0275 was waiting for. Hosted-side release and signing authority stay with ADR-0274.

## Decision

1. **Scope.** One device key for the native desktop. It exists to sign challenges from the user's own apps (sign-in, dapp requests). It is not a funds wallet:
   no transfer, trade or on-chain settlement is signed here (those stay outside this repository by the repository's chain-integration rule).
2. **Algorithm.** For a signature that never leaves the device (re-verified locally, e.g. after a reboot), Ed25519. For any signature that leaves the device, the
   post-quantum floor applies: Ed25519 together with ML-DSA-65, both verified, no classical-only downgrade (the repository's cryptographic boundary rule). The first
   slice implements the local half only and says so.
3. **Entropy and creation.** The key is drawn from the hardware RNG the kernel already exposes, once, on the user's first explicit request, through the W1 consent
   surface (an operation naming "create device key", data: none). It is never created implicitly.
4. **Persistence.** The key lives in its own sectors on this machine's volume, written with read-back and a checksum, with its own magic, using the same native ATA
   commit path as the draft store. A different volume has a different key.
5. **Never exported.** No code path displays, copies or sends the private key. The public key and its identifier are the only things shown (the trust summary's `DID`
   and `Wallet` lines become live from them).
6. **Every signature is a consent.** Each sign goes through the W1 surface: it names the requester, the operation and the data category, and signs only after Allow. Deny signs nothing.
   Synthetic input in gates proves the state machine, never a human consent.
7. **Gate (W3).** `guest-browser-wallet-sign` prints its marker only if: creation is refused without Allow; a fresh boot keeps the same public key; a challenge signed
   with this key verifies and one signed by another device's key does not; Deny signs nothing; and the private bytes appear in no frame, serial or exported word.

## Order and prerequisites

1. The owned-region table and a free surface word for the live trust summary (ADR-0276 steps 1 to 3); without them W2 and the `DID`/`Wallet` lines stay static.
2. Ed25519 and SHA-512 in the native desktop kernel as Kotoba objects, with test vectors; ML-DSA-65 before any signature leaves the device.
3. The key sectors and their commit/restore, with a tampered-sector refusal.
4. The signing consent request, then the gate.

## Not decided here

Key rotation and revocation, backup of the key (W6 covers records, not this key), and multi-device identity (a DID document anchoring several device keys).
