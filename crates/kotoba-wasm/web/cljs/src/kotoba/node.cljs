(ns kotoba.node
  "Browser read-plane orchestrator (ClojureScript).

   The whole point of docs/ADR-browser-cid-query-vs-p2p.md: a browser queries a
   pinned graph with ZERO peer connection. Query is content-addressed, so the
   flow is just

     (verify signed head) → sync covering index roots → CID-verified block pull
       → traverse locally → Datalog

   No libp2p, no WebRTC. `node` is a wasm `KotobaNode` instance exposing
   missingBlockCids / ingestBlock / hydrateFromProlly / datomicQ. The CID-verified
   block sync + IndexedDB cache live in `kotoba.blocks`."
  (:require [kotoba.ipns :as ipns]
            [kotoba.blocks :as blocks]))

;; ── covering index roots ─────────────────────────────────────────────────────

(defn sync-index-roots
  "POST datomic.sync → JS response carrying `index_roots` ({eavt,aevt,…} → CID)
   and `ipns_sequence`. Returns Promise<response-object>."
  ([graph remote] (sync-index-roots graph remote js/fetch))
  ([graph remote fetch-fn]
   (-> (fetch-fn (str remote "/xrpc/com.etzhayyim.apps.kotoba.datomic.sync")
                 #js {:method  "POST"
                      :headers #js {"content-type" "application/json"}
                      :body    (js/JSON.stringify #js {:graph graph})})
       (.then (fn [^js r]
                (if (.-ok r)
                  (.json r)
                  (throw (js/Error. (str "datomic.sync → HTTP " (.-status r))))))))))

;; ── CID-verified block sync (delegates to kotoba.blocks: IndexedDB + block.get) ─

(defn hydrate!
  "Pull every block reachable from EAVT `root` (CID-verified, IndexedDB-cached)
   into `node`, then traverse it locally. Returns Promise<datom-count>.
   opts: :remote (REQUIRED) :fetch-fn :max-rounds (default 64)."
  [^js node root opts]
  (blocks/hydrate-via-blocks node root opts))

;; ── local Datalog ────────────────────────────────────────────────────────────

(defn query
  "Run a Datomic-style Datalog query entirely in-browser. `inputs` is a JS array
   (or nil). Returns the result JSON string from the wasm engine."
  [^js node query-edn inputs]
  (.datomicQ node query-edn (js/JSON.stringify (or inputs #js []))))

;; ── full round-trips ─────────────────────────────────────────────────────────

(defn- eavt-root [^js sync]
  (some-> (.-index_roots sync) (aget "eavt")))

(defn hydrate-and-query!
  "Works TODAY. Read-plane round-trip with no peer connection, head taken from
   `datomic.sync` (server-asserted index roots):

     datomic.sync → CID-verified block pull → local Datalog.

   opts: :remote (REQUIRED) :fetch-fn :max-rounds.
   Returns Promise<query-result-json>."
  [node graph query-edn inputs {:keys [remote fetch-fn] :as opts}]
  (-> (sync-index-roots graph remote (or fetch-fn js/fetch))
      (.then (fn [^js sync]
               (let [root (eavt-root sync)]
                 (when-not root
                   (throw (js/Error. "datomic.sync returned no eavt index root")))
                 (-> (hydrate! node root opts)
                     (.then (fn [_] (query node query-edn inputs)))))))))

(defn fetch-commit-roots
  "Fetch the verified head commit block by CID (block.get, CID-verified) and
   decode its covering ProllyTree index roots in-wasm. Returns Promise<#js{eavt,…}>.
   `node` must expose `commitIndexRoots` (which re-checks the CID before decoding)."
  [^js node head-cid remote fetch-fn]
  (-> (blocks/block-get remote head-cid fetch-fn)
      (.then (fn [bytes]
               (js/JSON.parse (.commitIndexRoots node head-cid bytes))))))

(defn hydrate-and-query-verified!
  "Fully trustless read-plane round-trip — NO server trust anywhere:

     verify signed head (ipns.head + KotobaNode.verifyIpnsRecord)
       -> head CID -> commit block (block.get, CID-verified)
       -> commitIndexRoots -> EAVT root (derived from the VERIFIED head, not datomic.sync)
       -> CID-verified block sync -> local Datalog.

   Every hop is signature- or CID-checked, so the serving node/gateway is
   untrusted end to end (closes ADR follow-up :wasm-commit-index-roots).

   opts: :node-class (REQUIRED) :remote (REQUIRED) :require-signature?
         :fetch-fn :max-rounds. Returns Promise<query-result-json>."
  [^js node graph query-edn inputs {:keys [remote fetch-fn] :as opts}]
  (let [fetch-fn (or fetch-fn js/fetch)]
    (-> (ipns/resolve-head graph opts)
        (.then (fn [^js head]
                 (let [head-cid (.-head head)]
                   (-> (fetch-commit-roots node head-cid remote fetch-fn)
                       (.then (fn [^js roots]
                                (let [root (aget roots "eavt")]
                                  (when-not root
                                    (throw (js/Error. "verified head commit has no eavt index root")))
                                  (-> (hydrate! node root opts)
                                      (.then (fn [_] (query node query-edn inputs))))))))))))))
