# oauth

OAuth 2.0 flow substrate: authorization request, token response, and host-port
exchange/introspection. Network calls and client secrets stay outside this repo.

For the raw RFC 6749/PKCE spec-as-data substrate (zero deps, no host
assumptions), see [kotoba-lang/org-ietf-oauth2](https://github.com/kotoba-lang/org-ietf-oauth2).
This repo is the result-shape/substrate layer consumed by
[kotoba-lang/authentication](https://github.com/kotoba-lang/authentication).
