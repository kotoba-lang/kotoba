# Maturity

**Level: R2 live adapter**

Implemented:
- Session and session event models.
- Active/expired check, refresh, and revoke transitions.
- Datom emitters for session and event records.
- Session store port with in-memory contract implementation.
- Key-value store adapter boundary.
- Durable EDN file key-value store implementation.
- Datomic/Kotoba datom-backed session store adapter with lookup-ref transaction payloads.
- Datomic/Kotoba cluster schema bootstrap and transaction audit export boundary.
- Cookie, header, token, device, and IP binding validation.
- Session rotation with old-session revocation and rotated-from provenance.
- Idle timeout handling on touch.
- Concurrent active-session limit policy for indexed stores.
- Contract tests for lifecycle, revocation, event persistence, key-value payload mapping, Datomic/Kotoba datom persistence, durable reload, binding mismatch rejection, rotation, idle timeout, and concurrency limiting.

Not yet R2:
- None.
