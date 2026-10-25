## Kotoba Identity additions

Cryptographic components and tests are implemented; production enrollment,
canonical storage host, real trust distribution, supervised-review operations,
phone app distribution and physical passport qualification remain pending.
See [Kotoba Identity v1](docs/kotoba-identity-v1.md). The historical level below
refers to the earlier provider-port substrate only.

# Maturity

**Level: R2 live adapter**

Implemented:
- eKYC session and evidence models.
- Provider host port for session start, evidence submit, and result fetch.
- Status and check validation.
- Required-check completion aggregation.
- Audit datom emitters for sessions, evidence, and completion decisions.
- Provider adapter boundary for session creation, evidence upload, and result retrieval.
- Evidence custody adapter boundary for evidence commits before provider upload.
- Durable EDN provider and custody implementations.
- Identity ledger bridge for verified evidence and completion attestations.
- Kagi evidence custody adapter with deterministic evidence refs.
- Verifiable Credential issuer boundary for completed eKYC evidence.
- Production provider transport adapter.
- Contract tests for provider delegation, completion, datom shape, provider/custody payload mapping, Kagi custody, VC issuance, durable state persistence, and identity ledger projection.

Not yet R2:
- None.
