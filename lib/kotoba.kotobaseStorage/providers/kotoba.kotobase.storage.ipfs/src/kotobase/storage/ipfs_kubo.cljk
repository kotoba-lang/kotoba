(ns kotobase.storage.ipfs-kubo
  "A concrete `kotobase.storage.ipfs` client backed by a real, independently
  operated Kubo (go-ipfs) node's HTTP RPC API + gateway — over
  `kotoba.lang.ipfs` (`kotoba-lang/io-ipfs`), which models the Kubo wire
  protocol as pure functions over an injected `IHttp` transport.

  ## Why this exists

  `kotobase.storage.ipfs/open` asks only for `{:put-block! :get-block}` —
  Promise-returning, cid-in/cid-out. It names no transport.
  `kotobase.storage.ipfs-kotobase` is the OTHER concrete client this library
  ships, and it deliberately talks back to kotobase.net's own archive — which
  makes it a cache-shaped round trip, not a distinct storage substrate. THIS
  namespace is the one that actually reaches outside a single operator's
  infrastructure: any Kubo-compatible RPC endpoint (a self-hosted node, a
  pinning provider's RPC-compatible gateway) that the deployer chooses and
  configures — `kotoba-lang/kotobase-storage-d1`'s `KOTOBASE_AUTHORITY=ipfs`
  wiring is the first caller (superproject ADR-2608281000 Decision 2:
  'ベースは分散型、中央集権は効率化のための cache').

  ## Identity vs. what Kubo actually stored it as

  `kotobase.storage.ipfs` gives blocks a caller-assigned identity CID (raw
  sha2-256, computed upstream) and requires `put-block!` to resolve to THAT
  cid regardless of what the transport did internally. Kubo, added to with
  `cid-version=1`, defaults `raw-leaves` to true for a single unchunked leaf,
  so for the small (<=256 KiB raw leaf) blocks this library expects, Kubo's
  own computed CID is normally textually identical to the identity CID. It is
  not guaranteed byte-for-byte across Kubo versions/config (multibase choice,
  chunker settings), so this client does not assume equality: like
  `ipfs-kotobase`, it keeps a small in-memory identity->location map for the
  rare block whose Kubo CID differs, and `put-block!` still always resolves
  to the identity CID it was given.

  No credential handling beyond an optional bearer token lives here — the
  API endpoint is assumed to be a private/authenticated RPC surface, the
  gateway a public read surface, matching Kubo's own default topology
  (RPC on :5001, gateway on :8080)."
  (:require [kotoba.lang.ipfs :as kubo]))

(defn- auth-headers [token]
  (cond-> {} (some? token) (assoc "authorization" (str "Bearer " token))))

(defn- resp->result [resp]
  (-> (.arrayBuffer resp)
      (.then (fn [buffer]
               {:status (.-status resp)
                :body (js/Uint8Array. buffer)}))))

(defrecord ^:private FetchHttp [headers]
  kubo/IHttp
  (-get [_ url]
    (-> (js/fetch url #js {:method "GET" :headers (clj->js headers)})
        (.then resp->result)))
  (-post [_ url]
    (-> (js/fetch url #js {:method "POST" :headers (clj->js headers)})
        (.then resp->result)))
  (-post-file [_ url content]
    (let [form (js/FormData.)
          part (if (instance? js/Uint8Array content)
                 (js/Blob. #js [content])
                 content)]
      (.append form "file" part)
      (-> (js/fetch url #js {:method "POST" :body form :headers (clj->js headers)})
          (.then resp->result)))))

(defn open
  "`api-url` — the Kubo node's RPC origin (e.g. \"https://ipfs-rpc.example
  \" fronting :5001), used for writes (`/api/v0/add`). `gateway-url` — the
  Kubo (or any-compatible) gateway origin used for reads (`/ipfs/<cid>`).
  `token` — optional bearer credential for the RPC origin; the gateway is
  read-only and unauthenticated, matching Kubo's own default topology.

  Both URLs are required and are NOT defaulted to a well-known public
  service: this library selects no daemon, and a deployment that wants a
  third-party pinning provider supplies that provider's origins here.

  `:http` is an injection seam for tests (anything satisfying `kubo/IHttp`);
  it defaults to a real `js/fetch`-backed transport and production callers
  never pass it.

  Returns the `kotobase.storage.ipfs/open` client shape
  (`{:put-block! :get-block}`), plus `:location-index` for a caller that
  wants to persist the rare identity->location entries across restarts."
  [{:keys [api-url gateway-url token http]}]
  (when-not (string? api-url)
    (throw (ex-info "kotobase.storage.ipfs-kubo requires :api-url"
                    {:type :kotobase.storage.ipfs-kubo/invalid-configuration
                     :missing :api-url})))
  (when-not (string? gateway-url)
    (throw (ex-info "kotobase.storage.ipfs-kubo requires :gateway-url"
                    {:type :kotobase.storage.ipfs-kubo/invalid-configuration
                     :missing :gateway-url})))
  (let [http (or http (->FetchHttp (auth-headers token)))
        location (atom {})]
    {:location-index location
     :location-of (fn [cid] (get @location cid cid))
     :put-block!
     (fn [cid bytes]
       (-> (kubo/pin-blob http api-url bytes)
           (.then (fn [{stored-cid :cid}]
                    (when-not (= stored-cid cid)
                      (swap! location assoc cid stored-cid))
                    cid))))
     :get-block
     (fn [cid]
       (let [loc (get @location cid cid)]
         (-> (kubo/-get http (kubo/gateway-url gateway-url loc))
             (.then (fn [{:keys [status body]}]
                      (cond
                        (= 200 status) body
                        (= 404 status) nil
                        :else
                        (throw (ex-info "kubo gateway fetch failed"
                                        {:type :kotobase.storage.ipfs-kubo/get-failed
                                         :status status
                                         :cid cid
                                         :location loc}))))))))}))
