# Maturity

**Level: R2 live adapter**

Implemented:
- One-time challenge and verification result models.
- Host port for verification.
- Challenge kind validation.
- Datom emitters for challenge and result records.
- Attempt store and successful-code replay prevention.
- Digest verifier adapter boundary.
- HMAC-SHA1 HOTP/TOTP verifier implementation.
- `authenticator` engine adapter.
- Rate-limit policy over attempt counts.
- Email/SMS delivery adapter boundary with payload normalization.
- Contract tests for verifier delegation, replay prevention, attempt counts, digest payload mapping, rate-limit rejection, delivery payloads, and RFC HOTP/TOTP vectors.

Not yet R2:
- None.
