(ns kotobase.protocols.atproto
  "atproto.kotobase.net — AT-Protocol XRPC projection of kotobase
  tenant records (ADR-2607171700, KRP §3.2 Record / §5).

  SCOPE GUARD: this is the DATA-plane record API over kotobase tenant
  graphs — it is NOT a social PDS and does not touch the aozora.app
  consolidation (ADR-2607062200). No app.bsky.*, no firehose, no
  handle resolution here.

  Mapping:
    (did, collection nsid) → IStore collection [:kotobase.at/records did nsid]
    rkey                   → doc key
    record                 → doc value (JSON-decoded, string keys)
    blobs                  → shared block space (kotobase.protocols.blocks)

  Implemented XRPC subset (v0.1):
    GET  /xrpc/com.atproto.repo.getRecord?repo&collection&rkey
    GET  /xrpc/com.atproto.repo.listRecords?repo&collection
    POST /xrpc/com.atproto.repo.putRecord     {repo collection rkey record}
    POST /xrpc/com.atproto.repo.deleteRecord  {repo collection rkey}
    GET  /xrpc/com.atproto.sync.getBlob?did&cid

  Authentication (CACAO) is the deploy shell's job, same as the
  kotobase.net Worker (kotobase-client mints, the edge verifies)."
  (:require [kotobase.protocols.blocks :as blocks]
            [kotobase.protocols.http :as http]
            [kotobase.protocols.json :as json]
            [kotobase.store :as st]))

(defn records-coll [did nsid] [:kotobase.at/records did nsid])

(defn at-uri [did nsid rkey] (str "at://" did "/" nsid "/" rkey))

(defn- json-response [status m]
  (http/response status {"content-type" "application/json"} (json/encode m)))

(defn- xrpc-error [status error msg]
  (json-response status {"error" error "message" msg}))

(defn- audit! [store op did nsid rkey]
  (st/-append store :kotobase.protocols/audit
              {:surface :atproto :op op :did did :collection nsid :rkey rkey}))

(defn- parse-body [req]
  (try (json/parse (or (:body req) "{}"))
       (catch #?(:clj Exception :cljs :default) _ nil)))

(defn- get-record [store req]
  (let [did  (http/query-param req "repo")
        nsid (http/query-param req "collection")
        rkey (http/query-param req "rkey")]
    (if-not (and did nsid rkey)
      (xrpc-error 400 "InvalidRequest" "repo, collection and rkey are required")
      (if-let [record (st/-get store (records-coll did nsid) rkey)]
        (json-response 200 {"uri" (at-uri did nsid rkey) "value" record})
        (xrpc-error 400 "RecordNotFound"
                    (str "record not found: " (at-uri did nsid rkey)))))))

(defn- list-records [store req]
  (let [did  (http/query-param req "repo")
        nsid (http/query-param req "collection")]
    (if-not (and did nsid)
      (xrpc-error 400 "InvalidRequest" "repo and collection are required")
      (let [records (->> (st/-list store (records-coll did nsid))
                         sort
                         (keep (fn [rkey]
                                 (when-let [v (st/-get store (records-coll did nsid) rkey)]
                                   {"uri" (at-uri did nsid rkey) "value" v}))))]
        (json-response 200 {"records" (vec records)})))))

(defn- put-record [store req]
  (let [b (parse-body req)
        {:strs [repo collection rkey record]} b]
    (if-not (and repo collection rkey (map? record))
      (xrpc-error 400 "InvalidRequest"
                  "body must carry repo, collection, rkey and a record object")
      (do (st/-put store (records-coll repo collection) rkey record)
          (audit! store :put-record repo collection rkey)
          (json-response 200 {"uri" (at-uri repo collection rkey)})))))

(defn- delete-record [store req]
  (let [{:strs [repo collection rkey]} (parse-body req)]
    (if-not (and repo collection rkey)
      (xrpc-error 400 "InvalidRequest" "body must carry repo, collection and rkey")
      (do (st/-put store (records-coll repo collection) rkey nil)
          (audit! store :delete-record repo collection rkey)
          (json-response 200 {})))))

(defn- get-blob [ctx req]
  (let [did (http/query-param req "did")
        cid (http/query-param req "cid")]
    (if-not (and did cid)
      (xrpc-error 400 "InvalidRequest" "did and cid are required")
      (if-let [b (blocks/get-block ctx cid)]
        (http/response 200 {"content-type" (:content-type b)} (:bytes b))
        (xrpc-error 400 "BlobNotFound" (str "blob not found: " cid))))))

(def nsid-methods
  "The NSIDs this surface implements, and the one method each answers on.

  `store-free-response` and `handle` both read this, so an NSID cannot be
  added to the dispatch and missed by the pre-hydrate check — the drift that
  would turn a supported call into a 501."
  {"com.atproto.repo.getRecord"    :get
   "com.atproto.repo.listRecords"  :get
   "com.atproto.repo.putRecord"    :post
   "com.atproto.repo.deleteRecord" :post
   "com.atproto.sync.getBlob"      :get})

(defn store-free-response
  "The response for a request whose answer does not depend on the store, or
  nil when answering does need one.

  Three shapes qualify: a path that is not `/xrpc/*` (404), an NSID this
  surface does not implement (501), and an implemented NSID reached with the
  wrong method (405). None of them reads a datom.

  **A deploy shell should call this BEFORE it hydrates.** On kotobase.net the
  atproto surface is the only one whose reads are open, so an unauthenticated
  GET runs past the credential check into the graph path, and a request that
  names no `repo` resolves to the shared production chain. Measured 2026-08-30
  against atproto.kotobase.net: of 8 requests whose correct answer is this
  function's 501, **5 came back as Cloudflare 1102** (Worker exceeded resource
  limits) — the Worker hydrated that chain before discovering it had a static
  answer. The other 4 surfaces on the same Worker answered 32 of 32, because
  they require a credential and return 401 before doing any work."
  [req]
  (let [segs (http/segments (:path req))]
    (if-not (= "xrpc" (first segs))
      (http/not-found)
      (let [nsid (second segs)]
        (if-let [method (get nsid-methods nsid)]
          (when-not (= method (:method req)) (http/method-not-allowed))
          (xrpc-error 501 "MethodNotImplemented"
                      (str "unsupported nsid: " (or nsid ""))))))))

(defn handle
  "XRPC handler. Dispatches /xrpc/{nsid}; unknown NSIDs → 501.

  The store-free cases are decided by `store-free-response` first, so the
  dispatch below runs only for an implemented NSID on its own method."
  [{:keys [store] :as ctx} req]
  (or (store-free-response req)
      (case (second (http/segments (:path req)))
        "com.atproto.repo.getRecord" (get-record store req)
        "com.atproto.repo.listRecords" (list-records store req)
        "com.atproto.repo.putRecord" (put-record store req)
        "com.atproto.repo.deleteRecord" (delete-record store req)
        "com.atproto.sync.getBlob" (get-blob ctx req)
        ;; Unreachable: `store-free-response` returns non-nil for every NSID
        ;; outside `nsid-methods`. Kept because `case` without a default
        ;; throws, and a thrown error here would be a 500 where the contract
        ;; says 501.
        (xrpc-error 501 "MethodNotImplemented" "unsupported nsid"))))
