(ns kotobase.protocols.sparql
  "sparql.<apex> -- the SPARQL 1.1 Protocol
  (https://www.w3.org/TR/sparql11-protocol/) wire surface, wrapping
  `kotoba-lang/sparql`'s already-real EDN algebra
  (BGP/join/filter/union/optional/project/distinct/order-by/slice) around
  data materialized by `kotoba-lang/kotobase-query`'s bridge -- ADR-2607172300
  in `com-junkawasaki/root`, the SPARQL row of the query-protocol-extension
  batch (`kotobase-query`/`datomic-client-shim`/`org-postgresql-wire`/
  `org-opencypher-cypher`/`org-w3-sparql-protocol`).

  Same ring-shaped request/response plumbing `kotoba-lang/kotobase-protocols`
  establishes for this repo family (a request is `{:method :path :query
  :headers :body}`, a response is `{:status :headers :body}`; `handle` is
  pure: `(handle ctx req) -> resp`), NOT a code dependency on that repo --
  see `kotobase.protocols.sparql.json`'s docstring for why (ADR-2607172300's
  dependency table lists only `kotoba-lang/sparql` + `kotoba-lang/
  kotobase-query` for this repo).

  ## Implemented subset (v0.1)

  - `GET /sparql?query=<SPARQL text>` (§2.1.1/§2.1.4 of the protocol spec
    -- query via URL-encoded parameter; per this family's convention the
    `:query` map on a request already arrives percent-decoded, the same
    contract `kotobase-protocols`' handlers assume of `:query`/`http/
    query-param` -- percent-decoding a raw query string is the deploy
    shell's job, not this handler's).
  - `POST /sparql` with `Content-Type: application/sparql-query` -- the
    ENTIRE request body IS the query text, no further decoding (§2.1.2).
    This is the PRIMARY supported POST form: zero decoding ambiguity.
  - `POST /sparql` with `Content-Type: application/x-www-form-urlencoded`
    and a `query` field (§2.1.3) -- SECONDARY supported form. Percent-
    decoding here is ASCII-safe only (each `%XX` run is decoded as UTF-8
    bytes via `percent-decode` below); this is spec-correct for any
    application/x-www-form-urlencoded producer (non-ASCII MUST already be
    percent-escaped in this content-type), so no real limitation, just
    stated for clarity since GET's `:query` map is NOT decoded by this ns
    at all (upstream's job) while POST form bodies ARE (this ns's job,
    since nothing upstream of `:body` has parsed form-encoding yet).
  - `Accept: application/sparql-results+json` (or `*/*`/absent, which
    default to JSON) -- SPARQL 1.1 Query Results JSON Format
    (https://www.w3.org/TR/sparql11-results-json/) for both `SELECT` and
    `ASK`. Any other `Accept` value that does not also accept JSON gets
    `406 Not Acceptable` -- **XML and CSV results formats are explicitly
    NOT implemented for SELECT/ASK** (ADR-2607172300 / the task brief for this
    repo: \"XML/CSV are a nice-to-have, not required for v0.1\").
  - The query LANGUAGE subset is exactly what `kotoba-lang/sparql`'s
    algebra + `kotobase.protocols.sparql.parser`'s translation support --
    see that namespace's docstring for the precise grammar subset and its
    explicit non-goals (no property paths / GRAPH / SERVICE / aggregates /
    subqueries / predicate-object lists).
  - `CONSTRUCT`/`DESCRIBE`/`UPDATE` are NOT implemented (no RDF-graph-out
    or write path in `kotoba-lang/sparql`'s algebra to wrap -- `SELECT`/
    `ASK` only, matching that repo's own `select`/`ask` public API)."
  (:require [kotoba.lang.text :as str]
            [kotobase.query.bridge :as bridge]
            [kotobase.protocols.sparql.json :as json]
            [kotobase.protocols.sparql.ntriples :as nt]
            [kotobase.protocols.sparql.parser :as parser]
            [kotobase.protocols.sparql.quads :as quads]
            [kotobase.protocols.sparql.results :as results]
            [sparql.core :as sparql]))

;; ------------------------------------------------------------- ring bits

(defn- query-param [req k] (get (:query req) k))
(defn- header [req k] (get (:headers req) (str/lower k)))

(defn- response
  ([status headers body] {:status status :headers headers :body body})
  ([status body] (response status {} body)))

(defn- json-response [status body-edn]
  (response status {"content-type" "application/sparql-results+json"} (json/encode body-edn)))

(defn- error-response [status msg]
  (response status {"content-type" "text/plain; charset=utf-8"} msg))

;; --------------------------------------------------------- form decoding

(defn- hex->int [hex] #?(:clj (Integer/parseInt hex 16) :cljs (js/parseInt hex 16)))

(defn- char->byte [c] #?(:clj (int (.charAt ^String c 0)) :cljs (.charCodeAt c 0)))

(defn- decode-utf8-bytes [bytes]
  #?(:clj (String. (byte-array (map unchecked-byte bytes)) "UTF-8")
     :cljs (.decode (js/TextDecoder. "utf-8") (js/Uint8Array.from (clj->js bytes)))))

(defn percent-decode
  "application/x-www-form-urlencoded value -> decoded string. `+` -> space;
  `%XX` runs are collected as raw bytes and UTF-8-decoded together (so a
  multi-byte percent-encoded UTF-8 sequence like `%E3%81%82` decodes
  correctly, not byte-by-byte); every other input character is ASCII-range
  by the content-type's own contract (a producer of this content-type MUST
  percent-escape anything outside that range)."
  [s]
  (let [s (str/replace s "+" " ")]
    (loop [i 0 bytes (transient [])]
      (if (>= i (count s))
        (decode-utf8-bytes (persistent! bytes))
        (let [c (subs s i (inc i))]
          (if (and (= c "%") (<= (+ i 3) (count s)))
            (recur (+ i 3) (conj! bytes (hex->int (subs s (inc i) (+ i 3)))))
            (recur (inc i) (conj! bytes (char->byte c)))))))))

(defn- parse-form-urlencoded [body]
  (into {}
        (map (fn [pair]
               (let [[k v] (str/split pair #"=" 2)]
                 [(percent-decode (or k "")) (percent-decode (or v ""))])))
        (remove str/blank? (str/split (or body "") #"&"))))

;; --------------------------------------------------------- content negotiation

(defn- accepts-json?
  "True if `accept` (the raw `Accept` header, possibly nil/absent/`*/*`/a
  comma-separated list with `;q=` params we ignore -- v0.1 does no real
  q-value ranking, just membership) is satisfied by
  `application/sparql-results+json`. No `Accept` header, or one containing
  `*/*`, defaults to yes (JSON is the only format offered, so `*/*` can
  only mean JSON here)."
  [accept]
  (or (str/blank? (or accept ""))
      (let [types (map #(-> % (str/split #";") first str/trim) (str/split accept #","))]
        (boolean (some #(or (= "*/*" %) (= "application/sparql-results+json" %) (= "application/json" %)) types)))))

;; ------------------------------------------------------------- extraction

(defn- extract-query
  "The SPARQL query text out of `req`, or nil if none was supplied. See ns
  docstring for exactly which GET/POST shapes are read."
  [req]
  (case (:method req)
    :get (query-param req "query")
    :post (let [ctype (str/lower (or (header req "content-type") ""))]
            (cond
              (str/starts-with? ctype "application/sparql-query") (:body req)
              (str/starts-with? ctype "application/x-www-form-urlencoded")
              (get (parse-form-urlencoded (:body req)) "query")
              :else nil))
    nil))

;; ------------------------------------------------------------------ handle

(def ^:private graph-forms
  "The two forms whose answer is an RDF graph rather than a solution table."
  #{:construct :describe :describe-solutions})

(defn- graph-form? [form] (contains? graph-forms form))

(defn- accepts-ntriples?
  "Whether the client will take N-Triples. `*/*` and a missing header count,
  same as the JSON path: a client that expressed no preference gets the one
  format there is rather than a 406 telling it so."
  [accept]
  (let [a (str/lower (or accept ""))]
    (or (str/blank? a)
        (str/includes? a "*/*")
        (str/includes? a nt/content-type)
        (str/includes? a "text/plain"))))

