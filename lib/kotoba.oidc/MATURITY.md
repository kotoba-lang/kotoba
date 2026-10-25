# Maturity

**Level: R2 live verifier**

Implemented:
- OIDC auth request and ID-token verification result models.
- Host port for ID-token verification and userinfo.
- Nonce, issuer, and audience consistency checks after host verification.
- Datom emitters for auth request and ID-token result.
- Nonce replay prevention port with in-memory contract implementation.
- JWKS verifier adapter boundary for host JWT verification.
- HS256 JWT verifier implementation with pluggable claims codec.
- RS256 JWT verifier implementation using JWK RSA public keys.
- OIDC discovery and JWKS retrieval/cache implementation with pluggable codecs.
- JWK rotation policy with TTL refresh, forced refresh, and stale-on-error fallback.
- Production key revocation feed wrapper.
- OIDC claims mapping into `identity` subjects and credential evidence.
- Positive, negative, replay-prevention, JWKS adapter, HS256/RS256 signature, expiry, discovery, JWK rotation, identity mapping, and JWKS cache contract tests.

Not yet R2:
- None.
