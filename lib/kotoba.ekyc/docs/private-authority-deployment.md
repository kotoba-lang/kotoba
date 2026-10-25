# Private authority deployment

`kotoba-identity-authority` is a service-binding-only Worker with no public routes,
workers.dev address, preview URLs, or invocation logging. The Kotoba Cloud gateway
supplies its authenticated Principal through the private binding. Requests with a
public origin or without that Principal are rejected.

The service is a **closed deployment entry**, not an activated vault. Its status
endpoint distinguishes the installed authority connection from the still missing
storage, key management and review policy. Every mutation and evidence read is
refused, regardless of supplied bindings. Merely adding bindings must never open
intake before their adapters and operational qualification are complete.

Production inspection on 2026-09-13 found the datom engine configured as
`legacy-public`, with no authority registry, key-unwrapper, claim-store, audit-sink
or authoritative head-store binding. No `kotodama-kms` deployment existed in the
same account. These findings do not establish absence in other accounts.

Activation needs:

1. A qualified private Kotobase tenant with encrypted metadata and authenticated
   CID reads/writes, plus authoritative compare-and-set and restart recovery.
2. A case-bound key provider whose deletion cannot be undone by recovering old
   state or backups. The public archive and a Worker-wide permanent seed are not
   substitutes. A service URL/name or provisioned account is needed to implement
   and qualify the concrete adapter; no endpoint has been invented here.
3. The owner's designated reviewer accounts/public signing keys, published operator
   and contact details, selected retention period, automatic deletion and recovery
   procedure. The agent must not appoint itself or infer reviewers from login.
4. Synthetic end-to-end qualification of upload/readback, contention, unauthorized
   reads, reviewer assignment/signatures, expiry, deletion and restart before real
   documents are accepted.

`wrangler.identity.jsonc` deliberately has no storage or key binding until these
providers exist. The next implementation replaces the closed entry with the
existing `identity-intake-service/handler` using qualified vault ports. Existing
signature/review tests alone do not qualify an external provider.