(defn- ntriples-response [graph]
  (response 200
            {"content-type" (str nt/content-type "; charset=utf-8")
             "cache-control" "no-store"}
            (nt/graph->ntriples graph)))

(defn scan-patterns
  "Every `[s p o]` a parsed query needs from a `datom.source/IPatternSource`.

  Public because the prefetch is the DEPLOY SHELL's job, not this handler's:
  scanning the source is asynchronous and this handler is synchronous by
  contract, so a shell parses, prefetches, and only then calls `handle` with
  `:source` in ctx, using `kotobase.protocols.sparql.parser/parse`.

  DESCRIBE has no algebra — it names terms and wants every triple they appear
  in, which is a scan per term in each position."
  [parsed]
  (if (= :describe (:form parsed))
    (quads/describe-scan-patterns (:terms parsed))
    (quads/algebra->scan-patterns (:algebra parsed))))

(defn handle
  "SPARQL 1.1 Protocol handler. `ctx` is `{:store IStore, :coll-keys
  [\"coll1\" ...], :visible? (fn [{:keys [s p o]}]) -> bool}`. `:coll-keys`
  is the fixed set of `kotobase.store` collections this endpoint exposes as
  its RDF dataset (there is no per-request dataset selection -- SPARQL's
  own `default-graph-uri`/`named-graph-uri` protocol params are out of
  scope, matching `kotoba-lang/sparql`'s own no-named-graphs boundary).
  `:visible?` is REQUIRED, same discipline as `kotobase.query.bridge`/
  `arrangement.datalog` (ADR-2607050500) -- see `kotobase.protocols.sparql.
  quads` ns docstring for why it is enforced here rather than via
  `bridge/q`.

  ctx may instead carry `:source` -- a `datom.source/IPatternSource` the
  deploy shell has already prefetched for this query's patterns (see
  `scan-patterns`). Then `:store`/`:coll-keys` are not read at all and what
  the query costs is its own patterns rather than the whole plane
  (superproject ADR-2608039970).

  Without `:source`, v0.1 re-materializes `:coll-keys` from `:store` on EVERY
  request (no caching between requests) -- the same linear-scan limitation
  `kotobase.query.bridge/materialize` itself documents; this handler adds
  no caching on top of it."
  [{:keys [store coll-keys visible?] :as ctx} req]
  (cond
    (not (#{:get :post} (:method req)))
    (error-response 405 "method not allowed: GET and POST only")

    (not (ifn? visible?))
    (error-response 500 "server misconfigured: ctx :visible? is required (ADR-2607050500)")

    :else
    (let [query-text (extract-query req)]
      (cond
        (str/blank? (or query-text ""))
        (error-response 400 "missing 'query' -- GET ?query=..., POST application/sparql-query body, or POST application/x-www-form-urlencoded 'query' field")

        :else
        (let [parsed (try (parser/parse query-text) (catch #?(:clj Exception :cljs :default) e e))]
          (cond
            (instance? #?(:clj Exception :cljs js/Error) parsed)
            (error-response 400 (str "SPARQL parse error: " #?(:clj (.getMessage ^Exception parsed) :cljs (.-message parsed))))

            ;; Content negotiation depends on the FORM, not just the header:
            ;; SELECT/ASK answer a solution table and CONSTRUCT/DESCRIBE answer
            ;; a graph, and `application/sparql-results+json` has no way to say
            ;; "these are triples". Checking the header before knowing which
            ;; one was asked for is how a graph ends up mislabelled as a
            ;; results table.
            (and (graph-form? (:form parsed)) (not (accepts-ntriples? (header req "accept"))))
            (error-response 406 (str "CONSTRUCT and DESCRIBE return an RDF graph; only "
                                     nt/content-type " is supported (no Turtle or RDF/XML yet)"))

            (and (not (graph-form? (:form parsed))) (not (accepts-json? (header req "accept"))))
            (error-response 406 "only application/sparql-results+json is supported for SELECT and ASK (no XML/CSV yet)")

            :else
            ;; Two ways to get the quads, and the ctx says which:
            ;;
            ;; `:source` — a datom.source/IPatternSource, already prefetched
            ;; for THIS query's patterns by the deploy shell (the scan is
            ;; async, this handler is sync — same split the kotobase Worker
            ;; uses for documents). Reads the patterns the algebra names.
            ;;
            ;; otherwise — materialize the whole plane and run the algebra
            ;; over it. `db-for` memoises when ctx carries a content address
            ;; and builds fresh when it does not (ADR-2607310900 L1).
            (let [quad-seq (if-let [source (:source ctx)]
                             (quads/source->quads source (scan-patterns parsed) visible?)
                             (quads/datoms->quads (bridge/db-for ctx store coll-keys)
                                                  visible?))]
              (case (:form parsed)
                :select (json-response 200 (results/select->json (:output-vars parsed)
                                                                   (sparql/select (:algebra parsed) quad-seq)))
                :ask (json-response 200 (results/ask->json (sparql/ask (:algebra parsed) quad-seq)))
                :construct (ntriples-response
                            (sparql/construct (:template parsed) (:algebra parsed) quad-seq))
                :describe (ntriples-response (sparql/describe (:terms parsed) quad-seq))
                :describe-solutions (ntriples-response
                                     (sparql/describe-solutions (:output-vars parsed)
                                                                (:algebra parsed) quad-seq))))))))))
