(ns engi.fake-kotobase
  "An in-memory, no-network double of the kotobase.net XRPC surface
  (`ai.gftd.apps.kotobase.datomic.{datoms,transact}`), injected via
  `kotobase.client/make-client`'s `:fetch-fn` seam — the SAME injection
  point `kotobase-client`'s own test suite uses
  (`kotobase.client-request-test/capturing-fetch` et al) and
  `yoro-ui.studio.genko-store`'s docstring calls out as the reason every fn
  here takes the client map explicitly. This is what makes
  `engi.protocol-test` exercise the REAL `engi.store`/`engi.crypto`/
  `engi.protocol` code paths end to end, with only the HTTP transport
  swapped for an in-memory map — not a separate, parallel mock of
  `engi.protocol`'s own logic.

  Does not verify CACAO (kotobase-client's own test suite already pins that
  wire shape) — it stores/returns datoms exactly like the real server does,
  keyed by graph CID, and parses `tx_edn` well enough for the fixed shape
  `engi.store/entity->tx-edn` produces (one flat entity map, every value
  token whitespace-free — did:key/CID/base64url/base64 alphabets and plain
  numbers never contain a space, so a single `str/split` on
  whitespace is a faithful, exact tokenizer here — no general EDN reader
  needed)."
  (:require [kotoba.lang.text :as str]
            [kotobase.cid :as cid]))

(defn- strip-brackets
  "\"[{...}]\" -> \"...\"."
  [^string s]
  (let [s (str/trim s)]
    (subs s 2 (- (count s) 2))))

(defn- parse-tx-edn->datoms
  "The tx_edn `entity->tx-edn` produces is `[{:kw1 val1 :kw2 val2 ...}]`,
  ONE entity, every val a single whitespace-free token (a bare number/bool/
  nil literal, or a JSON-quoted string whose content is always an alphabet
  with no spaces — did:key, base32 CID, base64url sig, uuid-suffixed id).
  So splitting on whitespace after stripping the outer `[{`/`}]` recovers
  exactly the k/v token pairs — passed straight through as `v_edn` (the real
  server also stores whatever EDN-string-literal token it was given,
  verbatim; `kotobase.client/decode-edn-scalar` on the READ side is what
  actually interprets it)."
  [^string tx-edn]
  (let [tokens (-> tx-edn strip-brackets (str/split #"\s+"))
        pairs (vec (partition 2 tokens))
        eid-raw (some (fn [[k v]] (when (= k ":db/id") v)) pairs)
        eid (js/JSON.parse eid-raw)]
    (->> pairs
         (remove (fn [[k _]] (= k ":db/id")))
         (map (fn [[k v]] {:e eid :a k :v_edn v :added true})))))

(defn- ok-response [body-map]
  #js {:ok true :status 200
       :text (fn [] (js/Promise.resolve (js/JSON.stringify (clj->js body-map))))})

(defn- not-found-response []
  #js {:ok false :status 404
       :text (fn [] (js/Promise.resolve "not found"))})

(defn- handle-datoms [graphs body]
  ;; `datoms`' body already carries the fully-computed `:graph` (the client
  ;; derives it locally from its OWN :did — see kotobase.client/datoms).
  (ok-response {:ok true :datoms (get @graphs (:graph body) [])}))

(defn- handle-transact [graphs ^js opts body]
  ;; `transact`'s body carries ONLY `:db_name`/`:tx_edn` — the real edge
  ;; derives the WRITE graph server-side from the CACAO issuer + db_name (so
  ;; a caller can never write anyone else's graph). This fake has no CACAO
  ;; verification, but still derives the graph the same way — from the
  ;; `x-kotoba-did` header `kotobase.client/post` always sets alongside a
  ;; CACAO — so a real bug in engi.store's graph-vs-write mismatch would
  ;; surface here exactly as it would against the real server.
  (let [did (aget (.-headers opts) "x-kotoba-did")
        graph (cid/canonical-graph did (:db_name body))
        entity-datoms (parse-tx-edn->datoms (:tx_edn body))]
    (swap! graphs update graph (fnil into []) entity-datoms)
    (ok-response {:ok true})))

(defn- handle-request [graphs ^string url ^js opts]
  (let [method (last (str/split url #"\."))
        body (js->clj (js/JSON.parse (.-body opts)) :keywordize-keys true)]
    (case method
      "datoms" (handle-datoms graphs body)
      "transact" (handle-transact graphs opts body)
      (not-found-response))))

(defn make-fake-kotobase
  "→ {:graphs (atom {graph-cid [datom ...]}) :fetch-fn (fn [url opts])} —
  pass `:fetch-fn` straight into `kotobase.client/make-client`."
  []
  (let [graphs (atom {})]
    {:graphs graphs
     :fetch-fn (fn [url opts] (js/Promise.resolve (handle-request graphs url opts)))}))
