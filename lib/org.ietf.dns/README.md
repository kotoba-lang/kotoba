# nameserver

[![CI](https://github.com/kotoba-lang/org-ietf-dns/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-ietf-dns/actions/workflows/ci.yml)

Renamed from `nameserver` (reverse-domain naming for the external spec it
implements — RFC 1035 is an IETF RFC — same `org-<body>-<spec>` convention as
this org's other IETF-RFC repos: `org-ietf-turn`, `org-ietf-ical`, etc.).

An **authoritative DNS nameserver** — a real RFC 1035 wire-protocol UDP/TCP
server you can `dig` against — plus an **alt-root custom-TLD bridge** that
resolves made-up TLDs (e.g. `.hogehoge`) to kotoba-lang's key-derived IPNS
self-sovereign names ([`ipns`](https://github.com/kotoba-lang/ipns)) via the
[dnslink](https://dnslink.io) convention.

This closes a gap the existing DNS-adjacent libraries in this org leave
open: [`zone`](https://github.com/kotoba-lang/zone) models zone files as
EDN and [`godaddy-dns`](https://github.com/kotoba-lang/godaddy-dns) talks to
a *registrar's* API — neither one actually **answers DNS queries on the
wire**. `nameserver` is the missing data-plane piece: it consumes
`zone.model` zones directly and serves them over real sockets.

## What this is (and isn't)

**Real TLD hosting (.com, .net, …)**: yes, for the part that's actually
yours to run — get a domain (or subdomain) NS-delegated to this
nameserver's public IP via your registrar (see `nameserver.delegate` +
`godaddy-dns`'s `IDns`, below), and this server becomes authoritative for it
from the internet's point of view. Nobody can make you the root authority
for `.com` itself (ICANN owns that), but you don't need to be — NS
delegation is exactly how every real authoritative nameserver, including
the big managed-DNS providers, actually works.

**Custom TLD hosting (.hogehoge, …)**: this is deliberately framed as an
**alt-root**, not a claim of global resolvability — nobody can grant that
for a made-up TLD (see Handshake / ENS-via-gateway / OpenNIC for the same
reality). What you get: point a stub resolver, browser extension, or this
nameserver's own clients at this server, and any syntactically valid
kotoba-lang IPNS key-derived name resolves under your chosen custom suffix
— no registrar, no owner hand-off, because holding the Ed25519 private key
already *is* authority over that name (see `ipns.core`'s docstring).

## Modules

| ns | portability | role |
|---|---|---|
| `nameserver.names` | `.cljc` | domain-name label helpers (split/join/parent/wildcard) |
| `nameserver.wire` | `.cljc` | RFC 1035 §4 message codec: EDN ⇄ wire bytes, with name compression on encode and decompression (loop-guarded against malicious pointers) on decode |
| `nameserver.store` | `.cljc` | in-memory authoritative zone store over `zone.model` zones: exact match, wildcard, CNAME chase, NXDOMAIN/NODATA |
| `nameserver.resolver` | `.cljc` | `IResolver` protocol + `chain-resolver` (first non-`:refused` wins) |
| `nameserver.custom-tld` | `.cljc` | the `.hogehoge`-style alt-root ⇄ IPNS/dnslink bridge |
| `nameserver.delegate` | `.cljc` | pure data: NS + glue-A record edit-set for delegating a subdomain via `godaddy-dns`'s `IDns` |
| `nameserver.domain-verification` | `.cljc` | portable DNS TXT ownership challenge and DNS-over-HTTPS JSON verdict |
| `nameserver.edns` | `.cljc` | EDNS(0) (RFC 6891): OPT pseudo-RR, payload negotiation, DO bit, extended RCODE, measured truncation |
| `nameserver.transfer` | `.cljc` | AXFR (RFC 5936) / IXFR (RFC 1995) with RFC 1982 serial arithmetic and a **required** ACL |
| `nameserver.server` | **`.clj` only** | the UDP/TCP socket listener |

## Why `.clj` (not `.cljc`) for the socket layer

Per this monorepo's kotoba-wasm → clojurewasm → ClojureScript → nbb → JVM
runtime priority, JVM is the deliberate last resort here, not a default:
raw UDP/TCP socket binding has no portable equivalent on this stack's other
runtimes — kotoba wasm's `actor:host` ABI has no raw-socket capability in
its closed host-import table, and browsers can't bind UDP:53 either. Every
other namespace (wire codec, zone store, resolver chain, custom-TLD bridge)
is zero-third-party-dep `.cljc` and runs anywhere; only the listener itself
is JVM.

## Quick start

```clojure
(require '[zone.zone :as zone]
         '[nameserver.resolver :as resolver]
         '[nameserver.custom-tld :as ctld]
         '[nameserver.server :as server])

(def zone-resolver
  (resolver/zone-store-resolver
    {"example.test." (zone/parse-str (slurp "example.test.zone"))}))

(def alt-root (ctld/custom-tld-resolver #{"hogehoge."} "ipns.dweb.link"))

(def srv (server/start-server!
           {:resolver (resolver/chain-resolver [zone-resolver alt-root])
            :port 1053 :host "127.0.0.1"}))   ; use 53 + root for real deployment

;; dig @127.0.0.1 -p 1053 example.test A
;; dig @127.0.0.1 -p 1053 TXT <ipns-name>.hogehoge

(server/stop-server! srv)
```

Runnable example: `kbb -M:dev:examples -m run-server` (see
`examples/run_server.cljk`).

## Delegating a real subdomain

```clojure
(require '[nameserver.delegate :as delegate]
         '[godaddydns.godaddy :as godaddy]
         '[godaddydns.dns :as dns])

(def records
  (delegate/delegation-records
    {:domain "example.com" :subdomain "ns"
     :ns-hosts ["ns1" "ns2"]
     :glue {"ns1" "203.0.113.10" "ns2" "203.0.113.11"}}))

;; push via godaddy-dns-clj's IDns (dry-run by default per its own ADR-0001)
(doseq [r (:glue-records records)]
  (dns/-upsert-records! godaddy-conn "example.com" (:type r) (:name r) [r]))
```

Changing an entire registered domain's *apex* nameservers (the registrar
account's "use these nameservers for the whole domain" setting) is a
different registrar-account operation that `godaddy-dns`'s `IDns` doesn't
implement — out of scope here too; `nameserver.delegate` covers subdomain
delegation through the generic records API.

## Running for real

The quick-start/`run_server.clj` path above is for trying it out. To run a
persistent process:

```
kbb -M -m nameserver.main [config.edn]   # defaults to $NAMESERVER_CONFIG, then ./config.edn
```

`config.edn` (see `examples/config.edn`):

```clojure
{:host "0.0.0.0" :port 53                     ; 53 needs root/CAP_NET_BIND_SERVICE, see below
 :zones-dir "/etc/org-ietf-dns/zones"          ; every *.zone file in the dir; $ORIGIN in the
                                                ; file text is the key, filename doesn't matter
 :custom-tld {:suffixes ["hogehoge."]          ; optional
              :gateway-host "ipns.dweb.link"}} ; optional
```

`nameserver.main` loads every zone file, wires up `chain-resolver`
(hosted zones first, custom-TLD alt-root as fallback if configured), boots
`nameserver.server`, and installs a JVM shutdown hook so `SIGTERM`/`SIGINT`
close the sockets cleanly (`systemctl stop` / `docker stop` / Ctrl-C all work).

**Binding port 53 without running as root** — three options, pick one:
1. `sudo setcap 'cap_net_bind_service=+ep' "$(readlink -f "$(which java)")"` once,
   then run the JVM as a normal user.
2. `AmbientCapabilities=CAP_NET_BIND_SERVICE` in the systemd unit (see
   `deploy/org-ietf-dns.service` — grants the capability only to this
   service, no `setcap` on the shared `java` binary).
3. Run in Docker (`docker run -p 53:53/udp -p 53:53/tcp ...`) — the
   container's own root can bind 53 internally regardless of host user; see
   `Dockerfile`. *(Follows this org's established pattern of running
   Clojure services from source via the Clojure CLI, no uberjar step —
   same shape as `ai-gftd-syosetsuka`'s Dockerfile. Not build-verified in
   this session — no Docker daemon available in the environment it was
   written in; verify with `docker build .` before relying on it.)*

**Getting real internet traffic to it**: NS delegation, not code — see
"Delegating a real subdomain" above. Nothing resolves *to* this server
until some parent zone's NS records point at its public IP.

**Using the custom-TLD bridge from a real client**: `.hogehoge` isn't in
anyone's default resolution path, so a client has to be told to ask *this*
server for it specifically (same reality section above already covers —
this is the client-side half of that). Two practical ways, least to most
invasive:
- **One-off / testing**: `dig @<this-server-ip> <name>.hogehoge TXT` directly
  — no client config at all, just point the query at the IP.
- **Split-horizon for a whole machine**: forward only the custom suffix to
  this server while everything else still goes to normal DNS, instead of
  replacing `/etc/resolv.conf` wholesale (which would break all other DNS).
  With `systemd-resolved`:
  ```
  # /etc/systemd/resolved.conf.d/hogehoge.conf
  [Resolve]
  DNS=<this-server-ip>
  Domains=~hogehoge
  ```
  (the `~` makes it a routing-only domain, not the default search domain)
  then `systemctl restart systemd-resolved`. With `dnsmasq`:
  `server=/hogehoge/<this-server-ip>` in `dnsmasq.conf`.

## Scope (documented, not silently missing)

- ASCII labels only (IDN's punycode ASCII-safe encoding covers real-world
  non-ASCII names, so this isn't a practical restriction in practice).
- TXT/CAA values ≤ 255 octets (single wire character-string; no multi-string
  TXT splitting).
- EDNS0 (RFC 6891) is implemented in `nameserver.edns`, as an interpretation
  layer over `wire` rather than inside it: OPT overloads CLASS to mean the
  sender's payload size and TTL to mean version/DO/extended-RCODE, and teaching
  the byte codec about that would put protocol semantics in a byte layer. Not
  wired into `nameserver.server` by default — a server embedding it picks its
  own payload ceiling. Without EDNS0 the body stays capped at 512 octets with
  the TC bit and a TCP retry (RFC 1035 §4.2.1 — implemented).
- Zone transfer (AXFR/IXFR) is implemented in `nameserver.transfer` and is
  **pure**: it produces the record sequence, and the caller owns the socket.
  The access predicate is a required argument with no default, because every
  default is wrong — permissive leaks the whole zone, restrictive silently
  breaks replication an operator thought they had configured.
- No DNSSEC (see [`org-ietf-dnssec`](https://github.com/kotoba-lang/org-ietf-dnssec)),
  no delegation-boundary NS referrals (if you host both a parent and child
  zone, records simply live in whichever zone map has them).
- No rate limiting/connection throttling beyond the wire-layer
  compression-pointer-loop guard — a public-facing deployment should sit
  behind its own DoS protection.

## Test

```
kbb -M:dev:test
```

51 tests / 150 assertions, including genuine socket-level tests (a real
`DatagramSocket` on `127.0.0.1` talking wire bytes to a server booted by
`nameserver.server`) and a `dig`-verified manual smoke test via
`examples/run_server.cljk`.
