# provider-transport

Opt-in JVM socket/TLS provider for the bounded Kotoba transport ABI.

This is a Chicory tender plugin, not part of `kototama` core. It converts
already-decided `HostCaps` into bounded socket host functions and re-checks
endpoint allowlists, ABAC, information flow, approvals, TLS identity, byte
budgets, and connection budgets at the native I/O boundary.

Dependency direction is intentionally one-way:

```text
provider-transport -> kototama (tender ABI)
provider-transport -> security (shared policy)
```

`provider.tls-channel` additionally exposes an opaque, host-side TLS netlayer
for CapTP-style runtimes. It enforces exact endpoint and resolved-address
allowlists, HTTPS hostname verification, optional certificate pinning, socket
timeouts, and a bounded length-prefixed frame. The channel description is
inert metadata; only the live value can write, read, exchange, or close.

Certificate rotation uses `:peer-certificate-sha256-set`: deploy an explicit
old+new overlap set, rotate the server, then remove the retired digest. A
single pin and a rotation set are mutually exclusive, empty/wildcard sets are
rejected, and the channel description records which pin profile admitted it.

Run `kbb -M:test`.
