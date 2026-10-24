(ns fleet.kotobase-store
  "The fleet log on kotobase.net — the same append-only `:db-api` the lease /
  governor / agent code already speaks, but shared across MACHINES instead of
  living in one process (MemStore) or one filesystem (fleet.filestore).

  Auth is self-minted CACAO: the key IS the authority for the graph its own DID
  derives (`kotobase/db/<did>/<db-name>`), so a dispatcher needs no token from
  an operator and can reach nothing but its own fleet graph.

  Two live-edge facts this had to be built around, both found by running it
  (`kotobase.edge-cacao/validate-cacao` is the authority):
  - every CACAO must carry a `kotoba://can/kotobase:pin` capability, and each
    `kotoba://graph/<scope>` resource must name the ISSUER DID — a graph CID
    there is rejected with 'CACAO graph scope does not include issuer DID';
  - the edge records nonces to stop replay, so a CACAO is single-use. Each
    request therefore mints its own; a conn cannot be captured and reused.

  Residual limitation (documented, not hidden): `kotoba.fleet.kotoba-store`
  cannot make `:transact-with-t!` atomic over a remote backend — there is no
  compare-and-swap in the `:db-api` contract — so two dispatchers CAN compute
  the same ordinal. `confirmed-holder?` below is the mitigation: after
  claiming, re-read the log and check the deterministic winner is still you
  before doing any work. Ties break on `[:lease/t :lease/id]`, so every
  observer converges on the same holder even when ordinals collide."
  (:require ["node:child_process" :as cp]
            ["node:crypto" :as crypto]
            [kotoba.lang.text :as str]
            [cljs.reader :as edn]
            [cacao.core :as cacao]
            [kotoba.fleet.lease :as lease]
            [langchain.kotoba-db :as kdb]))

(def default-url "https://kotobase.net")
(def operator-did "did:web:kotobase.net")

;; ── graph identity ──────────────────────────────────────────────────────────

(def ^:private b32 "abcdefghijklmnopqrstuvwxyz234567")

(defn- base32-lower-no-pad
  "RFC4648 base32 (lowercase, unpadded) — the multibase 'b' body."
  [bs]
  (let [out (atom "") buf (atom 0) bits (atom 0)]
    (doseq [b bs]
      (reset! buf (bit-or (bit-shift-left @buf 8) b))
      (swap! bits + 8)
      (while (>= @bits 5)
        (swap! bits - 5)
        (swap! out str (nth b32 (bit-and (bit-shift-right @buf @bits) 31)))
        (reset! buf (bit-and @buf (dec (bit-shift-left 1 @bits))))))
    (when (pos? @bits)
      (swap! out str (nth b32 (bit-and (bit-shift-left @buf (- 5 @bits)) 31))))
    @out))

(defn canonical-graph
  "The graph CID the edge derives for one of this DID's databases:
  CIDv1(dag-cbor, sha2-256) over the name `kotobase/db/<did>/<db-name>`."
  [did db-name]
  (let [name (str "kotobase/db/" did "/" db-name)
        digest (js/Uint8Array. (-> (crypto/createHash "sha256") (.update name "utf8") (.digest)))
        bytes (js/Uint8Array. (clj->js (concat [0x01 0x71 0x12 0x20] (array-seq digest))))]
    (str "b" (base32-lower-no-pad (array-seq bytes)))))

;; ── CACAO (single-use, self-minted) ─────────────────────────────────────────

