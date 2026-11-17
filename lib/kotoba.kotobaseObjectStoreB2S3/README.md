# Kotobase B2 S3 object store

This package owns one capability: validated Backblaze B2 S3 object transport.
It signs requests with SigV4 and reads or writes bytes and JSON objects.

It does not own API admission, authentication, billing, graph semantics, graph
heads, or physical index layout. Both `kotobase-api-gateway-cljs` and
`kotobase-graph-database` may depend on it; they must not depend on each other
for storage transport.

Cloudflare Workers are a supported runtime consumer, not part of this
package's capability name or contract.
