# Signer key lifecycle protocol v1

Status: enforced regulated baseline  
Date: 2026-07-23

`aiueos.key-lifecycle` distributes signer authority as root-signed,
monotonically chained epochs. Each bundle binds:

- epoch number and previous-bundle SHA-256;
- issue and expiry times;
- root authority id;
- signer public keys, lifecycle status and validity windows;
- delegation parent, delegation permission and component scopes.

A node accepts exactly its next epoch and the expected predecessor digest.
Replay, rollback, skipped epochs, forked predecessors, bad root signatures,
expired bundles, invalid delegation chains and scope expansion all fail closed.

Active keys materialize directly into `aiueos.signing`'s signer registry and
component-signer bindings. Revoked, retired, suspended, expired, and
compromised keys receive no authority. Rotation is an overlapping epoch with
both old and new keys active; compromise recovery advances to an epoch where
the old key is compromised and only the replacement remains authorized.

The launcher consumes `:aiueos/key-lifecycle` from a deployment policy before
manifest verification. The node checkpoint must be stored in sealed monotonic
storage. Regulated admission binds the root fingerprint, current epoch and
digest and requires dated convergence and compromise-recovery exercises.

The root private key is offline tooling/HSM material and is never part of the
deployment policy.