(defn- iso [ms] (str/replace (.toISOString (js/Date. ms)) #"\.\d{3}Z$" "Z"))

(defn- mint!
  "A fresh single-use CACAO for one request. `kotobase:pin` is mandatory at the
  edge; the graph scope must be the issuer DID."
  [{:keys [seed did]} capability ttl-sec]
  (let [now (js/Date.now)]
    (:cacao-b64 (cacao/mint {:seed seed
                             :aud operator-did
                             :domain "kotobase.net"
                             :nonce (str (random-uuid))
                             :iat (iso now)
                             :exp (iso (+ now (* 1000 ttl-sec)))
                             :resources [(str "kotoba://can/kotobase:pin")
                                         (str "kotoba://can/" capability)
                                         (str "kotoba://graph/" did)]}))))

;; ── host caps ───────────────────────────────────────────────────────────────

(defn- http-fn [{:keys [url method headers body]}]
  (let [hdr (mapcat (fn [[k v]] ["-H" (str k ": " v)]) headers)
        out (try (cp/execFileSync
                  "curl" (clj->js (concat ["-sS" "--max-time" "60" "-w" "\n%{http_code}"
                                           "-X" (str/upper (name method)) url]
                                          hdr ["--data-binary" body]))
                  #js {:encoding "utf8" :maxBuffer 33554432})
                 (catch :default e (str (.-message e) "\n599")))
        lines (str/split-lines out)]
    {:status (js/parseInt (last lines)) :body (str/join "\n" (butlast lines))}))

(def ^:private host-caps
  {:http-fn http-fn
   :json-write #(js/JSON.stringify (clj->js %))
   :json-read #(js->clj (js/JSON.parse %) :keywordize-keys true)})

;; ── store ───────────────────────────────────────────────────────────────────

(def ^:private blob-attr
  "One fleet datom = one backend entity with ONE attribute holding the whole
  `pr-str`'d [e a v t] tuple.

  `kotoba.fleet.kotoba-store` reifies each component as its own attribute
  (`:fd/e :fd/a :fd/v :fd/t`) and rejoins them with a four-clause query on the
  shared entity var. That is correct Datalog and it works in-process, but the
  live kotobase edge does NOT apply the join: a two-lease log came back as 240
  rows of recombined components (`:lease/agent` carrying a work id, and so on),
  i.e. a cross product. A single-attribute read has no join for a query engine
  to get wrong, and the fleet code only ever reads the whole log anyway."
  :fdb/blob)

(defn- read-log
  "The whole append-only log, in causal order.

  The XRPC client already `read-string`s wire cells that look like EDN
  (`langchain.kotoba-db/project-rows`), so a blob usually arrives as the tuple
  itself; decode only when it is still a string. Rows come back as a SET, so
  order is restored from the stored ordinal rather than assumed."
  [api conn]
  (->> ((:q api) [:find '?b :where ['?x blob-attr '?b]] conn)
       (map (fn [row] (let [b (first row)] (if (string? b) (edn/read-string b) b))))
       (sort-by (fn [[_ _ _ t]] t))
       vec))

(defn kotobase-store  "Fleet `:db-api` store backed by kotobase.net's tenant Datom plane.
  opts: {:identity {:seed :did} :db-name … :url … :ttl-sec …
         :graph (optional) — read another identity's fleet graph. Writes still
                go to the writer's own tenant graph (the edge derives it from
                db_name + the CACAO), so this is a READ-ONLY observer setting."
  [{:keys [identity db-name url ttl-sec graph] :or {url default-url ttl-sec 300}}]
  (let [graph (or graph (canonical-graph (:did identity) db-name))
        conn-for (fn [capability]
                   ;; a CACAO is single-use at the edge (nonce replay record),
                   ;; so every request mints its own
                   (kdb/kotoba-conn* url db-name
                                     {:graph graph
                                      :cacao (mint! identity capability ttl-sec)
                                      :did (:did identity)}))
        api (kdb/kotoba-api host-caps)
        append! (fn [datoms]
                  ((:transact! api) (conn-for "datom:transact")
                   (mapv (fn [d] {blob-attr (pr-str (vec d))}) datoms))
                  {:added (count datoms)})
        all (fn [] (read-log api (conn-for "datom:read")))]
    {:transact! append!

     ;; NOT atomic — the :db-api contract has no compare-and-swap, so two
     ;; dispatchers can read the same length before either appends. The
     ;; deterministic [t id] tiebreak means they still converge on ONE holder;
     ;; `confirmed-holder?` is how a caller finds out it was the loser before
     ;; doing any work.
     :transact-with-t!
     (fn [build-fn]
       (let [t (count (all))
             ds (vec (build-fn t))]
         (append! ds)
         {:t t :added (count ds)}))

     :datoms all
     :by (fn [a v] (filterv (fn [[_ da dv]] (and (= da a) (= dv v))) (all)))
     :entity (fn [e]
               (reduce (fn [m [de a v]] (if (= de e) (assoc m a v) m)) {:db/id e} (all)))
     :fleet/graph graph
     :fleet/did (:did identity)}))

(defn confirmed-holder?
  "Re-read the shared log after `settle-ms` and report whether `agent` is STILL
  the deterministic holder of `unit`.

  Required on any backend whose ordinal allocation is not atomic: two
  dispatchers can be told they won at claim time, but the log converges on one
  winner, so the loser must find out BEFORE it starts work rather than at
  materialize time."
  [db unit agent settle-ms]
  (let [end (+ (js/Date.now) settle-ms)]
    (while (< (js/Date.now) end) nil)
    (= agent (lease/holder db unit (js/Date.now)))))
