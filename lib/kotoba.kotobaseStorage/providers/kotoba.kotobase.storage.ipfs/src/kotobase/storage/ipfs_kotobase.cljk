(ns kotobase.storage.ipfs-kotobase
  "A concrete `kotobase.storage.ipfs` client backed by kotobase.net's own
  first-party archive: `PUT /ipfs/:cid` (`kotobase.archive-put`, in
  `net-kotobase/control-plane/kotobase-api-gateway-cljs`).

  ## Why this exists

  `kotobase.storage.ipfs/open` asks only for `{:put-block! :get-block}` —
  Promise-returning, cid-in/cid-out. It names no transport. This is the
  transport: kotobase.net's own raw-CID archive, over plain `fetch`.

  ## The identity/location split this bridges (root ADR-2608148200)

  `PUT /ipfs/:cid` accepts ONLY raw CIDv1(sha2-256) — `parse-raw-cid` in
  `kotobase.archive-put` rejects anything else with `:not-raw-sha256`. A
  UnixFS DAG (`unixfs.file/build`, `kotoba-lang/tech-ipfs-specs-unixfs`) is
  not uniformly raw: leaf blocks are (`bafkrei…`), but every dag-pb parent
  node above them is not (`bafybei…`).

  So for a block whose own identity CID is not raw, this client computes
  the RAW CID of the SAME BYTES (`multiformats.core/cidv1-raw`) — that is
  the archive Location — PUTs under the Location, and remembers
  `identity -> location` in `location-index` so `get-block` can still be
  asked for the identity CID it was given. `put-block!` still resolves to
  the identity CID, honouring the `IBlockStore` contract that
  `kotobase.storage.ipfs` enforces (`stored-cid` must equal the CID asked
  for) — the Location split is invisible above this namespace.

  A raw leaf's identity CID already IS its raw CID, so nothing is added to
  the index for it — `location-index` holds ONLY the dag-pb entries, and is
  therefore small: one entry per non-leaf node in the DAG, not one per
  block. For a single-tenant, single-process caller this in-memory index is
  enough; a caller spanning processes or wanting this durable should persist
  it as its own small catalog (root ADR-2608160100 already treats a pack
  catalog as a projection, not a premise — this index is the same shape,
  smaller)."
  (:require [multiformats.core :as mf]))

(defn- auth-headers [token content-type]
  (clj->js
   (cond-> {"authorization" (str "Bearer " token)}
     content-type (assoc "content-type" content-type))))

(defn open
  "`base-url` — kotobase.net origin, e.g. \"https://kotobase.net\" (no
  trailing slash). `token` — a `KOTOBASE_ARCHIVE_TOKEN` (or `_2`) value; see
  `kotobase.archive-put`'s Bearer gate. Never log or print it.

  Returns `{:put-block! :get-block}`, the `kotobase.storage.ipfs/open`
  client shape, plus `:location-index` (the identity->location map so far,
  for a caller that wants to persist it) and `:location-of` (a lookup
  function over that map, defaulting to identity when nothing was
  recorded)."
  [{:keys [base-url token]}]
  (let [location (atom {})]
    {:location-index location
     :location-of (fn [cid] (get @location cid cid))
     :put-block!
     (fn [cid bytes]
       (let [loc (mf/cidv1-raw bytes)]
         (when-not (= loc cid)
           (swap! location assoc cid loc))
         (-> (js/fetch (str base-url "/ipfs/" loc)
                       #js {:method "PUT"
                            :body bytes
                            :headers (auth-headers token "application/octet-stream")})
             (.then (fn [resp]
                      (if (.-ok resp)
                        cid
                        (-> (.text resp)
                            (.then
                             (fn [body]
                               (throw (ex-info "kotobase archive-put refused this block"
                                               {:type :kotobase.storage.ipfs-kotobase/put-refused
                                                :status (.-status resp)
                                                :cid cid :location loc :body body})))))))))))
     :get-block
     (fn [cid]
       (let [loc (get @location cid cid)]
         (-> (js/fetch (str base-url "/ipfs/" loc) #js {:method "GET"})
             (.then (fn [resp]
                      (cond
                        (= 200 (.-status resp)) (.arrayBuffer resp)
                        (= 404 (.-status resp)) nil
                        :else (throw (ex-info "kotobase archive-get failed"
                                              {:type :kotobase.storage.ipfs-kotobase/get-failed
                                               :status (.-status resp) :cid cid :location loc})))))
             (.then (fn [ab] (when ab (js/Uint8Array. ab)))))))}))
