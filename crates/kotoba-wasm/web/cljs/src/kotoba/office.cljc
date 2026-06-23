(ns kotoba.office
  "Organization-first office documents on the browser kotoba node.

   Two layers:
   - PURE (.cljc, runs under babashka + cljs): model <-> kotoba transact batch
     ([{e,a,v_edn}]), with v_edn encoded exactly as kotoba's parse_edn_scalar expects
     (kotoba-wasm/src/lib.rs). Org-first + W3C-DID + access-DAG schema (see
     docs/gftd-office/d-did-identity-layer.md).
   - CLJS-only (#?(:cljs)): drives the wasm KotobaNode (assert/transact/commit/datomicQ)
     + IndexedDB snapshot persistence. Wired into shadow-cljs.edn :exports.

   Entity ids here are caller-supplied LOGICAL ids; kotoba content-hashes `e` to a CID.
   :block/text is encrypted at write time via assertEncrypted (signal:v1:) in real use;
   this layer passes it as a plain value (encryption is a separate increment)."
  (:require [clojure.string :as str]
            #?(:clj [cheshire.core :as json])))

;; ===========================================================================
;; schema registry (value types drive v_edn encode/decode)
;; ===========================================================================

(def schema
  {;; org / account (account = org node)
   :org/did          {:db/valueType :did     :db/cardinality :one :db/unique :identity}
   :org/kind         {:db/valueType :keyword :db/cardinality :one}
   :org/display-name {:db/valueType :string  :db/cardinality :one}
   :org/parent       {:db/valueType :ref     :db/cardinality :one}  ; ownership tree = DID controller
   :org/data-graph   {:db/valueType :string  :db/cardinality :one}  ; DID service endpoint
   :org/created-at   {:db/valueType :long    :db/cardinality :one}
   ;; W3C DID verification method
   :vm/of                   {:db/valueType :ref     :db/cardinality :one}
   :vm/vid                  {:db/valueType :string  :db/cardinality :one :db/unique :identity}
   :vm/type                 {:db/valueType :keyword :db/cardinality :one}
   :vm/public-key-multibase {:db/valueType :string  :db/cardinality :one}
   :vm/rel                  {:db/valueType :keyword :db/cardinality :many}
   ;; membership grant (access DAG ~ CACAO)
   :grant/org        {:db/valueType :ref     :db/cardinality :one}
   :grant/subject    {:db/valueType :did     :db/cardinality :one}
   :grant/cap        {:db/valueType :keyword :db/cardinality :one}
   :grant/scope      {:db/valueType :string  :db/cardinality :one}
   :grant/role       {:db/valueType :keyword :db/cardinality :one}
   :grant/issued-at  {:db/valueType :long    :db/cardinality :one}
   :grant/expires-at {:db/valueType :long    :db/cardinality :one}
   ;; logical id (survives the server's content-addressing: the entity `e` becomes a
   ;; CID server-side, but :node/lid keeps the caller's stable id as a value, so
   ;; tree reconstruction (:block/parent references a parent's lid) works on read-back)
   :node/lid         {:db/valueType :string  :db/cardinality :one}
   ;; document
   :doc/kind         {:db/valueType :keyword :db/cardinality :one}
   :doc/title        {:db/valueType :string  :db/cardinality :one}
   :doc/owner-org    {:db/valueType :ref     :db/cardinality :one}
   :doc/created-at   {:db/valueType :long    :db/cardinality :one}
   ;; block (tree under doc)
   :block/kind    {:db/valueType :keyword :db/cardinality :one}
   :block/text    {:db/valueType :string  :db/cardinality :one :db/encrypted true}
   :block/order   {:db/valueType :string  :db/cardinality :one}
   :block/parent  {:db/valueType :ref     :db/cardinality :one}
   :block/deleted {:db/valueType :boolean :db/cardinality :one}})

(defn value-type [a] (get-in schema [a :db/valueType] :string))

;; ===========================================================================
;; v_edn codec — matches kotoba-wasm parse_edn_scalar exactly
;;   "\"s\""  -> JSON string  (string/ref/did)
;;   :kw      -> keyword (colon stripped on decode)
;;   123      -> bare literal (long)
;;   true     -> bare literal (boolean)
;; ===========================================================================

(defn- json-str [s]
  #?(:clj  (json/generate-string s)
     :cljs (js/JSON.stringify s)))

(defn- json-parse [s]
  #?(:clj  (json/parse-string s)
     :cljs (js/JSON.parse s)))

(defn encode-value
  "v -> v_edn string for a kotoba transact datom, per attribute value type."
  [a v]
  (case (value-type a)
    (:string :ref :did) (json-str (str v))
    :keyword            (str v)            ; keyword prints with leading ':'
    :long               (str v)
    :boolean            (str v)
    (json-str (str v))))

(defn parse-edn-scalar
  "Mirror of kotoba-wasm parse_edn_scalar: v_edn string -> decoded scalar string.
   (Real datomicQ already returns this decoded form; used here for round-trip tests.)"
  [s]
  (let [s (str/trim s)]
    (cond
      (str/starts-with? s "\"") (json-parse s)
      (str/starts-with? s ":")  (subs s 1)
      :else s)))

(defn decode-value
  "decoded-scalar-string (from kotoba) -> typed value, per attribute value type."
  [a s]
  (case (value-type a)
    (:string :ref :did) s
    :keyword            (keyword s)
    :long               #?(:clj (Long/parseLong s) :cljs (js/parseInt s 10))
    :boolean            (= "true" s)
    s))

;; ===========================================================================
;; model -> transact batch  ([{:e :a :v_edn}] as Clojure data)
;; ===========================================================================

(defn- d [e a v] {:e e :a (str a) :v_edn (encode-value a v)})

(defn- block->tx [parent-id {:keys [id kind text order children deleted]}]
  (into (cond-> [(d id :node/lid id)
                 (d id :block/kind kind)
                 (d id :block/parent parent-id)
                 (d id :block/order order)]
          (some? text)    (conj (d id :block/text text))
          (some? deleted) (conj (d id :block/deleted deleted)))
        (mapcat #(block->tx id %) children)))

(defn doc->tx [{:keys [id kind title owner-org created-at blocks]}]
  (into [(d id :node/lid id)
         (d id :doc/kind kind)
         (d id :doc/title title)
         (d id :doc/owner-org owner-org)
         (d id :doc/created-at created-at)]
        (mapcat #(block->tx id %) blocks)))

(defn org->tx [{:keys [id did kind display-name parent data-graph created-at vms]}]
  (into (cond-> [(d id :org/did did)
                 (d id :org/kind kind)
                 (d id :org/display-name display-name)
                 (d id :org/data-graph data-graph)
                 (d id :org/created-at created-at)]
          (some? parent) (conj (d id :org/parent parent)))
        (mapcat (fn [{:keys [vid type pk rels]}]
                  (into [(d vid :vm/of id)
                         (d vid :vm/vid vid)
                         (d vid :vm/type type)
                         (d vid :vm/public-key-multibase pk)]
                        (map #(d vid :vm/rel %) rels)))
                vms)))

(defn grant->tx [{:keys [id org subject cap scope role issued-at expires-at]}]
  (cond-> [(d id :grant/org org)
           (d id :grant/subject subject)
           (d id :grant/cap cap)
           (d id :grant/scope scope)
           (d id :grant/role role)
           (d id :grant/issued-at issued-at)]
    (some? expires-at) (conj (d id :grant/expires-at expires-at))))

(defn tx->json
  "Serialize a transact batch for KotobaNode.transact / loadDatoms (LOCAL write)."
  [tx]
  #?(:clj  (json/generate-string tx)
     :cljs (js/JSON.stringify (clj->js tx))))

;; ---- server sync form: tx_edn = [[:db/add e a v] ...] (datomic.transact) ----
;; The v_edn scalar already matches kotoba EDN exactly (string "x" / keyword :kw /
;; long 123 / bool true), so we reuse it verbatim as the [:db/add] value.

(defn- datom->add [{:keys [e a v_edn]}]
  (str "[:db/add " (json-str (str e)) " " a " " v_edn "]"))

(defn tx->edn
  "Render a transact batch ([{:e :a :v_edn}]) as kotoba `tx_edn`: a vector of
   [:db/add e a v] ops for the server datomic.transact endpoint."
  [tx]
  (str "[" (apply str (map datom->add tx)) "]"))

(defn- block-ids [{:keys [id children]}] (into [id] (mapcat block-ids children)))
(defn- doc-entity-ids [{:keys [id blocks]}] (into [id] (mapcat block-ids blocks)))

(defn doc->tx-edn
  "Datomic tx_edn for a doc. Prepends `[:db.fn/retractEntity id]` for the doc + every
   block so a RE-EDIT cleanly REPLACES prior values (office attrs are plain :db/add,
   so without this a re-saved :block/text would accumulate multiple values and a read
   could return a stale one). retractEntity on a not-yet-existing entity is a no-op."
  [model]
  (str "["
       (apply str (map (fn [eid] (str "[:db.fn/retractEntity " (json-str eid) "]"))
                       (doc-entity-ids model)))
       (apply str (map datom->add (doc->tx model)))
       "]"))

(defn org->tx-edn   [model] (tx->edn (org->tx model)))
(defn grant->tx-edn [model] (tx->edn (grant->tx model)))

;; ---- sovereign body encryption (pure tree transform; the actual crypto fn is
;;      injected so this stays platform-neutral / bb-testable) ----
(defn- map-block-text [f {:keys [text children] :as block}]
  (cond-> block
    (some? text)     (assoc :text (f text))
    (seq children)   (update :children #(mapv (partial map-block-text f) %))))

(defn map-doc-text
  "Return the doc with every block :text replaced by (f text). Used to encrypt
   (f = node.encrypt → signal:v1:) or decrypt (f = node.decrypt) bodies uniformly."
  [f {:keys [blocks] :as model}]
  (cond-> model
    (seq blocks) (assoc :blocks (mapv (partial map-block-text f) blocks))))

;; ===========================================================================
;; rows -> model   (rows = decoded [e a-str scalar-str] triples from datomicQ)
;; ===========================================================================

(defn- a->kw [a] (keyword (cond-> a (str/starts-with? a ":") (subs 1))))

(defn- v1 [rows e a]
  (some (fn [[re ra rv]] (when (and (= re e) (= (a->kw ra) a)) (decode-value a rv))) rows))

(defn- vN [rows e a]
  (set (keep (fn [[re ra rv]] (when (and (= re e) (= (a->kw ra) a)) (decode-value a rv))) rows)))

(defn rows->doc
  "Reconstruct the nested doc model from EAV rows. Identity is the logical id
   (:node/lid), NOT the entity `e` — so this works whether `e` is the caller's
   string id (local node) or a content-addressed CID (server read-back); parent
   links (:block/parent → a parent's lid) resolve in lid-space either way."
  [rows]
  (let [lid-of (fn [e] (v1 rows e :node/lid))
        doc-e  (some (fn [[e a]] (when (= (a->kw a) :doc/kind) e)) rows)
        children-of (fn children-of [parent-lid]
                      (->> rows
                           (keep (fn [[e a v]]
                                   (when (and (= (a->kw a) :block/parent)
                                              (= (decode-value :block/parent v) parent-lid)) e)))
                           distinct
                           (sort-by #(v1 rows % :block/order))
                           (mapv (fn [e]
                                   (let [lid  (lid-of e)
                                         kids (children-of lid)
                                         txt  (v1 rows e :block/text)
                                         del  (v1 rows e :block/deleted)]
                                     (cond-> {:id lid
                                              :kind  (v1 rows e :block/kind)
                                              :order (v1 rows e :block/order)}
                                       (some? txt) (assoc :text txt)
                                       (some? del) (assoc :deleted del)
                                       (seq kids)  (assoc :children kids)))))))]
    {:id         (lid-of doc-e)
     :kind       (v1 rows doc-e :doc/kind)
     :title      (v1 rows doc-e :doc/title)
     :owner-org  (v1 rows doc-e :doc/owner-org)
     :created-at (v1 rows doc-e :doc/created-at)
     :blocks     (children-of (lid-of doc-e))}))

(defn rows->org [rows org-id]
  (let [vm-ids (->> rows
                    (keep (fn [[e a v]]
                            (when (and (= (a->kw a) :vm/of)
                                       (= (decode-value :vm/of v) org-id)) e)))
                    distinct)
        vms (mapv (fn [vid] {:vid  vid
                             :type (v1 rows vid :vm/type)
                             :pk   (v1 rows vid :vm/public-key-multibase)
                             :rels (vN rows vid :vm/rel)})
                  vm-ids)]
    (cond-> {:id           org-id
             :did          (v1 rows org-id :org/did)
             :kind         (v1 rows org-id :org/kind)
             :display-name (v1 rows org-id :org/display-name)
             :data-graph   (v1 rows org-id :org/data-graph)
             :created-at   (v1 rows org-id :org/created-at)
             :vms          vms}
      (v1 rows org-id :org/parent) (assoc :parent (v1 rows org-id :org/parent)))))

(defn rows->grant [rows grant-id]
  (cond-> {:id        grant-id
           :org       (v1 rows grant-id :grant/org)
           :subject   (v1 rows grant-id :grant/subject)
           :cap       (v1 rows grant-id :grant/cap)
           :scope     (v1 rows grant-id :grant/scope)
           :role      (v1 rows grant-id :grant/role)
           :issued-at (v1 rows grant-id :grant/issued-at)}
    (v1 rows grant-id :grant/expires-at) (assoc :expires-at (v1 rows grant-id :grant/expires-at))))

;; ===========================================================================
;; CLJS-only: drive the wasm KotobaNode + IndexedDB persistence
;; ===========================================================================

#?(:cljs
   (do
     (defn- transact! [^js node tx]
       (.transact node (tx->json tx)))

     (defn- persist! [^js node]
       ;; mirror kotoba.write/kotoba-sw: snapshot -> IndexedDB (durable, offline)
       (js/Promise.resolve (.snapshot node)))

     ;; wasm-bindgen Option<String> wants `undefined`, not JS `null` (nil). And the
     ;; server requires a 20-char UTC `…SSZ` issued_at (no millis) + a fresh nonce.
     (defn- opt-str [v] (if (nil? v) js/undefined v))
     (defn- now-iso [] (str (.slice (.toISOString (js/Date.)) 0 19) "Z"))
     (defn- fresh-nonce []
       (let [a (js/Uint8Array. 16)]
         (js/crypto.getRandomValues a)
         (.join (js/Array.from a (fn [b] (str b "-"))) "")))

     (defn encrypt-doc
       "Return the doc with every block :text replaced by a signal:v1: envelope
        (node.encrypt) ONCE — so the same ciphertext is used for both the local store
        and the server sync. Structure (kind/order/parent/title) stays plaintext.
        Sovereign flow: (let [m (encrypt-doc node model)] (store-doc! node m)
        (sync-doc! node m {...}))."
       [^js node model]
       (map-doc-text (fn [t] (.encrypt node t)) model))

     (defn store-doc!
       "Write an office document into the node (LOCAL, sovereign) + commit + persist.
        Pass an encrypt-doc'd model to keep bodies as ciphertext.
        Returns Promise<#js{root snapshot}>. No network: pure local-first."
       [^js node model]
       (transact! node (doc->tx model))
       (let [root (.commit node)]
         (-> (persist! node)
             (.then (fn [snap] #js {:root root :snapshot snap})))))

     ;; ── aud (operator DID) discovery — public key.custodianInfo returns {did} ──
     (defn discover-operator-did
       "Fetch the node's operator DID (= CACAO aud) from the public key.custodianInfo
        endpoint, CACHED in localStorage so offline saves can still mint a CACAO.
        opts {:remote :fetch-fn}. Returns Promise<did>."
       [{:keys [remote fetch-fn]}]
       (let [cached (js/localStorage.getItem "kotoba.operator-did")]
         (if cached
           (js/Promise.resolve cached)
           (let [fetch-fn (or fetch-fn js/fetch)]
             (-> (fetch-fn (str remote "/xrpc/com.etzhayyim.apps.kotoba.key.custodianInfo"))
                 (.then (fn [^js r] (.json r)))
                 (.then (fn [^js j]
                          (let [d (.-did j)]
                            (js/localStorage.setItem "kotoba.operator-did" d)
                            d))))))))

     (defn- resolve-aud [{:keys [operator-did] :as opts}]
       (if operator-did (js/Promise.resolve operator-did) (discover-operator-did opts)))

     (defn prepare-sync-request
       "Build the SIGNED transact request for an (encrypted) doc → Promise<#js{url body}>,
        WITHOUT POSTing — so a Service Worker can deliver it later (offline/background)
        without re-signing (the SW cannot run WebAuthn). aud auto-discovered (cached)."
       [^js node enc {:keys [remote nonce issued-at expiry] :as opts}]
       (-> (resolve-aud opts)
           (.then (fn [aud]
                    (let [graph (.privateGraphId node)
                          cacao (.mintCacao node aud graph
                                            #js ["datom:transact" "tx:create"]
                                            (or nonce (fresh-nonce)) (or issued-at (now-iso))
                                            (opt-str expiry))]
                      #js {:url  (str remote "/xrpc/com.etzhayyim.apps.kotoba.datomic.transact")
                           :body (js/JSON.stringify
                                  #js {:graph graph :tx_edn (doc->tx-edn enc) :cacao_b64 cacao})})))))


     (defn- decrypt-row
       "Decrypt a signal:v1: value with the node identity; pass others through."
       [^js node v]
       (if (and (string? v) (str/starts-with? v "signal:v1:")) (.decrypt node v) v))

     (defn pull-doc
       "Read this account's office document back from the server's PRIVATE graph with
        a read CACAO (datom:read, scoped to the graph CID — require_datomic_read uses
        graph.to_multibase()). Reconstructs via :node/lid (server entity ids are CIDs)
        and decrypts signal:v1: bodies. aud is :operator-did or auto-discovered.
        opts: :remote (REQUIRED) :operator-did :nonce :issued-at :expiry :fetch-fn.
        Returns Promise<doc-model>."
       [^js node {:keys [remote nonce issued-at expiry fetch-fn] :as opts}]
       (-> (resolve-aud opts)
           (.then (fn [aud]
                    (let [fetch-fn (or fetch-fn js/fetch)
                          graph    (.privateGraphId node)
                          cacao    (.mintCacao node aud graph #js ["datom:read"]
                                               (or nonce (fresh-nonce)) (or issued-at (now-iso))
                                               (opt-str expiry))
                          body     (js/JSON.stringify
                                    #js {:graph graph :index "eavt"
                                         :components_edn #js [] :cacao_b64 cacao})]
                      (-> (fetch-fn (str remote "/xrpc/com.etzhayyim.apps.kotoba.datomic.datoms")
                                    #js {:method "POST"
                                         :headers #js {"content-type" "application/json"}
                                         :body body})
                          (.then (fn [^js r]
                                   (if (.-ok r)
                                     (.json r)
                                     (throw (js/Error. (str "datomic.datoms → HTTP " (.-status r)))))))
                          (.then (fn [^js resp]
                                   (rows->doc
                                    (mapv (fn [^js dt]
                                            [(.-e dt) (.-a dt)
                                             (decrypt-row node (parse-edn-scalar (.-v_edn dt)))])
                                          (.-datoms resp)))))))))))

     (defn store-org!  [^js node model] (transact! node (org->tx model))  (.commit node))
     (defn store-grant! [^js node model] (transact! node (grant->tx model)) (.commit node))

     (defn- all-rows
       "Fetch e/a/v triples from the local node. NOTE: P0 uses a broad scan;
        a scoped query (per doc subtree) is a follow-up optimisation."
       [^js node]
       (let [res (js/JSON.parse (.datomicQ node "[:find ?e ?a ?v :where [?e ?a ?v]]" "[]"))]
         (mapv (fn [^js row] [(aget row 0) (aget row 1) (aget row 2)]) res)))

     (defn load-doc
       "Read back an office document model from the LOCAL node, decrypting signal:v1:
        bodies."
       [^js node _doc-id]
       (rows->doc (mapv (fn [[e a v]] [e a (decrypt-row node v)]) (all-rows node))))

     (defn sync-doc!
       "Push an office document to the server's PRIVATE graph owned by this account,
        authenticated with a freshly-minted transact CACAO (doc b). Local-first: call
        after store-doc! (which already encrypted bodies — the signal:v1: envelopes
        sync as opaque values). The graph is the account's deterministic private-graph
        CID; the server auto-registers it Private{owner=account} on first write.
        aud is :operator-did or auto-discovered. opts: :remote (REQUIRED) :operator-did
        :nonce :issued-at :expiry :fetch-fn. Returns Promise<response-json>."
       [^js node model {:keys [remote nonce issued-at expiry fetch-fn] :as opts}]
       (-> (resolve-aud opts)
           (.then (fn [aud]
                    (let [fetch-fn (or fetch-fn js/fetch)
                          graph    (.privateGraphId node)
                          cacao    (.mintCacao node aud graph
                                               #js ["datom:transact" "tx:create"]
                                               (or nonce (fresh-nonce)) (or issued-at (now-iso))
                                               (opt-str expiry))
                          body     (js/JSON.stringify
                                    #js {:graph graph :tx_edn (doc->tx-edn model) :cacao_b64 cacao})]
                      (-> (fetch-fn (str remote "/xrpc/com.etzhayyim.apps.kotoba.datomic.transact")
                                    #js {:method "POST"
                                         :headers #js {"content-type" "application/json"}
                                         :body body})
                          (.then (fn [^js r]
                                   (if (.-ok r)
                                     (.json r)
                                     (throw (js/Error. (str "datomic.transact → HTTP " (.-status r)))))))))))))

     (defn sync-doc-delegated!
       "Team sharing: a MEMBER pushes a doc to an ORG's private graph via a depth-2
        delegation chain. The owner first mints a root grant
          (.mintCacao owner-node member-did org-graph #js[\"datom:transact\" \"tx:create\"] …)
        and hands `:root-grant` to the member. aud auto-resolved.
        opts: :remote (REQUIRED) :org-graph (REQUIRED) :root-grant (REQUIRED)
        :operator-did :nonce :issued-at :expiry :fetch-fn."
       [^js node model {:keys [remote org-graph root-grant nonce issued-at expiry fetch-fn] :as opts}]
       (-> (resolve-aud opts)
           (.then (fn [aud]
                    (let [fetch-fn (or fetch-fn js/fetch)
                          cacao    (.mintDelegated node root-grant aud org-graph
                                                   #js ["datom:transact" "tx:create"]
                                                   (or nonce (fresh-nonce)) (or issued-at (now-iso))
                                                   (opt-str expiry))
                          body     (js/JSON.stringify
                                    #js {:graph org-graph :tx_edn (doc->tx-edn model) :cacao_b64 cacao})]
                      (-> (fetch-fn (str remote "/xrpc/com.etzhayyim.apps.kotoba.datomic.transact")
                                    #js {:method "POST"
                                         :headers #js {"content-type" "application/json"}
                                         :body body})
                          (.then (fn [^js r]
                                   (if (.-ok r)
                                     (.json r)
                                     (throw (js/Error. (str "datomic.transact → HTTP " (.-status r)))))))))))))

     (defn office-roundtrip!
       "Full browser↔server round-trip exercising the REAL office cljs fns under
        :advanced: build a doc, encrypt bodies, store locally, sync to the account's
        private graph, pull it back, reconstruct + decrypt. JS-friendly (string in,
        JS object out) so a playwright-clj E2E can drive it. Returns
        Promise<#js{synced, title, text, match}>."
       [^js node remote]
       (let [model {:id "doc1" :kind :doc/document :title "Q3 戦略メモ"
                    :owner-org "self" :created-at 1719000005000
                    :blocks [{:id "b0" :kind :block/heading :text "概要" :order "a0"}
                             {:id "b1" :kind :block/paragraph :text "原材料費が上昇し…" :order "a1"
                              :children [{:id "b1a" :kind :block/paragraph :text "詳細" :order "a0"}]}]}
             enc (encrypt-doc node model)]
         (-> (store-doc! node enc)
             (.then (fn [_] (sync-doc! node enc {:remote remote})))
             (.then (fn [_] (pull-doc node {:remote remote})))
             (.then (fn [recovered]
                      (clj->js {:synced true
                                :title  (:title recovered)
                                :text   (get-in recovered [:blocks 1 :text])
                                :match  (= recovered model)}))))))

     ;; exports referenced from shadow-cljs.edn
     (def ^:export encryptDocument encrypt-doc)
     (def ^:export officeRoundtrip office-roundtrip!)
     (def ^:export storeDocument store-doc!)
     (def ^:export loadDocument  load-doc)
     (def ^:export syncDocument  sync-doc!)
     (def ^:export syncDocumentDelegated sync-doc-delegated!)
     (def ^:export pullDocument  pull-doc)
     (def ^:export discoverOperatorDid discover-operator-did)
     (def ^:export storeOrg      store-org!)
     (def ^:export storeGrant    store-grant!)))
