# tech-ipfs-specs-http-gateway

[![CI](https://github.com/kotoba-lang/tech-ipfs-specs-http-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/tech-ipfs-specs-http-gateway/actions/workflows/ci.yml)

**IPFS HTTP Gateway** (specs.ipfs.tech/http-gateways) as a pure `.cljc` library:
request parsing (path *and* subdomain forms), the caching policy, and the
resolution router that decides **which naming plane owns a name**.

Zero dependencies. The DHT client, the DNS resolver, the registry and the cache
are all injected, so the whole policy is testable without any of them.

## Why a gateway is fast

Not because it is near the user. Because **content addressing gives it the
strongest cache key that exists**, and the one part that does change says
exactly how long it is good for.

| | cacheable for | why |
|---|---|---|
| `/ipfs/{cid}` | a year, `immutable` | the identifier is a hash of the bytes; revalidation is pure waste |
| `/ipns/{name}` | the record's own **TTL** | the publisher stated how stale an answer may be |

The slow part is **resolution**, and it is exactly what the cache removes. This
workspace's own kotobase.net measures it: `kotobase-cf-wasm.head` documents that
every read pays a head lookup *it cannot cache*, p50 **176 ms**, calling it "the
serving floor". Caching the resolution for the record's TTL removes that floor
for every request after the first — a larger win than anything done to the
content path.

`stale-while-revalidate` matters more here than usual: when a TTL expires the
gateway must do a DHT round trip. Serving the slightly-stale answer immediately
and refreshing behind it makes the expiry invisible; without it, one unlucky
request per name per TTL pays full cost.

## Planes are chosen by the *name*, not ordered by preference

`gateway.resolve` routes a name to exactly one plane:

| name | plane |
|---|---|
| `k51…` / `bafz…` | `:dht` — authority is the Ed25519 key the name is derived from |
| `example.com` | `:dnslink` |
| anything else | `:registry` — e.g. kotobase.net's graph names |

**A DHT miss for a key-derived name is a miss, and the answer is 404.** Writing
this as "try the DHT, fall back to the local registry" would be a security bug
wearing the clothes of a reliability feature: a `k51…` name the DHT could not
answer would fall through to a plane that can assert any value it likes, for a
name whose authority is supposed to be a private key nobody else holds.

That is also what makes this a **migration rather than a cutover** — the
registry keeps answering for the names it actually owns, so nothing that
resolves today stops resolving, and nothing that should be key-authoritative
becomes registry-authoritative.

## Details that fail silently

**Immutability is a property of the namespace**, derived by
`request/immutable?`. Reading an `:immutable?` key off a parsed request looks
right and is always `nil` — silently giving every `/ipfs/` response the short
mutable max-age and throwing away the entire reason the gateway is fast. There
is a test; it caught exactly that bug during development.

**IPNS TTLs are nanoseconds.** Reading the number as seconds gives a cache
lifetime a billion times too long — a gateway that appears never to update.

**A CIDv0 cannot be a DNS label.** DNS is case-insensitive; `Qm…` is not. In a
*path* it is fine; as a subdomain, DNS has already lower-cased it and there is
nothing to recover, so this reports 400 rather than resolving something else. A
gateway that skips the redirect appears to work until a proxy normalizes case.

**The subdomain form exists for origin isolation**, not convenience. Two CIDs on
one host share a browser origin, so one page's script can read the other's
storage. A gateway serving only the path form cannot safely host untrusted
content.

**A deserialized response takes a weak Etag.** The same CID can render
differently across gateway versions (directory listings, `index.html`
selection). A strong etag tells caches two byte-different responses are
identical.

**A repeated `?format=` keeps the first value.** Last-wins lets an appended
parameter change what the gateway returns.

**A resolution with a lower sequence is rejected.** A stale-but-validly-signed
record would otherwise walk the name backwards for a whole TTL — the failure
that makes a gateway look like it is losing updates.

**A failed resolution still serves a recent answer.** Inside the window the
`Cache-Control` header already promised, the publisher's last statement beats a
502. Past it, an error — not an ancient answer.

## Usage

```clojure
(require '[gateway.request :as req] '[gateway.resolve :as res])

(def r (req/parse {:host "bafy….ipfs.gw.example" :path "/index.html"}))
;; => {:kind :content :namespace "ipfs" :id "bafy…" :path "index.html" :style :subdomain}

(res/lookup {:planes {:dht      resolve-via-kad-routing
                      :registry resolve-via-kotobase-head}
             :cache-get  #(.get cache %)
             :cache-put! #(.put cache %1 %2)
             :now-ms (now)}
            r)
;; => {:status :hit|:miss|:refreshed|:stale|:error :cid … :plane … :ttl-ns …}

(res/response-for r outcome)
;; => {"Cache-Control" "public, max-age=600, stale-while-revalidate=600"
;;     "Etag" "W/\"bafy…\"" "X-Ipfs-Path" "/ipns/k51…" "Accept-Ranges" "bytes"}
```

The `:dht` plane is wired to [`io-libp2p-specs-kad-dht`](https://github.com/kotoba-lang/io-libp2p-specs-kad-dht)'s
`kad.routing/resolve` with [`ipns.record`](https://github.com/kotoba-lang/tech-ipfs-specs-ipns)
validation.

## Scope

- **In:** request parsing, format negotiation, the caching policy and its
  freshness/staleness/regression rules, response headers, plane routing, cached
  resolution.
- **Not here:** block fetching, UnixFS traversal, directory listings, CAR
  streaming, Range slicing. Those need a blockstore, and this library
  deliberately has none — it decides *what to serve and for how long*, not how
  to get the bytes.
- **Not yet:** DNSLink TXT lookup (the `:dnslink` plane is routed to but not
  implemented — `org-ietf-dns` has the DoH client it needs), `_redirects`
  support, and `If-None-Match` handling.

## Test

```
kbb -M:test
```

25 tests / 81 assertions.
