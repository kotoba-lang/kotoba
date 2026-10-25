(ns langchain.kotoba-db
  "Kotoba-server XRPC backend implementing the langchain.db/api contract.

  Instead of an in-process EAV store, every operation is a POST to a
  running kotoba-server pod via the datomic.* XRPC namespace:

    ai.gftd.apps.kotobase.datomic.transact  → :transact!
    ai.gftd.apps.kotobase.datomic.q         → :q
    ai.gftd.apps.kotobase.datomic.pull      → :pull
    ai.gftd.apps.kotobase.datomic.entid     → :entid

  Pass the kotoba-api map as :db-api to datomic-checkpointer,
  langchain.memory/datomic-chat-history, etc.:

    (require '[langchain.kotoba-db    :as kdb]
             '[langgraph.checkpoint   :as cp])

    (def conn (kdb/kotoba-conn \"http://pod:8080\" \"k51...\"))
    (def api  (kdb/kotoba-api  jvm-host-caps))
    (def cp   (cp/datomic-checkpointer conn {:db-api api}))

  I/O is fully injected (ADR-0001) — host-caps shape matches langchain.model:
    {:http-fn   (fn [{:keys [url method headers body]}] => {:status n :body s})
     :json-write (fn [clj-data] => json-string)
     :json-read  (fn [json-string] => clj-data with keyword keys)}"
  (:require #?(:clj  [kotoba.lang.edn :as edn]
               :cljs [cljs.reader :as edn])
            [kotoba.lang.text :as str]))

;; ─── connection map ───────────────────────────────────────────────────────────

(def KG-GRAPH-CID
  "Multibase CID of the kotobase-kg-v1 named graph (sha256 of b\"kotobase-kg-v1\").
  Pass as :graph to kotoba-conn when reading kg.ingest data via datomic.q."
  "bafyreiglzym7s24os6nki3aknbg2d6dncy5dadwjftavcnuarkdswz6afa")

(defn kotoba-conn
  "Creates a kotoba connection map (not an atom — state lives on the server).

   url   – kotoba-server base URL, e.g. \"http://149.28.207.62:8080\"
   graph – IPNS name or CID multibase of the target named graph. Still sent
           as the wire `graph` param — required for reading a pre-established,
           non-tenant-scoped graph (e.g. `KG-GRAPH-CID`), and kept for
           backward compat with every existing caller of this fn.
   opts  – :token   Bearer JWT
           :cacao   base64-CBOR CACAO string (for CACAO-gated endpoints)
           :did     DID string (required with :cacao; sent as x-kotoba-did)
           :db-name tenant database name. When present, `kotoba-api`'s
                    `:transact!` sends `db_name` (not `graph`) on the wire —
                    the edge derives + verifies the target graph
                    server-side as `kotobase/db/<your-did>/<db-name>` from
                    the CACAO alone, which the live edge now REQUIRES for a
                    tenant Datom write (`db_name required for a tenant
                    Datom write` — a plain `:graph` param is rejected on
                    `datomic.transact`).
           :graph   precomputed graph CID (e.g. `kotoba.cid/canonical-graph`
                    or `tsumugu.cacao/canonical-graph` for `<did>/<db-name>`).
                    `kotoba-api`'s `:q`/`:pull`/`:entid` need THIS (not
                    `db_name`) — empirically, the live edge's read ops don't
                    derive the tenant graph from `db_name`+CACAO the way
                    `transact` does; a `db_name`-only read silently matches
                    nothing (200 OK, empty rows) rather than erroring. Pass
                    both `:db-name` (for writes) and `:graph` (for reads) for
                    a fully-functional tenant `conn` — see `kotoba-conn*`."
  ([url graph] (kotoba-conn url graph {}))
  ([url graph {:keys [token cacao did db-name]}]
   (cond-> {:kotoba/url url :kotoba/graph graph}
     token   (assoc :kotoba/token token)
     cacao   (assoc :kotoba/cacao cacao :kotoba/did did)
     db-name (assoc :kotoba/db-name db-name))))

(defn kotoba-conn*
  "Like `kotoba-conn`, but for a tenant database addressed by `db-name`
  instead of a precomputed `graph` — the wire shape the live edge's tenant
  Datom *write* op requires today. Pass `:graph` in `opts` too (the
  precomputed CID for `<did>/<db-name>`) so `:q`/`:pull`/`:entid` — which
  need the precomputed graph, not `db_name` — also work; see `kotoba-conn`'s
  docstring. Equivalent to
  `(kotoba-conn url (:graph opts) (assoc opts :db-name db-name))`."
  [url db-name opts]
  (kotoba-conn url (:graph opts) (assoc opts :db-name db-name)))

;; ─── private helpers ──────────────────────────────────────────────────────────

(defn- xrpc-url [conn nsid]
  (str (:kotoba/url conn) "/xrpc/" nsid))

(defn- req-headers [conn]
  (cond-> {"content-type" "application/json"
           "accept"       "application/json"}
    (:kotoba/token conn) (assoc "authorization"
                                (str "Bearer " (:kotoba/token conn)))
    (:kotoba/cacao conn) (-> (assoc "authorization"
                                    (str "CACAO " (:kotoba/cacao conn)))
                             (assoc "x-kotoba-did" (:kotoba/did conn)))))

(defn- post! [{:keys [http-fn json-write json-read]} conn nsid body]
  (let [resp (http-fn {:url     (xrpc-url conn nsid)
                       :method  :post
                       :headers (req-headers conn)
                       :body    (json-write body)})]
    (when-not (#{200 201} (:status resp))
      (throw (ex-info (str "kotoba XRPC error " (:status resp) ": " nsid)
                      {:nsid nsid :status (:status resp) :body (:body resp)})))
    (json-read (:body resp))))

;; ─── query projection ─────────────────────────────────────────────────────────

(defn- normalize-query
  "A vector-shaped Datomic query (`[:find ... :where ...]`, the form every
  existing caller of this ns's `:q` sends — same as `langchain.db/q`)
  parses to a MAP (`{:find [...] :where [...]}`) before going over the
  wire, since the live edge's `datomic.q` handler (`kotobase.server.
  handler/do-q`) interprets a *vector*-shaped `query_edn` as a single
  `[s p o]` triple-pattern query, not a multi-clause Datalog query — so a
  vector-shaped find/where query silently matched nothing (200 OK, empty
  rows, no error) rather than running the query the caller actually meant.
  Confirmed against the live kotobase.net edge, 2026-07-18: the exact same
  `:find`/`:where` query returns real rows when sent as a map and an empty
  set when sent as the original vector. A query already given as a map
  passes through unchanged (both `langchain.db/q` and kotoba-server's
  `do-q` already accept a map query natively)."
  [query]
  (if (map? query)
    query
    (let [groups (partition-by #{:find :in :where :with} query)]
      ;; same malformed-query hazard as langchain.db/parse-query
      ;; (independently duplicated logic, not shared code) -- see
      ;; that fn's docstring for the full odd-group-count/silent-
      ;; drop rationale.
      (when (odd? (count groups))
        (throw (ex-info "langchain.kotoba-db: malformed query -- a :find/:in/:where/:with marker must be followed by at least one value before the next marker (or end of query)"
                        {:query query})))
      (reduce (fn [m [[k] v]] (assoc m k (vec v))) {} (partition 2 groups)))))

(defn- parse-find-spec [query]
  (:find (normalize-query query)))

(defn- project-rows
  "Maps either legacy rows_edn strings or native JSON rows to the same result
  shape as langchain.db/q: scalar value, collection vector, or set of tuples."
  [wire-rows find-spec]
  (let [decode-cell (fn [cell]
                      (if (string? cell)
                        (edn/read-string cell)
                        cell))
        rows    (mapv (fn [row] (mapv decode-cell row)) wire-rows)
        scalar? (= '. (last find-spec))
        coll?   (and (= 1 (count find-spec))
                     (vector? (first find-spec))
                     (= '... (second (first find-spec))))]
    (cond
      scalar? (ffirst rows)
      coll?   (vec (distinct (map first rows)))
      :else   (set rows))))

(defn- entity-wire-value
  "eid -> the plain string kotobase-server's `do-pull` actually expects for
  `:entity` (body: {:graph :entity :pattern_edn}, handler.cljc's own
  docstring: 'body: {:graph :entity :pattern_edn}' — `entity` is used
  as-is, NEVER `edn/read-string`'d server-side, unlike `:pull`'s sibling
  `:entid`/`:q`, whose EDN-string fields (`ident_edn`/`query_edn`) ARE
  parsed there). Sending `(pr-str eid)` here — the natural-looking choice,
  since every other field on this wire IS an EDN string — silently pulled
  an empty entity against the live edge (confirmed 2026-07-18: `:entity
  \"\\\"debug-rep-1\\\"\"` → `{}`; `:entity \"debug-rep-1\"` → real attrs).

  A Datomic-style 2-tuple lookup ref (`[attr value]`, what `crm.store` and
  every other in-process `langchain.db/pull` caller already pass as `eid`)
  has `value` extracted and sent alone — this substrate has exactly one
  identity space per graph (whichever attribute a caller's schema marks
  `:db.unique/identity`, its VALUE is the entity id string directly; see
  `kotobase.server.handler`'s `hot-datoms`/`entid` for why there is no
  per-attribute identity resolution the way real Datomic's `entid` needs),
  so the ref's attr half carries no additional information the edge can
  use. A non-tuple eid (already a plain id) is coerced to a string as-is."
  [eid]
  (if (and (vector? eid) (= 2 (count eid)))
    (str (second eid))
    (str eid)))

(defn- decode-pull-value
  "A single `[*]` pull set-element, round-trip-safely decoded. Every
  non-string attribute type (keyword, boolean, number) on this wire IS
  its own pr-str (`:tier/rep`, `\"true\"`, `\"5\"` all `edn/read-string`
  back to the real value cleanly) -- but a STRING attribute's value comes
  back RAW, not pr-str'd/quoted (`\"6399 Managed Job Board (aggregate
  free-tenant pool)\"`, not `\"\\\"6399 ...\\\"\"`). Blindly
  `edn/read-string`-ing a raw multi-token string silently truncates to
  its first reader token (confirmed against the live edge, 2026-07-18:
  a value with a space came back as just its first word) -- Clojure's
  reader has no obligation to consume the whole string and doesn't error
  on leftover input via `read-string`.

  Two guards, in order: (1) a parse that comes back as a SYMBOL is always
  rejected -- this substrate's schema never legitimately stores a bare
  symbol as an attribute value, so a symbol result means `v` was actually
  a single-word raw string (`\"t1\"` parses to the symbol `t1`, and
  `(pr-str 't1)` is ALSO `\"t1\"`, so the round-trip check below alone
  cannot tell a genuine 1-word string apart from an accidental symbol
  parse -- confirmed directly: this exact false-positive broke 3 existing
  tests, e.g. a mocked `:checkpoint/thread \"t1\"` before this guard was
  added). (2) otherwise, only trust the parse when re-printing it
  recovers the EXACT original wire string (catches multi-token strings
  like the space-containing example above); anything else falls back to
  the raw string as-is.

  Restored 2026-07-24 after the `kotoba-api-async` addition briefly
  replaced this fn's call site with a bare unconditional `edn/read-
  string`, silently reintroducing the exact multi-word-string-truncation
  regression this fn was written to fix -- see `normalize-wildcard-pull`,
  the ONLY caller, shared by both `kotoba-api`'s and `kotoba-api-async`'s
  `:pull`, so both stay fixed together and cannot re-diverge silently."
  [v]
  (let [parsed (try (edn/read-string v)
                     (catch #?(:clj Exception :cljs :default) _ ::unparseable))]
    (if (and (not= parsed ::unparseable)
             (not (symbol? parsed))
             (= v (pr-str parsed)))
      parsed
      v)))

(defn- normalize-wildcard-pull
  "The result of a `[*]` pull against the live edge, one `edn/read-string`
  in (see `:pull`'s caller — `result-map` is already `{\":attr\" #{\"v\"}}`,
  e.g. `{\":rep/name\" #{\"Acme\"} \":rep/discount-tier\" #{\":tier/rep\"}}`
  — note :rep/name's element is the RAW string, not pr-str'd; see
  `decode-pull-value`), normalized to a plain Clojure map (`{:rep/name
  \"Acme\" :rep/discount-tier :tier/rep}`): each string key is itself
  further `edn/read-string`'d to a keyword, and — since this substrate
  wraps EVERY attribute's value in a set regardless of Datomic
  cardinality (confirmed against the live edge, 2026-07-18: a plain
  cardinality-one string attribute came back set-wrapped identically to
  how a cardinality-many attribute would) and this ns's callers
  (`crm.store` et al.) only ever use cardinality-one schemas — the single
  set element is taken and decoded via `decode-pull-value`. Shared by
  both `kotoba-api` and `kotoba-api-async`'s `:pull` (see that fn's own
  docstring)."
  [result-map]
  (into {}
        (map (fn [[k vs]]
               [(cond-> k (string? k) edn/read-string)
                (decode-pull-value (first vs))]))
        result-map))

;; ─── api map ─────────────────────────────────────────────────────────────────

(defn- write-scope
  "Scope param for `:transact!`: a tenant `db-name` (the edge derives +
  verifies the graph itself from the CACAO's DID — required for tenant
  writes) if present, else a precomputed `graph` (backward-compat / a
  pre-established non-tenant graph like `KG-GRAPH-CID`)."
  [conn]
  (if-let [db-name (:kotoba/db-name conn)]
    {:db_name db-name}
    {:graph (:kotoba/graph conn)}))

