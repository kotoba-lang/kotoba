# Maturity

**Level: R2 live adapter**

Implemented:
- FaceID request and attestation metadata models.
- Host port for local authentication.
- Raw face image/template/embedding rejection.
- Audit datom emitter for attestation metadata.
- LocalAuthentication adapter boundary for FaceID policy evaluation.
- EDN local-auth device registry implementation.
- Replay challenge store and one-time attestation flow.
- Device-bound attestation store.
- Step-up integration through `authentication.adapters.external-factors`.
- Production Apple LocalAuthentication bridge.
- Positive, negative, datom, adapter payload, enrolled-device, unenrolled-device, replay-prevention, and device-bound storage contract tests.

Not yet R2:
- None.
