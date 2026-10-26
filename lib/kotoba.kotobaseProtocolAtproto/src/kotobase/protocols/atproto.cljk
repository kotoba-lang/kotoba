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

(defn handle
  "XRPC handler. Dispatches /xrpc/{nsid}; unknown NSIDs → 501."
  [{:keys [store] :as ctx} req]
  (let [segs (http/segments (:path req))]
    (if-not (= "xrpc" (first segs))
      (http/not-found)
      (let [nsid (second segs)
            get? (= :get (:method req))
            post? (= :post (:method req))]
        (case nsid
          "com.atproto.repo.getRecord"
          (if get? (get-record store req) (http/method-not-allowed))
          "com.atproto.repo.listRecords"
          (if get? (list-records store req) (http/method-not-allowed))
          "com.atproto.repo.putRecord"
          (if post? (put-record store req) (http/method-not-allowed))
          "com.atproto.repo.deleteRecord"
          (if post? (delete-record store req) (http/method-not-allowed))
          "com.atproto.sync.getBlob"
          (if get? (get-blob ctx req) (http/method-not-allowed))
          (xrpc-error 501 "MethodNotImplemented"
                      (str "unsupported nsid: " (or nsid ""))))))))
