# zone-clj (DNS ゾーンファイル)

[![CI](https://github.com/kotoba-lang/zone/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/zone/actions/workflows/ci.yml)

Handle **DNS zone files (RFC 1035) as EDN/Clojure data** in portable Clojure —
every namespace is `.cljc`, with **zero third-party runtime deps**, so it runs on
the JVM, ClojureScript, and Clojure-on-WASM hosts (SCI).  A zone is plain data
you can `assoc`, `diff`, store in Datomic, or generate; the library adds the
record queries, structural validation, zone-file I/O, and a structural diff
purpose-built for DNS sync (feeds directly into
[godaddy-dns-clj](https://github.com/com-junkawasaki/godaddy-dns-clj)).

Sibling of the other reusable `*-clj` kernels in this org
([bpmn-clj](https://github.com/com-junkawasaki/bpmn-clj),
[dmn-clj](https://github.com/com-junkawasaki/dmn-clj)).

## Why a shared library (org placement)

Per the three-org rule, the **reusable** zone model lives in **com-junkawasaki**;
**public-benefit actor instances** that drive DNS management for community
infrastructure live in **etzhayyim**; any **business/private deployment** lives in
**gftdcojp**.  zone-clj is the dep — it carries no domain credentials and no
registrar bindings (those are host-injected ports via godaddy-dns-clj or similar).

## The model: zone as EDN (`zone.model`)

A zone is a flat map with namespaced `:zone/*` keys; records are a vector (ordered
by parse/emit order, not document significance):

```clojure
{:zone/origin  "example.com."
 :zone/ttl     3600
 :zone/records [{:zone/name  "@"
                 :zone/ttl   3600
                 :zone/class "IN"
                 :zone/type  "SOA"
                 :zone/rdata {:zone/mname   "ns1.example.com."
                              :zone/rname   "hostmaster.example.com."
                              :zone/serial  2024010101
                              :zone/refresh 3600
                              :zone/retry   900
                              :zone/expire  604800
                              :zone/minimum 86400}}
                {:zone/name "@" :zone/ttl 3600 :zone/class "IN"
                 :zone/type "A" :zone/rdata {:zone/address "93.184.216.34"}}
                {:zone/name "@" :zone/ttl 3600 :zone/class "IN"
                 :zone/type "MX" :zone/rdata {:zone/pref 10
                                              :zone/exchange "mail.example.com."}}
                ...]}
```

rdata shapes per record type:

| type | rdata keys |
|---|---|
| `A` / `AAAA` | `:zone/address` |
| `CNAME` / `NS` / `PTR` | `:zone/target` |
| `MX` | `:zone/pref` `:zone/exchange` |
| `TXT` | `:zone/text` |
| `SOA` | `:zone/mname` `:zone/rname` `:zone/serial` `:zone/refresh` `:zone/retry` `:zone/expire` `:zone/minimum` |
| `SRV` | `:zone/pri` `:zone/weight` `:zone/port` `:zone/target` |
| `CAA` | `:zone/flags` `:zone/tag` `:zone/value` |

Queries:

```clojure
(require '[zone.model :as m])

(m/records-of-type zone "MX")   ;=> all MX records
(m/by-name zone "@")            ;=> all apex records
```

## Validation (`zone.validate`)

`problems` returns a vector of `{:zone/severity :error|:warn :zone/code .. :zone/id .. :zone/msg ..}`;
`valid?` is true iff there are no `:error`s (warnings are advisory):

```clojure
(require '[zone.validate :as v])
(v/valid? zone)             ;=> true
(v/problems broken)         ;=> [{:zone/severity :error :zone/code :zone/no-soa …}]
```

Errors: no SOA record; more than one SOA; CNAME exclusivity violation (a name has
both a CNAME and other records); incomplete MX/SRV/SOA rdata.  Warnings: an
FQDN-looking rdata value (`:zone/target`, `:zone/exchange`, `:zone/mname`,
`:zone/rname`) that lacks a trailing dot.

## Zone I/O (`zone.zone`)

```clojure
(require '[zone.zone :as z])
(z/parse-str (slurp "example.com.zone"))   ; zone file text → EDN model
(z/emit-str zone)                          ; EDN model → canonical zone text (round-trips)
```

Zero-dep and portable: a **minimal reader/emitter** covers the well-formed RFC 1035
subset — `$ORIGIN`, `$TTL`, `@` apex, blank-owner inheritance, flexible
`[ttl] [class]` ordering before the type, `;` comments (protected inside quoted
strings), and SOA multi-line `( … )` parentheses collapsed to a single logical
line.  `emit-str` sorts records by `[name type]` for deterministic output.

## Diff (`zone.model/diff`)

```clojure
(require '[zone.model :as m])

(m/diff old-zone new-zone)
;=> {:zone/added   [{:zone/name "blog" :zone/type "A" …}]
;    :zone/removed []
;    :zone/changed [{:zone/from {:zone/name "@" :zone/type "A"
;                                :zone/rdata {:zone/address "1.2.3.4"} …}
;                   :zone/to   {:zone/name "@" :zone/type "A"
;                               :zone/rdata {:zone/address "5.6.7.8"} …}}]}
```

Identity key is `[name type rdata]`.  A single-record `[name type]` group whose
rdata changes is reported as `:zone/changed` rather than add+remove — this matches
the godaddy-dns-clj API sync model where a PATCH is cheaper than DELETE+CREATE.

## Test

```
kbb -X:test
```
