(ns kotobase.protocols.ipfs-pinning
  "IPFS Pinning Service API (https://ipfs.github.io/pinning-services-api-spec/)
  projected onto the shared block space `kotobase.protocols.blocks` already
  reads/writes (ADR-2607172210 — this extension stays inside
  kotobase-protocols rather than becoming a 4th IPFS-adjacent repo, since it
  is pure incremental extension of the exact same block space that
  `kotobase.protocols.ipfs`, `kotoba-lang/ipfs`, and `gftdcojp/net-kotobase-ipfs`
  already share; see the Rejected section of that ADR).

  This is the WRITE-SIDE companion to `kotobase.protocols.ipfs`'s read-only
  gateway, not a relaxation of it: `ipfs.cljc`'s docstring says the HTTP
  surface is 'READ-ONLY by design' and that writes 'go through the library
  fn `blocks/put-block!` inside an authenticated deploy shell' — a pinning
  request IS exactly that authenticated-deploy-shell write path, made real
  over HTTP. It lives in its own namespace/handler (and, per router.cljc, its
  own subdomain) rather than adding write methods to `ipfs.cljc` itself, so
  '`GET`/`HEAD` on the ipfs surface is always side-effect-free' stays
  mechanically true.

  HONESTY NOTE — v0.1 has no pinning daemon: the real Pinning Service API
  spec models a pin request as async work that transitions
  queued → pinning → pinned/failed while a remote node fetches+pins the CID
  from the given `origins`. This library has no background worker and no
  peer connectivity, and does not act on `origins` at all — they are
  accepted and stored for request/response shape compatibility only, never
  dialed. So a request here is decided **synchronously at POST time** and
  can only ever land in one of two terminal statuses:
    - the CID's block is already present locally (`blocks/get-block`) →
      `\"pinned\"`
    - the CID's block is NOT present → `\"failed\"`, with a human-readable
      `info.reason`. We deliberately do NOT return `\"queued\"` for the
      missing-block case: queueing would imply a pipeline that will
      eventually complete, and none exists. A real async daemon (fetch CID
      from `origins`, flip status queued→pinning→pinned/failed in the
      background) is the obvious extension seam if one is ever built.

  Mapping:
    request id  → `hash/fingerprint` over `cid + \"|\" + now + \"|\" + seq`,
                  where `seq` is a monotonic counter obtained by
                  `-append`-ing a throwaway event to the
                  `:kotobase.protocols.ipfs-pinning/id-seq` stream (IStore
                  stamps every appended event with a monotonic `:seq` — this
                  reuses that instead of keeping local mutable state, so the
                  library stays pure over the injected store). Guarantees a
                  fresh id even for two pin requests of the same cid at the
                  same `now`.
    pin request → IStore doc `[:kotobase.protocols/pins requestid]`
                  `{:pin/cid :pin/name :pin/status :pin/created :pin/origins}`.
    DELETE      → tombstones the pin **request** doc only (nil value, same
                  convention `s3.cljc` object DELETE uses) — the underlying
                  block is untouched. Multiple pin requests may reference the
                  same block, exactly like `blocks.cljc`'s own
                  content-addressed dedup: pins and blocks are different
                  lifecycles.

  Implemented subset (v0.1):
    POST   /pins               create a pin request — body {cid, name?, origins?}
    GET    /pins/{requestid}   fetch one pin request's status
    GET    /pins               list pin requests — `cid=`/`status=` filters
    DELETE /pins/{requestid}   remove a pin request (not the block)

  Deliberately out of scope v0.1 (documented here, not silently dropped):
  `name=`/`before=`/`after=`/`limit=`/`meta=` list filters, `POST
  /pins/{requestid}` (\"replace\"), `delegates`, per-pin `meta`, and any real
  peering/fetch against `origins`. Authentication (the Pinning API spec's
  bearer token) is the deploy shell's job, same split every other surface in
  this repo uses (CACAO verification lives at the edge, not in the engine).

  Discovery advertise (ADR-2608160300) is the same split. This namespace
  does not require ipni. Optional `ctx` key `:advertise` is
  `(fn [event] …)` where `event` is
  `{:cid :op :requestid :context-id :mutates-cid?}`. `:cid` is the content
  CID. `:op` is `:advertise` on the first pinned request for that CID and
  `:remove` when the last pinned request for that CID is deleted. Missing
  hook is silence, not failure. A thrown hook or `{:ok? false}` is audited
  and does not change pin status — local block presence is the pin
  contract; IPNI is discovery. The deploy shell maps this event onto
  `kotoba.protocol.discover/advertise-live` / `ipni.advertise`."
  (:require [kotobase.protocols.blocks :as blocks]
            [kotobase.protocols.hash :as hash]
            [kotobase.protocols.http :as http]
            [kotobase.protocols.json :as json]
            [kotobase.store :as st]))

(def pins-coll :kotobase.protocols/pins)

(defn- json-response [status m]
  (http/response status {"content-type" "application/json"} (json/encode m)))

(defn- pin-error [status reason]
  (json-response status {"error" reason}))

(defn- audit! [store op requestid cid]
  (st/-append store :kotobase.protocols/audit
              {:surface :ipfs-pinning :op op :requestid requestid :cid cid}))

(defn- next-seq!
  "Monotonic counter used only to keep generated request ids unique — see
  the id scheme note in the namespace docstring."
  [store]
  (:seq (st/-append store :kotobase.protocols.ipfs-pinning/id-seq {})))

(defn- gen-requestid [store cid now]
  (hash/fingerprint (str cid "|" now "|" (next-seq! store))))

(defn- pinned-request-ids
  "Live pinned request ids for `cid`. Tombstones (`nil`) and failed
  requests do not count — they never advertised."
  [store cid]
  (->> (st/-list store pins-coll)
       (keep (fn [id]
               (when-let [d (st/-get store pins-coll id)]
                 (when (and (= cid (:pin/cid d))
                            (= "pinned" (:pin/status d)))
                   id))))
       vec))

(defn- fire-advertise
  "Call injected `:advertise` if present. Never throws. Never rewrites
  `:cid`. Absence is not a pass dressed as success — it is simply not
  this library's transport."
  [ctx event]
  (let [f (:advertise ctx)]
    (when (ifn? f)
      (try
        (let [ret (f event)]
          (when (and (map? ret) (false? (:ok? ret)))
            (audit! (:store ctx) :advertise-rejected
                    (:requestid event) (:cid event)))
          ret)
        (catch #?(:clj Exception :cljs :default) e
          (audit! (:store ctx) :advertise-error
                  (:requestid event) (:cid event))
          {:ok? false
           :reason :advertise-error
           :detail #?(:clj (.getMessage e) :cljs (str e))})))))

(defn- pin->json
  "Pin doc → PinStatus JSON map (ipfs.github.io pinning-services-api-spec
  shape). `delegates` is always empty — this library has no peer identity to
  delegate to."
  [requestid {:pin/keys [cid name status created origins]}]
  (cond-> {"requestid" requestid
           "status" status
           "created" created
           "pin" (cond-> {"cid" cid}
                   name (assoc "name" name)
                   (seq origins) (assoc "origins" origins))
           "delegates" []}
    (= "failed" status)
    (assoc "info" {"reason" (str "cid not present in local block space; "
                                  "v0.1 has no pinning daemon to fetch it "
                                  "from origins")})))

(defn- create-pin [ctx now body]
  (let [store (:store ctx)
        {:strs [cid name origins]} body]
    (if-not (string? cid)
      (pin-error 400 "cid is required")
      (let [already (seq (pinned-request-ids store cid))
            requestid (gen-requestid store cid now)
            status (if (blocks/get-block ctx cid) "pinned" "failed")
            doc {:pin/cid cid
                 :pin/name name
                 :pin/status status
                 :pin/created now
                 :pin/origins (vec origins)}]
        (st/-put store pins-coll requestid doc)
        (audit! store :create-pin requestid cid)
        (when (and (= "pinned" status) (not already))
          (fire-advertise ctx {:cid cid
                               :op :advertise
                               :requestid requestid
                               :context-id requestid
                               :mutates-cid? false}))
        (json-response 202 (pin->json requestid doc))))))

(defn- get-pin [store requestid]
  (if-let [doc (st/-get store pins-coll requestid)]
    (json-response 200 (pin->json requestid doc))
    (pin-error 404 "pin request not found")))

(defn- list-pins [store req]
  (let [cid-filter (http/query-param req "cid")
        status-filter (http/query-param req "status")
        entries (->> (st/-list store pins-coll)
                    sort
                    (keep (fn [id]
                            (when-let [d (st/-get store pins-coll id)]
                              [id d])))
                    (filter (fn [[_ d]]
                              (or (nil? cid-filter) (= cid-filter (:pin/cid d)))))
                    (filter (fn [[_ d]]
                              (or (nil? status-filter)
                                  (= status-filter (:pin/status d))))))]
    (json-response 200 {"count" (count entries)
                        "results" (mapv (fn [[id d]] (pin->json id d)) entries)})))

(defn- delete-pin [ctx requestid]
  (let [store (:store ctx)]
    (if-let [doc (st/-get store pins-coll requestid)]
      (let [cid (:pin/cid doc)]
        (st/-put store pins-coll requestid nil)
        (audit! store :delete-pin requestid cid)
        (when (and (= "pinned" (:pin/status doc))
                   (empty? (pinned-request-ids store cid)))
          (fire-advertise ctx {:cid cid
                               :op :remove
                               :requestid requestid
                               :context-id requestid
                               :mutates-cid? false}))
        (http/response 202 {} nil))
      (pin-error 404 "pin request not found"))))

(defn- parse-body [req]
  (try (json/parse (or (:body req) "{}"))
       (catch #?(:clj Exception :cljs :default) _ nil)))

(defn handle
  "IPFS Pinning Service API handler. `ctx` is {:store IStore, :now optional
  ISO string, optional `:advertise` (fn [event]), and optionally the
  `:blocks`/`:cid-of` block plane kotobase.protocols.blocks documents}.
  Dispatches POST/GET /pins and GET/DELETE /pins/{requestid}."
  [{:keys [store now] :as ctx} req]
  (let [segs (http/segments (:path req))
        method (:method req)
        n (count segs)]
    (cond
      (not= "pins" (first segs))
      (http/not-found)

      (and (= 1 n) (= :post method))
      (let [body (parse-body req)]
        (if (nil? body)
          (pin-error 400 "malformed JSON body")
          (create-pin ctx now body)))

      (and (= 1 n) (= :get method))
      (list-pins store req)

      (and (= 2 n) (= :get method))
      (get-pin store (second segs))

      (and (= 2 n) (= :delete method))
      (delete-pin ctx (second segs))

      (or (= 1 n) (= 2 n))
      (http/method-not-allowed)

      :else (http/not-found))))