(defn- read-scope
  "Scope param for `:q`/`:pull`/`:entid`: the precomputed `graph` if present
  — empirically required for tenant reads, since the live edge's read ops
  don't derive the tenant graph from `db_name`+CACAO the way `transact`
  does (a `db_name`-only read silently matches nothing). Falls back to
  `db_name` for a conn built without `:graph` (e.g. an older caller of
  `kotoba-conn*`; matches that fn's prior behavior — still broken against
  the live edge's reads, but not a new regression)."
  [conn]
  (if-let [graph (:kotoba/graph conn)]
    {:graph graph}
    {:db_name (:kotoba/db-name conn)}))

(defn kotoba-api
  "Returns a langchain.db-compatible api map backed by kotoba-server XRPC.

   host-caps: {:http-fn   (fn [{:keys [url method headers body]}] => {:status n :body s})
               :json-write (fn [clj-data] => json-string)
               :json-read  (fn [json-string] => clj-data with keyword keys)}

   The returned map has the same keys as langchain.db/api:
     {:transact! :db :q :pull :entid}

   A Datomic Local or DataScript connection can also be used there;
   kotoba-api is the distributed, CID-pinned, CACAO-gated variant. Writes
   address the graph per `write-scope`, reads per `read-scope` — the live
   edge requires opposite scope params for each (see both fns' docstrings)."
  [host-caps]
  {:transact!
   (fn [conn tx-data]
     (post! host-caps conn "ai.gftd.apps.kotobase.datomic.transact"
            (cond-> (assoc (write-scope conn) :tx_edn (pr-str (vec tx-data)))
              (:kotoba/cacao conn) (assoc :cacao_b64 (:kotoba/cacao conn))))
     ;; tx-report stub — checkpointer only needs side-effect, not tempids
     {:tx-data tx-data})

   ;; The conn map itself IS the db reference — all state lives on the server.
   ;; This matches the Datomic peer model: (d/db conn) returns a db value;
   ;; here the conn already identifies the remote graph head.
   :db identity

   :q
   (fn [query conn & inputs]
     (let [data (post! host-caps conn "ai.gftd.apps.kotobase.datomic.q"
                       (cond-> (assoc (read-scope conn)
                                      ;; normalize-query: the edge's do-q treats a
                                      ;; vector query_edn as a single [s p o]
                                      ;; triple-pattern, not a multi-clause
                                      ;; find/where query -- see that fn's docstring.
                                      :query_edn  (pr-str (normalize-query query))
                                      ;; inputs_edn: non-$ bindings ($ is already the graph)
                                      :inputs_edn (mapv pr-str inputs))
                         (:kotoba/cacao conn) (assoc :cacao_b64 (:kotoba/cacao conn))))]
       (project-rows (or (:rows_edn data) (:rows data) [])
                     (parse-find-spec query))))

   :pull
   (fn [conn pattern eid]
     ;; ALWAYS requests [*], regardless of the caller's own `pattern` --
     ;; confirmed against the live edge, 2026-07-18: a `pattern_edn` naming
     ;; specific attributes (e.g. `[:rep/name]`, the natural-looking way to
     ;; ask for less than everything) silently returned `{}` every time,
     ;; while `[*]` alone returned real attrs for the exact same entity.
     ;; This is a live server-side limitation (kotobase-peer's `pull`
     ;; pattern-matching against a non-wildcard attr list), not something
     ;; fixable purely at this wire layer -- the workaround is to always
     ;; pull everything and filter client-side (see `select-keys` below),
     ;; which only supports FLAT attribute-list patterns like this ns's
     ;; own callers (`crm.store` et al.) use -- a nested pull pattern
     ;; (`{attr [sub-pattern]}`) is NOT reproduced by this workaround.
     (let [data (post! host-caps conn "ai.gftd.apps.kotobase.datomic.pull"
                       (cond-> (assoc (read-scope conn)
                                      ;; entity-wire-value, NOT (pr-str eid) --
                                      ;; see that fn's docstring.
                                      :entity      (entity-wire-value eid)
                                      :pattern_edn (pr-str '[*]))
                         (:kotoba/cacao conn) (assoc :cacao_b64 (:kotoba/cacao conn))))
           ;; result_edn (NOT entity_edn -- kotobase.server.handler/do-pull's
           ;; pattern_edn branch, which this fn always takes since :pattern_edn
           ;; is unconditionally sent above, wire-encodes the whole pull result
           ;; as :result_edn; do-pull's OTHER branch (no pattern_edn, a legacy
           ;; flat-attrs shape this fn never triggers) returns :attrs instead --
           ;; neither branch of the live edge ever returns a field literally
           ;; named entity_edn. That name only exists on the UNRELATED
           ;; datomic.entity NSID (do-entity), which this :pull fn doesn't
           ;; call. Reading a field that's never present silently produced nil
           ;; for every :pull call against the live edge -- confirmed directly,
           ;; 2026-07-18.
           full (normalize-wildcard-pull (edn/read-string (:result_edn data)))
           ;; This substrate has no separate storage for the identity
           ;; attribute itself -- its VALUE literally IS the entity id
           ;; (confirmed 2026-07-18: a rep transacted as {:rep/id "x"
           ;; :rep/name "y"} came back from a wildcard pull with :rep/name
           ;; present but NO :rep/id key at all), so it never appears as
           ;; its own key in the pull result. When `eid` was a `[attr
           ;; value]` lookup ref, re-add `{attr value}` so a caller that
           ;; pulls an identity attribute back out (e.g. `crm.store`'s
           ;; `pull->rep`/`pull->account`/etc., every one of which gates
           ;; on that id field being present in the pulled map) sees it —
           ;; without this, EVERY entity looked up by lookup ref pulled
           ;; back as a map indistinguishable from "entity does not
           ;; exist" to those callers.
           full (if (and (vector? eid) (= 2 (count eid)))
                  (assoc full (first eid) (second eid))
                  full)]
       (if (= pattern '[*]) full (select-keys full pattern))))

   :entid
   (fn [conn eid]
     ;; entity_id (NOT entity -- kotobase.server.handler/do-entid's
     ;; response field is :entity_id; :entity is a DIFFERENT NSID's
     ;; (datomic.pull/datomic.ident) request/response field name. Reading
     ;; the wrong one silently produced nil for every :entid call against
     ;; the live edge -- confirmed by code inspection, 2026-07-18 (see
     ;; handler.cljc's do-entid: `{:ok true :graph graph :entity_id ...}`).
     (:entity_id (post! host-caps conn "ai.gftd.apps.kotobase.datomic.entid"
                        (cond-> (assoc (read-scope conn) :ident_edn (pr-str eid))
                          (:kotoba/cacao conn) (assoc :cacao_b64 (:kotoba/cacao conn))))))})

;; ─── portable promise-like seam (for kotoba-api-async) ────────────────────────

(defn- p-resolved
  "v -> a promise-like of v: a real `js/Promise` under `:cljs`, the plain
  value itself under `:clj`. Kept private and local to this ns (langchain
  has zero third-party runtime deps, ADR-0001) rather than reusing any
  app's own `pcompat`/similar ns -- this is the SAME documented duality
  every kotobase-backed edge caller already relies on one layer up (e.g.
  `commitledger.edge.pcompat`/`credit.edge.pcompat`'s `resolved`), just
  needed here too since `kotoba-api-async`'s own :db op has no I/O to
  perform and must still return a promise-like."
  [v]
  #?(:cljs (js/Promise.resolve v)
     :clj  v))

(defn- p-then
  "p is a promise-like (see `p-resolved`) -- `:cljs` chains a real
  `js/Promise` via `.then`; `:clj` calls `f` on `p` directly (JVM callers
  of `kotoba-api-async` pass a synchronous-under-the-hood mock
  `:http-fn`, so there is no event loop to chain against, matching every
  app-level `pcompat/then`'s own `:clj` branch)."
  [p f]
  #?(:cljs (.then p f)
     :clj  (f p)))

(defn- post!-async
  "Like `post!`, but `http-fn` is ASYNC (returns a promise-like of
  `{:status :body}` instead of the plain map itself) -- the contract a
  real Cloudflare Pages Function needs, since `js/fetch` there is
  unconditionally async with no synchronous I/O primitive available at
  all. Returns a promise-like of the parsed response body; throws the
  same `kotoba XRPC error <status>: <nsid>` ex-info a non-200/201 status
  produces (raised inside the `p-then` callback, so on `:cljs` it
  surfaces as a rejected promise the caller's own `.catch` handles, same
  as any other exception thrown inside a `.then` callback)."
  [{:keys [http-fn json-write json-read]} conn nsid body]
  (p-then (http-fn {:url     (xrpc-url conn nsid)
                    :method  :post
                    :headers (req-headers conn)
                    :body    (json-write body)})
          (fn [resp]
            (when-not (#{200 201} (:status resp))
              (throw (ex-info (str "kotoba XRPC error " (:status resp) ": " nsid)
                              {:nsid nsid :status (:status resp) :body (:body resp)})))
            (json-read (:body resp)))))

(defn kotoba-api-async
  "Like `kotoba-api`, but for hosts with NO synchronous I/O primitive at
  all (a Cloudflare Pages Function, where `js/fetch` is unconditionally
  async) -- every op threads through an ASYNC `:http-fn` (`(fn [{:keys
  [url method headers body]}] => promise-like of {:status n :body s})`,
  NOT `kotoba-api`'s synchronous `{:status n :body s}` directly) and
  every `:db-api` fn below returns a promise-like in turn (a real
  `js/Promise` under `:cljs`, the plain value itself under `:clj` -- see
  `p-resolved`/`p-then`). Same `{:transact! :db :q :pull :entid}` shape,
  same wire semantics/gotchas as `kotoba-api` (map-shaped `query_edn`,
  always-wildcard `pattern_edn`, `:result_edn`/`:entity_id` field names,
  `write-scope`/`read-scope`'s `:db_name`-vs-`:graph` split, double-EDN-
  encoded cells -- see `kotoba-api`'s own docstring and this ns's private
  helpers for the full rationale on each) -- this fn only adds the async
  plumbing on top, it does not change any wire behavior.

   host-caps: {:http-fn   (fn [{:keys [url method headers body]}] => promise-like of {:status n :body s})
               :json-write (fn [clj-data] => json-string)
               :json-read  (fn [json-string] => clj-data with keyword keys)}

  `:db` has no I/O to perform (the conn map itself IS the db reference,
  same as `kotoba-api`) but is still wrapped in `p-resolved` so it
  satisfies the SAME promise-like contract as every other op here for a
  caller that treats every `:db-api` fn uniformly."
  [host-caps]
  {:transact!
   (fn [conn tx-data]
     (p-then (post!-async host-caps conn "ai.gftd.apps.kotobase.datomic.transact"
                          (cond-> (assoc (write-scope conn) :tx_edn (pr-str (vec tx-data)))
                            (:kotoba/cacao conn) (assoc :cacao_b64 (:kotoba/cacao conn))))
             ;; tx-report stub — checkpointer only needs side-effect, not tempids
             (fn [_] {:tx-data tx-data})))

   ;; The conn map itself IS the db reference — same as `kotoba-api`'s :db.
   :db (fn [conn] (p-resolved conn))

   :q
   (fn [query conn & inputs]
     (p-then (post!-async host-caps conn "ai.gftd.apps.kotobase.datomic.q"
                          (cond-> (assoc (read-scope conn)
                                         :query_edn  (pr-str (normalize-query query))
                                         :inputs_edn (mapv pr-str inputs))
                            (:kotoba/cacao conn) (assoc :cacao_b64 (:kotoba/cacao conn))))
             (fn [data]
               (project-rows (or (:rows_edn data) (:rows data) [])
                             (parse-find-spec query)))))

   :pull
   (fn [conn pattern eid]
     (p-then (post!-async host-caps conn "ai.gftd.apps.kotobase.datomic.pull"
                          (cond-> (assoc (read-scope conn)
                                         :entity      (entity-wire-value eid)
                                         :pattern_edn (pr-str '[*]))
                            (:kotoba/cacao conn) (assoc :cacao_b64 (:kotoba/cacao conn))))
             (fn [data]
               (let [full (normalize-wildcard-pull (edn/read-string (:result_edn data)))
                     full (if (and (vector? eid) (= 2 (count eid)))
                            (assoc full (first eid) (second eid))
                            full)]
                 (if (= pattern '[*]) full (select-keys full pattern))))))

   :entid
   (fn [conn eid]
     (p-then (post!-async host-caps conn "ai.gftd.apps.kotobase.datomic.entid"
                          (cond-> (assoc (read-scope conn) :ident_edn (pr-str eid))
                            (:kotoba/cacao conn) (assoc :cacao_b64 (:kotoba/cacao conn))))
             (fn [data] (:entity_id data))))})

;; ─── kg.ingest surface ────────────────────────────────────────────────────────

(defn kg-ingest!
  "POST one entity to ai.gftd.apps.kotobase.kg.ingest.

   Writes to the kotobase-kg-v1 named graph (shared multi-tenant KG).
   Auth: Bearer JWT in conn is sufficient; CACAO is also forwarded when present.

   host-caps – {:http-fn :json-write :json-read}
   conn      – kotoba-conn (only url + auth are used; :kotoba/graph is ignored)
   entity    – {:id    string          ; unique entity ID, e.g. \"<thread>/<step>\"
                :kind  string          ; entity type, e.g. \"langgraph/checkpoint\"
                :claims [{:pred str :value str}]  ; free-form key-value pairs
                :relations [{:pred str :dst-id str}]  ; optional edges}"
  [host-caps conn entity]
  (post! host-caps conn "ai.gftd.apps.kotobase.kg.ingest"
         (cond-> {:id     (:id entity)
                  :kind   (:kind entity)
                  :claims (vec (:claims entity []))}
           (seq (:relations entity)) (assoc :relations (vec (:relations entity)))
           (:kotoba/cacao conn)      (assoc :cacao_b64 (:kotoba/cacao conn)))))
