# Maturity

**Level: R2 live verifier**

Implemented:
- EDN models for WebAuthn challenge, credential, assertion, and PRF envelope.
- Host port for registration, authentication, and PRF derivation.
- Validation for ceremony, transport, and successful assertion requiring user
  presence plus user verification.
- Datom emitters for challenge, credential, and assertion records.
- Challenge replay prevention port with in-memory contract implementation.
- WebAuthn ceremony verifier adapter boundary for registration, authentication,
  and PRF derivation.
- HMAC ceremony verifier implementation for local registration/authentication tests.
- Production boundary for clientDataJSON/authenticatorData verification, attestation trust-chain policy, and browser/OS ceremonies.
- Positive, negative, replay-prevention, ceremony adapter, and HMAC verifier contract tests.
- `webauthn.adapters.edge`: real WebAuthn L2 ceremony verification on
  WebCrypto only (Cloudflare Workers / browsers) — clientDataJSON
  type/origin/challenge, authenticatorData bounds-checked parsing with
  rpIdHash and user-present enforced on BOTH ceremonies, COSE EC2/P-256
  credential-key extraction, and ECDSA assertion verification
  (`webauthn.der` bridges DER to the raw IEEE-P1363 form `crypto.subtle`
  requires). Storage, key custody and session issuance are deliberately the
  caller's.
- `webauthn.virtual-authenticator` (test): a P-256 authenticator that really
  signs, so the edge adapter is exercised against live ceremonies —
  including ones that misbehave (wrong origin, wrong RP, user-present clear,
  tampered signature, a registration replayed as a login) — rather than
  against fixtures frozen alongside whatever bug produced them.

Not yet R2:
- None.
