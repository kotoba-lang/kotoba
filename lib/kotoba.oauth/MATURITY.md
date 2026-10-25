# Maturity

**Level: R2 live transport**

Implemented:
- OAuth authorization request, token request, and token result models.
- Host port for token exchange and introspection.
- Authorization-code checks for code and PKCE verifier references.
- Refresh-token check for refresh token reference.
- Datom emitters for authorization request and token result.
- OAuth callback handling with state equality and one-time state consumption.
- HTTP token-endpoint/introspection adapter boundary.
- Java HttpClient token-endpoint/introspection transport with pluggable codecs.
- Provider metadata discovery and in-memory metadata cache.
- Live token introspection normalization and active-token guard.
- Client authentication policy for Basic, post body, bearer, and private-key-jwt assertion forms.
- Retry wrapper for retryable HTTP/transport failures across GET and POST with injectable exponential backoff.
- Token signature validation adapter.
- Positive, negative, replay-prevention, HTTP adapter, discovery, introspection, client-auth, local-server transport, backoff, and retry contract tests.

Not yet R2:
- None.
