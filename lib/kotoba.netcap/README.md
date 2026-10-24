# kotoba-lang/netcap

Portable CLJC networking capability contracts for kotoba runtimes.

`netcap` models TCP, UDP, and DNS access as WIT-style capability tokens. It
does not open sockets directly; hosts inject concrete networking drivers and
the manager gates calls through policy.

## TLS client streams: `kotoba.netcap.tls` + `kotoba.netcap.tls-host` (2026-09-25)

The kotoba replacement for `javax.net.ssl` at the call sites that open a TLS
client stream. Same split as [`kotoba-lang/process`](https://github.com/kotoba-lang/process):

- **`kotoba.netcap.tls`** — pure: request validation (`validate-connect`, every
  refusal a literal keyword in `refusals`), defaults (`normalize`), SNI naming
  (`server-name`: none for an IP literal, RFC 6066 §3), and the capability:
  a `connector` is a `TlsDriver` plus the endpoints it was granted
  (`:allow` `:any` / `:none` (default) / a set of hosts and `[host port]`
  pairs). `connect!` validates, checks the grant, then calls the driver. A
  refused request never reaches the driver; a request's `:identity` never
  appears in ex-data.
- **`kotoba.netcap.tls-host`** — the host's TLS stack as `system-driver`, and
  `connect` (a connector over it granted `:any`: the host's own door, where
  `kotoba.lang.process-host/sh` stands for processes — guest code is handed a
  connector instead). JVM: JSSE, returns the connected `SSLSocket` with the
  handshake completed. kbb: `node:tls`, returns a `js/Promise` of the
  connected `TLSSocket` (Node sockets are asynchronous). Also `session-info`,
  `tls-exception?`, and (JVM only) `ssl-context` — the `SSLContext` a
  `:trust`/`:identity` pair describes, for code that must hand one to a JDK
  server or HTTP client.

```clojure
(require '[kotoba.netcap.tls-host :as tls-host])
(tls-host/connect {:host "imap.gmail.com" :port 993 :timeout-ms 20000})
;; JVM => connected javax.net.ssl.SSLSocket; kbb => Promise<tls.TLSSocket>
```

Request: `:host` (ASCII STD3 name or IP literal), `:port` 1..65535,
`:timeout-ms` read timeout 1..600000 (default 20000), `:connect-timeout-ms`
(default `:timeout-ms`), `:server-name`, `:trust` (`:system` default |
`{:anchors-pem "..."}` | `{:pin-spki-sha256 #{"<hex>"}}`), `:identity`
(`{:cert-chain-pem :key-pem}`, PKCS#8, for mTLS), `:protocols`
(subset of `#{"TLSv1.2" "TLSv1.3"}`).

**The certificate is always checked against the name** for `:system` and
`:anchors-pem` trust (HTTPS endpoint identification) and there is no switch
to turn it off. A bare `SSLSocketFactory/getDefault` socket does *not* check
the name — JSSE leaves endpoint identification off for a socket — so a call
site moved here refuses a peer the old code accepted. That is measured, not
assumed (below). With `:pin-spki-sha256` the pin is the identity: the leaf's
SubjectPublicKeyInfo SHA-256 is checked, not the chain or the name.

`:system` is the host's store and the hosts differ: the JDK's `cacerts` on the
JVM, Node's bundled Mozilla store on kbb.

### What is measured

Loopback handshakes against a server holding a test PKI
(`test/kotoba/netcap/tls_fixtures.cljk`: EC P-256 CA, a `localhost`-only
server, a client certificate, and an unrelated self-signed `localhost`),
the same nine cases on both hosts:

| case | kotoba (JVM, JSSE) | raw `SSLSocketFactory` socket (JVM) | kotoba (kbb, node:tls) |
|---|---|---|---|
| trusted issuer, name matches | accepted | accepted | accepted |
| trusted issuer, socket to `127.0.0.1` (cert says `localhost`) | **refused** `No subject alternative names matching IP address` | **accepted** | **refused** `ERR_TLS_CERT_ALTNAME_INVALID` |
| unknown issuer, anchors / `:system` | refused (PKIX) | refused | refused |
| SPKI pin right, to `127.0.0.1` | accepted | — | accepted |
| SPKI pin wrong | refused `spki-pin-mismatch: <seen>` | — | refused `ERR_TLS_SPKI_PIN_MISMATCH` |
| mTLS with / without client identity | accepted / refused | — | accepted / refused |
| `:protocols #{"TLSv1.2"}` | TLSv1.2 negotiated | — | TLSv1.2 negotiated |

JVM: `kbb --backend sci scripts/jvm_test.cljk kotoba.netcap.tls-test kotoba.netcap.tls-jvm-test kotoba.lang.netcap-test`
(a real JDK 21 is the oracle; the runner mirrors `.cljk` → `.cljc`).
Disabling endpoint identification in `tls_host.cljk` turns the second row red
(2 failures, 1 error) — the row tests something. kbb: `kbb -M:test`.

### Boundary

- `kotoba-lang/org-ietf-tls` is a TLS 1.3 **protocol implementation** in
  portable code (every primitive injected, peer authenticated by SPKI pin,
  no chain validation). `kotoba.netcap.tls-host` drives the **host's** TLS
  stack with chain validation; the two share the pin format.
- `kotoba-lang/provider-transport` is a Chicory tender plugin for the bounded
  transport ABI (JVM sockets for WASM guests); it is not a library for
  `.cljk` call sites.
- `kotoba-lang/capability-crypto-tls` / `capability-net-connect` are atomic
  authority packages (contract-only); this repo is where a host driver for
  such a grant lives.

Root codemod: `scripts/migrate-javax-net-ssl-to-kotoba-netcap-tls.cljk`.

## Test

```bash
kbb -M:test                                   # kbb: pure + node:tls loopback
kbb --backend sci scripts/jvm_test.cljk kotoba.netcap.tls-test kotoba.netcap.tls-jvm-test kotoba.lang.netcap-test
```
