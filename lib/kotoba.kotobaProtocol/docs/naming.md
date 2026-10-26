# Naming

A name is a **mutable pointer, not a hash**. The canonical public form is
`ipns://{k51}`.

| Existing surface | Naming projection |
|---|---|
| Git `refs/heads/main` | mutable ref |
| IPNS k51 | key-derived name, not a server |
| DNS / DNSLink | discovery alias toward IPNS |
| HTTP `/{org}/{repo}` | naming projection, not content identity |
| package tag such as `latest` or `1.2.3` | mutable name; the lock hash is identity |
| `:kotoba.app/id` | reverse-DNS local name |
| `:kotoba.app/latest` | provider actor's key-derived IPNS name |

IPNS is the degenerate action/overlay link: one name points to one current CID.
When an actual graph is needed, use datoms/CreateLink-shaped edges rather than
inventing more names.

The executable seam is `kotoba.protocol.naming/lookup-live` and `publish-live`.
Hosts inject `kad.routing/resolve` and `publish` adapters for delegated
`GET`/`PUT /routing/v1/ipns/{k51}` operations. The protocol has no Kad runtime
dependency and is not a DHT node.

A returned name that differs from the requested name fails with
`:name-mismatch`. A changed value CID is normal—that is the purpose of naming.
A real 404 becomes `:not-found`; silence from every router becomes
`:all-routers-failed`. The two states are not interchangeable.
