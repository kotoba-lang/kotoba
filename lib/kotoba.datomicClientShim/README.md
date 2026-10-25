# datomic-client-shim

**This is SHAPE-compatible with the [Datomic Client API](https://docs.datomic.com/client-api/datomic.client.api.html)'s
published namespace and request/response shapes — it is explicitly NOT
wire-compatible with proprietary Datomic, and it is not affiliated with or
endorsed by Datomic/Nubank/Cognitect.** There is no single open Datomic wire
protocol to conform to (the Client API is HTTP+transit but not an
independently-specified standard; the Peer/transactor protocol is
proprietary/undocumented) — so this repo does not, and could not honestly,
claim wire conformance. **A stock `com.datomic/client-cloud` binary cannot
point at this server.** This is why the repo is named plainly (`datomic-client-shim`,
no `org-<body>-<spec>` reverse-domain prefix) rather than claiming spec
conformance the way `kotoba-lang/org-ietf-webdav` or
`kotoba-lang/org-oci-distribution` do — see ADR-2607172300 in
`com-junkawasaki/root`, which follows the same don't-overclaim discipline
ADR-2607060100 used to exclude `json`/`dag-cbor`/`openapi` from
reverse-domain naming.

## Client library

`datomic.client.api` now exports the same 24 public var names as Datomic Client
1.0.146, backed by `kotoba-lang/kotobase-engine`:

```clojure
(require '[datomic.client.api :as d])

(def client (d/client {:server-type :kotobase
                       :endpoint "https://datomic.kotobase.net"
                       :token #(System/getenv "KOTOBASE_TOKEN")}))
(def conn (d/connect client {:db-name "production"}))
(def db (d/as-of (d/db conn) 42))
(d/q '[:find ?e :where [?e :person/name _]] db)
```

The shim covers lifecycle, immutable database values, as-of/since/history,
q/qseq, pull, datoms/seek/rseek/index-range/index-pull, db-stats, tx-range,
sync, transact and speculative with/with-db. JVM remote calls use the standard
HTTP client; embedded/test hosts may inject `:request-fn`.

Both local and hosted engines execute speculative `with`; the hosted db-after
is an immutable portable token carrying its speculative transaction and does
not advance the durable graph head. `administer-system` implements the public
`:upgrade-schema` action and reports Kotobase's intrinsic base schema as
current. Namespace parity is not a claim of Cognitect's proprietary wire or of
the embedded Peer API.

Do not put this shim and Cognitect's `com.datomic/client` on the same
classpath: both intentionally provide `datomic.client.api`.

## Legacy embedded query handler

An HTTP+edn query surface over [`kotobase`](https://github.com/kotoba-lang/kotobase),
built on [`kotoba-lang/kotobase-query`](https://github.com/kotoba-lang/kotobase-query)
(the shared bridge that materializes `kotobase.store/IStore` collections
into an [`arrangement`](https://github.com/kotoba-lang/arrangement)
in-memory db and runs real `:find`/`:where` Datalog over it, joins across
collections included). This repo is the HTTP handler on top of that bridge
— it does not reimplement query evaluation, materialization, or indexing.

The handler is a **pure cljc function** over an injected
`kotobase.store/IStore`, same seam every `kotobase.protocols.*` handler
uses (`kotobase-protocols`'s `s3`/`ipfs`/`atproto`/`git`, and the sibling
per-protocol repos `org-ietf-webdav`/`org-oci-distribution`/
`org-ietf-sftp`). No I/O, no transport, no authentication live here —
a deploy shell (Cloudflare Worker, browser worker, fleet peer) owns those,
same discipline as every other surface in this family.

## Endpoint

```
POST /api/query
  body:   edn {:query <datalog-query> :args [...]}
  200:    edn #{[...] ...}           (the result-set tuples)
  400:    edn {:error "..."}         (parse error / malformed body / no collections)
  404/405 text                       (unknown path / wrong method — generic HTTP miss)
```

This is the only endpoint. There is **no transact/connect/db endpoint** —
this surface is read-only (query only), matching ADR-2607172300's scope for
all four new query-language surfaces.

### `:args` — the one place the shape genuinely diverges from real Datomic

Real Datomic's `:args` vector conventionally starts with a `db` value, then
one positional value per `:in` binding after `db`. This surface has **no
`db` value on the wire** — the deploy-side `ctx` already fixes which
`kotobase.store` collections are materialized (`:coll-keys`) and how
visibility is decided (`:visible?`) for every request it serves. So here
`:args` is threaded directly as `kotobase.query.bridge/q`'s `inputs` —
positional values for whatever the query's `:in` clause declares, **no db
slot**. Omit `:args` (or send `[]`) for a query with no `:in` clause.

## `ctx` (extends the shared `kotobase.protocols.*` `{:store IStore}` shape)

```clojure
{:store     IStore    ; required — kotobase.query.bridge/materialize reads from this
 :coll-keys [...]     ; required (default) — collections a request materializes
                       ;   if it doesn't send its own :coll-keys in the body
 :visible?  (fn [datom] ...) ; REQUIRED, NOT DEFAULTED — see below
 :now       "..."}    ; optional, carried into the audit event only
```

### `:visible?` is required, never defaulted — read this before deploying

Every query fn in `kotobase.query.bridge` takes an explicit `visible?`
predicate with no permissive default (ADR-2607050500, "query as
first-class effect" — the same discipline `arrangement.datalog` and the
retired `kqe` already enforce). This handler adds one more layer on top: if
`ctx` has **no** `:visible?` at all, `handle` throws immediately rather
than silently falling back to "see everything".

**v0.1 honesty note**: a real multi-tenant deploy MUST supply a real
authorization-derived `:visible?` (a per-datom tenant/ACL check). This repo
ships **no such policy**. The only predicate defined here,
`kotobase.protocols.datomic/always-visible?` (`(constantly true)`), is
appropriate **only** for a single-tenant/trusted deploy where every
materialized collection is meant to be fully readable by every caller of
this endpoint. It exists as an explicit, named, opt-**in** choice a deploy
shell reaches for — never a hidden default this handler falls back to on
its own.

## Audit

This is a read-only surface — there is nothing to audit in the
`kotobase.protocols.s3`/`.atproto` PUT/DELETE sense. Instead, **every
successful query is audited**, one event per request, appended to the same
`:kotobase.protocols/audit` collection those write surfaces use:

```clojure
{:surface :datomic :op :query :coll-keys [...] :query <the query form>
 :args-count n :result-count n}
```

Failed requests (parse error, missing `:query`, wrong method/path) are
**not** audited — they never reached `kotobase.query.bridge`.

## Example

```clojure
(require '[kotobase.local :as local]
         '[kotobase.store :as st]
         '[kotobase.protocols.datomic :as datomic])

(def store (local/local-store))
(st/-put store "users" "u1" {:name "Alice" :role "admin" :dept-key "d1"})
(st/-put store "departments" "d1" {:name "Engineering"})

(def ctx {:store store
          :coll-keys ["users" "departments"]
          :visible? datomic/always-visible?}) ; explicit opt-in, single-tenant

(datomic/handle ctx
  {:method :post :path "/api/query"
   :body (pr-str '{:query {:find [?uname ?dname]
                            :where [[?u :name ?uname]
                                    [?u :dept-key ?dk]
                                    [?d :kotobase/coll "departments"]
                                    [?d :kotobase/key ?dk]
                                    [?d :name ?dname]]}})})
;; => {:status 200
;;     :headers {"content-type" "application/edn"}
;;     :body "#{[\"Alice\" \"Engineering\"]}"}
```

## `kotobase.protocols.http` is vendored, not depended on

`src/kotobase/protocols/http.cljc` (ring-shaped request/response plumbing)
is vendored byte-for-byte from `kotoba-lang/kotobase-protocols`, same
discipline `org-ietf-webdav`/`org-oci-distribution`/`org-ietf-sftp` use
(ADR-2607172210, continued by ADR-2607172300) — this repo has **no runtime
dependency on `kotobase-protocols`**, only on `kotobase` (the `IStore`
seam) and `kotobase-query` (the materialize+query bridge). Update it by
re-vendoring from upstream, not by independent edits.

**Namespace stays `kotobase.protocols.datomic`** even though this library
lives in its own repo (not inside `kotobase-protocols`) — kept consistent
with the family for a possible future re-homing, same rationale
`org-ietf-webdav`'s README documents for `kotobase.protocols.webdav`.

## Legacy-handler scope guards

- **Query only, no writes.** No transact/connect endpoint, no schema
  mutation. If a write surface over this data is ever needed, that is a
  different, separately-decided repo — not a silent extension of this one.
- **v0.1 linear materialization** (inherited from `kotobase-query`): every
  request does a full `-list`+`-get` scan of every materialized collection,
  no caching, no incremental indexing. Fine for small/test-scale query
  volume; a documented, accepted limitation, not an oversight. See
  `kotobase-query`'s own README for the full explanation.
- **The legacy `/api/query` handler has no transact/db/history/pull endpoints.**
  Those operations live in the `datomic.client.api` client and the canonical
  `https://datomic.kotobase.net/api/*` gateway; they are not duplicated in the
  embedded document-store handler.
- **`:args` semantics diverge from real Datomic** — see the dedicated
  section above. This is the single most important thing to get right if
  you are porting client code that expects real Datomic `:args` shape.
- **No authentication, no transport** — the deploy shell owns both, exactly
  as CACAO verification lives in the kotobase.net Worker, not in the
  engine.

## Develop / test

First-class runtime is **nbb/cljs** (repo-wide runtime priority: `kotoba
wasm` > `clojurewasm` > ClojureScript > nbb > (jvm/bb)):

```bash
git clone https://github.com/kotoba-lang/kotobase .deps/kotobase
git clone https://github.com/kotoba-lang/kotobase-query .deps/kotobase-query
git clone https://github.com/kotoba-lang/arrangement .deps/arrangement
git clone https://github.com/kotoba-lang/prolly-tree .deps/prolly-tree
git clone https://github.com/kotoba-lang/io-ipld .deps/io-ipld
git clone https://github.com/kotoba-lang/io-multiformats .deps/io-multiformats
git clone https://github.com/kotoba-lang/org-ietf-cbor .deps/org-ietf-cbor
npm install
kbb --backend sci --classpath "src:test:.deps/kotobase/src:.deps/kotobase-query/src:.deps/arrangement/src:.deps/prolly-tree/src:.deps/io-ipld/src:.deps/io-multiformats/src:.deps/org-ietf-cbor/src" bin/run_tests.cljk
```

Each `.deps/<name>` should be checked out at the SHA pinned in `deps.edn`
(`kotobase`, `kotobase-query`) or transitively in `kotobase-query`'s own
`deps.edn` (`arrangement`) / `arrangement`'s own `deps.edn`
(`prolly-tree`, `io-ipld`, `io-multiformats`, `org-ietf-cbor`) — CI pins
every one of them, see `.github/workflows/ci.yml`.

The `:test` alias in `deps.edn` is the JVM **compat** suite only (`clojure
-M:test`, via `tools.deps` transitive git-dep resolution — no manual
`.deps/` cloning needed for this path) — not the primary execution path.

## License

Apache-2.0
