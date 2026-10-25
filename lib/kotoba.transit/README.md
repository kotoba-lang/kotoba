# kotoba-lang/transit

Plain JSON envelope helpers for Kotoba's internal app/resource wire protocol.

Kotoba's data model is EDN/Datomic: keywords, symbols, sets, and immutable
datoms are semantic values, not plain JSON strings. This library defines the
shared CLJC envelope layer used by Kotoba browser, JVM, bb, and server-side
tooling. It intentionally has no Rust dependency and no bespoke wire tag
scheme — the wire shape is web-standard JSON, transported over ordinary HTTP
(and, where already adopted at the transport layer, HTTP/2, HTTP/3/QUIC, or
WebTransport; see `kotoba-lang/net`, `kotoba-lang/murakumo`, `kotoba-lang/rt`).

Plain JSON (optionally gzip-compressed) is the default wire projection for
Kotoba-owned APIs. EDN remains the in-memory and file authoring shape; CID,
signed manifests, and lockfiles remain the package/storage integrity
boundary. This is a deliberately lossy projection: keywords/symbols become
bare strings and sets/lists become JSON arrays, with no reader tags to
recover exact EDN type identity. See `ADR-kotoba-json-wire-protocol.md`
(supersedes `ADR-kotoba-transit-wire-protocol.md`) in `kotoba-lang/kotoba-lang`.

## Non-goals

- No Transit tag scheme, no `application/transit+json` media type.
- No host-specific object model in the envelope layer.
- No independent SPARQL/Cypher/GraphQL persistence semantics.

Hosts may provide byte encoders, HTTP clients, gzip compression, or storage
adapters, but the shape of Kotoba's JSON envelopes is defined here in CLJC.

## Tiering

Tier 1:

- Kotoba app/resource envelopes
- Datomic API: transact, q, pull, datoms, entity, history, tx, sync
- EDN/Datomic semantics
- JSON HTTP media type: `application/json`

Tier 2:

- SPARQL
- Cypher
- GraphQL

Tier-2 query languages compile to or project from the tier-1 Datomic graph.
They are interoperability surfaces, not independent sources of truth.

## Usage

```clojure
(require '[transit.core :as transit])

(transit/write-json {:db/id 1 :user/name "Ada"})
;; => {"db/id" 1, "user/name" "Ada"} as a plain JSON-compatible value

(transit/datomic-envelope {:graph "people"
                           :query-edn "[:find ?e :where [?e :user/name \"Ada\"]]"})
;; => {:content-type "application/json"
;;     :accept "application/json"
;;     :body {"graph" "people", "query_edn" "..."}}

;; opt into gzip once the body crosses transit.core/default-gzip-threshold-bytes
(transit/datomic-envelope {:graph "people"} {:gzip? true})
;; => adds :content-encoding "gzip" — the host still does the actual compression
```

## Design

This repo intentionally stays a small CLJC surface:

- `write-json`: EDN values to plain JSON-compatible values (no tags).
- `datomic-envelope`: standard HTTP envelope metadata for Kotoba Datomic APIs.
- `office-envelope` / `read-office-envelope-body`: standard JSON envelope for
  Slides, Sheets, Docs, and related app resources. The handful of
  keyword-typed discriminant fields (protocol family, resource kind,
  operation kind) are recovered explicitly on read; the payload itself
  round-trips as plain JSON data, not the original EDN shape.

## Host boundary

`transit.core/write-json` returns plain JSON-compatible data. A host is
responsible only for turning that data into bytes, gzip-compressing it when
`:content-encoding "gzip"` is present, and adding HTTP headers:

```clojure
{:content-type transit.core/media-type-json
 :accept transit.core/media-type-json
 :body (transit.core/write-json value)}
```

Rust, JavaScript, JVM, or future Kotoba-native hosts can all perform that byte
encoding, but they should not invent new tag schemes, envelope keys, tiering,
or Datomic semantics.

## Test

```bash
kbb -M:test
```
