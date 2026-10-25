# Maturity

**Level: R2 live verifier**

Implemented:
- SAML AuthnRequest and assertion verification result models.
- Host port for assertion verification.
- Post-verification checks for failed assertions, issuer separation, and audience presence.
- RelayState one-time consumption store.
- Datom emitters for request and assertion result.
- XML Signature verifier adapter boundary for host SAML verification.
- Condition-window verifier for `NotBefore` / `NotOnOrAfter`.
- Clock-skew tolerant condition-window verifier.
- Secure live XML assertion parser for issuer, subject, audience, condition window, assertion ID, and signature presence.
- IdP metadata retrieval/cache implementation.
- Cryptographic XML Signature trust-chain policy wrapper.
- Positive, negative, replay-prevention, XML adapter, live XML parsing, condition-window, clock-skew, and metadata cache contract tests.

Not yet R2:
- None.
