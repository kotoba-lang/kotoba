# Maturity

**Level: R2 live adapter**

Implemented:
- TouchID request and attestation metadata models.
- Host port for local authentication.
- Raw fingerprint/template rejection.
- Audit datom emitter for attestation metadata.
- LocalAuthentication adapter boundary for TouchID policy evaluation.
- EDN local-auth device registry implementation.
- Replay challenge store and one-time attestation flow.
- Device-bound attestation store.
- Step-up integration through `authentication.adapters.external-factors`.
- Production Apple LocalAuthentication bridge.
- Positive, negative, datom, adapter payload, enrolled-device, unenrolled-device, replay-prevention, and device-bound storage contract tests.

Not yet R2:
- None.
