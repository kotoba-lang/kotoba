# Sealed audit and component-state storage

Status: enforced production baseline  
Date: 2026-07-23

## Audit

`aiueos.sealed-audit` stores independently AES-256-GCM sealed records. AAD
binds format version, sequence, external key id and predecessor hash.
Retention atomically reseals live records, backup bytes are verified before
restore, and removal of an external per-subject key provides crypto-erasure.

The internal chain detects mutation, insertion and reordering. After every
durable append batch, production retains an Ed25519-signed chain head outside
the log. The head binds record count, last record hash and complete log digest,
therefore a valid-prefix suffix truncation also fails verification.

## Component state

`aiueos.sealed-state` stores one bounded AES-256-GCM snapshot per component.
AAD binds component identity, monotonic state version, external key id and
creation time. Restore requires the expected component and a minimum version.
Wrong keys, tampering, identity substitution and rollback fail before
plaintext release.

Snapshot replacement is atomic. Backups authenticate before copying and again
before restore. Deletion authenticates the exact target first; external
per-component/per-subject key removal provides crypto-erasure independently of
filesystem remanence.

Keys are inputs supplied by a KMS/HSM adapter and never serialized beside
ciphertext. The software tests establish the adapter contract; production
custody evidence must identify the real provider and key policy.
