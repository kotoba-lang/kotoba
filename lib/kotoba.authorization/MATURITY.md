# Maturity

**Level: R2 live adapter**

Implemented:
- Authorization request and decision models.
- Host port for policy/capability decision delegation.
- Request validation for principal, action, resource, and request ID.
- Decision validation for known outcomes, request matching, and deny reason.
- Datom emitters for request and decision records, with identity carried as a `:db.unique/identity` attribute rather than a per-transaction `:db/id` tempid, absent attributes dropped rather than asserted as nil, and nested EDN encoded as `pr-str` blobs.
- One canonical schema (`authorization.schema`) in Datomic installation tx-data, converted for the in-memory store by `langchain.db/schema-from-tx-data`.
- Policy engine adapter boundary.
- In-process rules policy engine implementation.
- Policy bundle identity and version propagation.
- Policy-effect trace and obligation normalization.
- External `policy` engine adapter with `cacao` capability verification.
- Replay-resistant decision ledger adapter boundary.
- Durable decision ledger on `langchain.db` + `journal`: an append-only EDN history replayed into a queryable index on open, with duplicate request-id rejection evaluated as a Datalog query rather than a bookkeeping set kept alongside the data.
- Contract tests for delegation, invalid request/decision rejection, policy payload mapping, allow/deny rules, default deny, bundle provenance, effect traces, obligations, and — for the ledger — nested request pull with blob round-trip, request/decision reference join, replay rejection, cross-transaction entity identity, undecided requests, nil suppression, restart recovery, and journal history.

Not yet R2:
- None.
