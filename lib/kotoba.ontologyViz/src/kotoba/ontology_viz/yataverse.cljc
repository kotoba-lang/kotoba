(ns kotoba.ontology-viz.yataverse
  "Explicit bidirectional wire adapter between Kotoba's canonical
  `ontology.graph/v1` model and Yataverse PR #83's `yataverse.ontology.graph/v1`
  schema (`schema`, numeric `version`, `basisCid`, `nodeCount`, `meta`,
  `layers[].nodeCount`, `nodes[].meta`, `edges[].from/to/meta`, `joins[]`,
  `coverage`, `truncated`, `edgesTruncated`, `graphCid`).

  Array-order and CID invariants:
  - Preserves exact input sequence order of `nodes`, `edges`, `layers`, and
    `joins` on lossless ingress (`<-yataverse-graph`) and egress
    (`->yataverse-graph`).
  - Verifies any declared `graphCid` on ingress against freshly computed
    canonical DAG-CBOR + SHA-256 CIDv1 (`0x01 0x71 0x12 0x20`), failing closed
    with `:graph-cid-mismatch` if even array order differs.
  - Always recomputes `graphCid` from the emitted canonical DAG-CBOR bytes on
    `->yataverse-graph` — never copies a stale `graphCid` onto a modified graph."
  (:require [clojure.string :as str]
            [kotoba.ontology-viz.dag-cbor :as dcbor]
            [kotoba.ontology-viz.escape :as esc]
            [kotoba.ontology-viz.graph :as g]
            [kotoba.ontology-viz.validate :as v]))

(def yataverse-graph-schema "yataverse.ontology.graph/v1")
(def yataverse-operations-schema "yataverse.ontology.operations/v1")

(defn- mget
  "Read field `k` (keyword) from map `m` whether `m` uses keyword or string keys."
  [m k]
  (when (map? m)
    (if (contains? m k)
      (get m k)
      (get m (if (namespace k) (str (namespace k) "/" (name k)) (name k))))))

(defn yataverse-graph?
  "True when `x` declares Yataverse PR #83's `yataverse.ontology.graph/v1` schema."
  [x]
  (and (map? x) (= yataverse-graph-schema (mget x :schema))))

(def ^:private yv-kind->kotoba-kind
  {"connector"   :connector
   "object-type" :object-type
   "fact"        :entity
   "attribute"   :attribute
   "rdf-subject" :rdf-resource
   "rdf-blank"   :rdf-blank
   "ipld-node"   :ipld-node})

(def ^:private kotoba-kind->yv-kind
  {:connector    "connector"
   :object-type  "object-type"
   :entity       "fact"
   :attribute    "attribute"
   :rdf-resource "rdf-subject"
   :rdf-blank    "rdf-subject"
   :ipld-node    "ipld-node"})

(def ^:private yv-layer->kotoba-layer
  {"connector"   "connector"
   "object-type" "ontology"
   "fact"        "instance"
   "attribute"   "attribute"
   "rdf-subject" "rdf"
   "ipld"        "ipld"})

(def ^:private kotoba-layer->yv-layer
  {"connector" "connector"
   "ontology"  "object-type"
   "instance"  "fact"
   "attribute" "attribute"
   "rdf"       "rdf-subject"
   "ipld"      "ipld"})

(def ^:private yv-edge-kind->kotoba-edge-kind
  {"provenance"    :provenance
   "produces"      :produces
   "instance"      :instance-of
   "instance-of"   :instance-of
   "join"          :join
   "join-instance" :join-instance
   "has-attribute" :has-attribute
   "datom-ref"     :datom-ref
   "rdf-predicate" :rdf-predicate
   "ipld-link"     :ipld-link})

(def ^:private kotoba-edge-kind->yv-edge-kind
  {:produces      "provenance"
   :provenance    "provenance"
   :instance-of   "instance"
   :join          "join"
   :join-instance "join-instance"
   :has-attribute "has-attribute"
   :datom-ref     "datom-ref"
   :rdf-predicate "rdf-predicate"
   :ipld-link     "ipld-link"})

(defn- stringify-map-keys [m]
  (into {}
        (map (fn [[k val]]
               [(cond
                  (keyword? k) (if (namespace k) (str (namespace k) "/" (name k)) (name k))
                  (string? k) k
                  :else (str k))
                val]))
        (or m {})))

(defn <-yataverse-graph
  "Strictly validate and convert a Yataverse PR #83 `yataverse.ontology.graph/v1`
  payload (keyword- or string-keyed) into a validated, laid-out Kotoba
  `ontology.graph/v1` graph while preserving exact input order of `nodes`,
  `edges`, `layers`, and `joins`.

  If `graphCid` is present on `yv`, computes the canonical DAG-CBOR SHA-256
  CIDv1 over `yv` (excluding `graphCid`) and fails closed with
  `:graph-cid-mismatch` if it does not match byte-for-byte."
  ([yv] (<-yataverse-graph yv {}))
  ([yv {:keys [limits layout]}]
   (when-not (map? yv)
     (v/fail! :invalid-yataverse-graph "Yataverse graph must be a map" {:type (str (type yv))}))
   (let [schema (mget yv :schema)
         version (mget yv :version)
         basis-cid (mget yv :basisCid)
         graph-cid (mget yv :graphCid)
         declared-node-count (mget yv :nodeCount)
         raw-meta (mget yv :meta)
         resolved-limits (v/resolve-limits limits)]
     (when-not (= yataverse-graph-schema schema)
       (v/fail! :invalid-yataverse-graph
                (str "expected schema " yataverse-graph-schema ", got: " (pr-str schema))
                {:schema schema}))
     (when-not (= 1 version)
       (v/fail! :invalid-yataverse-graph
                (str "expected numeric version 1, got: " (pr-str version))
                {:version version}))
     (when (some? basis-cid)
       (v/extract-cid basis-cid))
     (when (some? graph-cid)
       (v/extract-cid graph-cid))
     (when (and (some? declared-node-count)
                (not (and (integer? declared-node-count) (not (neg? declared-node-count)))))
       (v/fail! :invalid-yataverse-graph
                (str "nodeCount must be a non-negative integer, got: " (pr-str declared-node-count))
                {:nodeCount declared-node-count}))
     (when (and (some? raw-meta) (not (map? raw-meta)))
       (v/fail! :invalid-yataverse-graph "top-level meta must be a map" {:meta raw-meta}))
     (v/assert-bounded-and-no-remote-context! resolved-limits yv)
     (v/assert-no-forbidden-wire-keys! resolved-limits yv)
     (let [raw-nodes (or (mget yv :nodes) [])
           raw-edges (or (mget yv :edges) [])
           raw-joins (or (mget yv :joins) [])
           raw-layers (mget yv :layers)]
       (when-not (and (sequential? raw-nodes) (sequential? raw-edges) (sequential? raw-joins))
         (v/fail! :invalid-yataverse-graph "nodes, edges, and joins must be sequential" {}))
       (when (and (some? raw-layers) (not (sequential? raw-layers)))
         (v/fail! :invalid-yataverse-graph "layers must be sequential" {}))
       (v/bounded-count-or-fail! raw-nodes (:max-nodes resolved-limits) :max-nodes-exceeded :nodes)
       (when (and (some? declared-node-count) (not= declared-node-count (count raw-nodes)))
         (v/fail! :invalid-yataverse-graph
                  (str "declared nodeCount (" declared-node-count ") does not match nodes length (" (count raw-nodes) ")")
                  {:nodeCount declared-node-count :actual (count raw-nodes)}))
       (v/bounded-count-or-fail! raw-edges (:max-edges resolved-limits) :max-edges-exceeded :edges)
       (v/bounded-count-or-fail! raw-joins (:max-joins resolved-limits) :max-joins-exceeded :joins)

       ;; Fail-closed cryptographic verification of declared graphCid against exact input bytes & order
       (when (some? graph-cid)
         (let [{computed-cid :cid} (dcbor/encode-ontology-graph-dag-cbor yv)]
           (when-not (= graph-cid computed-cid)
             (v/fail! :graph-cid-mismatch
                      (str "declared graphCid (" graph-cid ") does not match canonical DAG-CBOR CID (" computed-cid ")")
                      {:declared graph-cid :computed computed-cid}))))

       ;; Preserve EXACT input array order for nodes, edges, joins, and layers
       (let [nodes
             (mapv
              (fn [n]
                (let [nid (mget n :id)
                      lbl (or (mget n :label) nid)
                      yv-kind (str (or (mget n :kind) (mget n :layer) "object-type"))
                      yv-layer (str (or (mget n :layer) yv-kind))
                      k-kind (get yv-kind->kotoba-kind yv-kind)
                      k-layer (get yv-layer->kotoba-layer yv-layer yv-layer)
                      meta-map (stringify-map-keys (mget n :meta))
                      node-cid (when-let [c (or (get meta-map "cid") (mget n :cid))]
                                 (v/extract-cid c))
                      keys-vec (when-let [ks (get meta-map "key")]
                                 (if (sequential? ks) (mapv str ks) [(str ks)]))
                      prov (cond-> {}
                             (get meta-map "ontology/type") (assoc :type (str (get meta-map "ontology/type")))
                             (get meta-map "ontology/source") (assoc :source (str (get meta-map "ontology/source")))
                             (get meta-map "ontology/fetched-at") (assoc :fetched-at (str (get meta-map "ontology/fetched-at")))
                             (contains? meta-map "ontology/confidence") (assoc :confidence (get meta-map "ontology/confidence"))
                             (get meta-map "status") (assoc :status (str (get meta-map "status")))
                             (v/safe-display-https-url (get meta-map "repo"))
                             (assoc :repo (v/safe-display-https-url (get meta-map "repo"))))
                      attrs (into {}
                                  (keep (fn [[k val]]
                                          (when (and (some? val) (not= k "repo"))
                                            [k (if (sequential? val) (str/join ", " (map str val)) (str val))])))
                                  meta-map)]
                  (when-not (and (string? nid) (not (str/blank? nid)))
                    (v/fail! :invalid-yataverse-graph "node missing string id" {:node n}))
                  (when-not k-kind
                    (v/fail! :invalid-yataverse-graph
                             (str "unsupported Yataverse node kind: " yv-kind)
                             {:node-id nid :kind yv-kind}))
                  (v/assert-label-length! resolved-limits :node/id nid)
                  (v/assert-label-length! resolved-limits :node/label lbl)
                  (v/assert-attributes-count! resolved-limits nid (count attrs))
                  (cond-> {:id nid
                           :label (str lbl)
                           :kind k-kind
                           :layer k-layer
                           :attributes attrs
                           :meta meta-map}
                    node-cid (assoc :cid node-cid)
                    (seq keys-vec) (assoc :keys keys-vec)
                    (seq prov) (assoc :provenance prov))))
              raw-nodes)
             edges
             (mapv
              (fn [e]
                (let [eid (mget e :id)
                      from (mget e :from)
                      to (mget e :to)
                      lbl (str (or (mget e :label) ""))
                      yv-ekind (str (or (mget e :kind) "provenance"))
                      k-ekind (get yv-edge-kind->kotoba-edge-kind yv-ekind)
                      emeta (stringify-map-keys (mget e :meta))]
                  (when-not (and (string? eid) (string? from) (string? to))
                    (v/fail! :invalid-yataverse-graph "edge requires string id, from, to" {:edge e}))
                  (when-not k-ekind
                    (v/fail! :invalid-yataverse-graph
                             (str "unsupported Yataverse edge kind: " yv-ekind)
                             {:edge-id eid :kind yv-ekind}))
                  (v/assert-label-length! resolved-limits :edge/id eid)
                  (v/assert-label-length! resolved-limits :edge/label lbl)
                  {:id eid
                   :source from
                   :target to
                   :label lbl
                   :kind k-ekind
                   :layer (if (#{:join :join-instance} k-ekind) "ontology" "connector")
                   :metadata emeta}))
              raw-edges)
             joins
             (mapv
              (fn [j]
                (let [jname (str (or (mget j :name) "join"))
                      ltype (str (or (mget j :leftType) ""))
                      rtype (str (or (mget j :rightType) ""))
                      lkey (str (or (mget j :leftKey) ""))
                      rkey (str (or (mget j :rightKey) ""))
                      lcnt (or (mget j :leftCount) 0)
                      rcnt (or (mget j :rightCount) 0)
                      mleft (or (mget j :matchedLeft) 0)
                      mrows (or (mget j :matchedRows) 0)
                      ratio (mget j :coverageRatio)
                      unmatched (max 0 (- lcnt mleft))
                      cov (when (some? ratio) (double ratio))
                      status (cond
                               (zero? lcnt) :schema-only
                               (= mleft lcnt) :full
                               (pos? mleft) :partial
                               :else :unmatched)]
                  {:id jname
                   :name jname
                   :from-node (str "type:" ltype)
                   :from-type ltype
                   :from-attr (if (str/blank? ltype) lkey (str ltype "." lkey))
                   :to-node (str "type:" rtype)
                   :to-type rtype
                   :to-attr (if (str/blank? rtype) rkey (str rtype "." rkey))
                   :left-key lkey
                   :right-key rkey
                   :join-kind (str (or (mget j :kind) "inner"))
                   :match-rule :exact
                   :cardinality :many-to-one
                   :exclude []
                   :matched-count mleft
                   :matched-rows mrows
                   :unmatched-count unmatched
                   :excluded-count 0
                   :total-source-count lcnt
                   :right-count rcnt
                   :eligible-count lcnt
                   :coverage cov
                   :status status
                   :matched-pairs []
                   :unmatched-values []
                   :excluded-values []}))
              raw-joins)
             preserved-yv-layers (when (seq raw-layers)
                                   (mapv (fn [l]
                                           {:id (str (mget l :id))
                                            :label (str (or (mget l :label) (mget l :id)))
                                            :order (or (mget l :order) 0)
                                            :nodeCount (or (mget l :nodeCount) 0)})
                                         raw-layers))
             layers (g/build-layers nodes)
             ;; Include any zero-count layers declared in preserved-yv-layers so
             ;; KotobaSpec v1.0 empty standard layers never fail undeclared-layer checks
             layers-with-preserved
             (if (seq preserved-yv-layers)
               (let [existing-ids (set (map :id layers))
                     extra (keep (fn [{:keys [id label order]}]
                                   (let [k-lid (get yv-layer->kotoba-layer id id)]
                                     (when-not (contains? existing-ids k-lid)
                                       (assoc (get g/default-layer-specs k-lid
                                                   {:id k-lid :label label :color "#475569" :bg "#f8fafc"})
                                              :order order
                                              :node-count 0))))
                                 preserved-yv-layers)]
                 (vec (sort-by :order (concat layers extra))))
               layers)
             cids (vec (sort (distinct (keep identity (concat (when basis-cid [basis-cid])
                                                              (when graph-cid [graph-cid])
                                                              (map :cid nodes))))))
             snap-schema (some-> raw-meta (mget :snapshotSchema) str)
             edges-trunc (cond
                           (contains? yv :edgesTruncated) (boolean (mget yv :edgesTruncated))
                           (contains? yv "edgesTruncated") (boolean (mget yv :edgesTruncated))
                           (and raw-meta (or (contains? raw-meta :edgesTruncated)
                                             (contains? raw-meta "edgesTruncated")))
                           (boolean (mget raw-meta :edgesTruncated))
                           :else false)
             basis (cond-> {:schema-version g/schema-version
                            :codec "dag-cbor"
                            :hash-alg "sha2-256"
                            ;; KotobaSpec v1.0.1 two-axis verification separation:
                            ;; graphCid verification NEVER promotes snapshot basisCid to :verified.
                            :cid-verification :syntax-only
                            :basis-cid-verification :syntax-only
                            :graph-cid-verification (if (some? graph-cid) :verified :absent)
                            :node-count (count nodes)
                            :edge-count (count edges)
                            :layer-count (count layers-with-preserved)
                            :join-count (count joins)
                            :cids cids
                            :bounds resolved-limits
                            :edges-truncated edges-trunc}
                     basis-cid (assoc :root-cid basis-cid)
                     graph-cid (assoc :graph-cid graph-cid)
                     preserved-yv-layers (assoc :yataverse-layers preserved-yv-layers)
                     snap-schema (assoc :snapshot-schema snap-schema)
                     (mget yv :id) (assoc :id (str (mget yv :id)))
                     (mget yv :stats) (assoc :stats (stringify-map-keys (mget yv :stats)))
                     (mget yv :coverage) (assoc :coverage (stringify-map-keys (mget yv :coverage)))
                     (contains? yv :truncated) (assoc :truncated (boolean (mget yv :truncated)))
                     (contains? yv "truncated") (assoc :truncated (boolean (mget yv :truncated))))
             graph {:schema/version g/schema-version
                    :schema/kind g/schema-kind
                    :basis basis
                    :layers layers-with-preserved
                    :nodes nodes
                    :edges edges
                    :joins joins}]
         (g/layout-graph graph (or layout {})))))))

(defn ->yataverse-graph
  "Validate and convert a Kotoba `ontology.graph/v1` graph into Yataverse PR #83's
  exact `yataverse.ontology.graph/v1` wire format.

  Preserves exact `nodes`/`edges`/`joins`/`layers` order and ALWAYS freshly
  computes `:graphCid` from the emitted canonical DAG-CBOR bytes (never
  inheriting a potentially stale `graphCid` from input metadata)."
  [graph]
  (v/validate-graph! graph)
  (let [basis (:basis graph)
        nodes (:nodes graph)
        edges (:edges graph)
        joins (:joins graph)
        yv-nodes
        (mapv
         (fn [n]
           (let [yv-kind (get kotoba-kind->yv-kind (:kind n) (name (or (:kind n) :object-type)))
                 yv-layer (get kotoba-layer->yv-layer (:layer n) (:layer n))
                 meta-map (or (:meta n)
                              (cond-> (stringify-map-keys (:attributes n))
                                (:cid n) (assoc "cid" (:cid n))
                                (seq (:keys n)) (assoc "key" (vec (:keys n)))
                                (get-in n [:provenance :source])
                                (assoc "ontology/source" (str (get-in n [:provenance :source])))
                                (get-in n [:provenance :type])
                                (assoc "ontology/type" (str (get-in n [:provenance :type])))
                                (get-in n [:provenance :fetched-at])
                                (assoc "ontology/fetched-at" (str (get-in n [:provenance :fetched-at])))
                                (contains? (:provenance n) :confidence)
                                (assoc "ontology/confidence" (get-in n [:provenance :confidence]))
                                (get-in n [:provenance :repo])
                                (assoc "repo" (get-in n [:provenance :repo]))))]
             {:id (:id n)
              :label (:label n)
              :kind yv-kind
              :layer yv-layer
              :meta meta-map}))
         nodes)
        ;; On newly projected Kotoba native graphs (no preserved :yataverse-layers),
        ;; sort edges by Yataverse generator phase order (produces -> join ->
        ;; fact instance/source -> join-instance -> other Kotoba edges) and assign
        ;; sequential numeric IDs e1..eN per KotobaSpec v1.0.1.
        native-phase-key (fn [e]
                           (let [k (:kind e)
                                 phase (case k
                                         :produces 0
                                         :join 1
                                         :instance-of 2
                                         :provenance 2
                                         :join-instance 3
                                         4)
                                 sub-phase (case k
                                             :instance-of 0
                                             :provenance 1
                                             0)]
                             [phase
                              (if (#{1 3} phase) (:label e) (:source e))
                              sub-phase
                              (:source e)
                              (:target e)
                              (:label e)
                              (:id e)]))
        yv-edges
        (if (:yataverse-layers basis)
          (mapv
           (fn [e]
             {:id (:id e)
              :from (:source e)
              :to (:target e)
              :label (or (:label e) "")
              :kind (get kotoba-edge-kind->yv-edge-kind (:kind e) (name (or (:kind e) :provenance)))
              :meta (stringify-map-keys (:metadata e))})
           edges)
          (vec
           (map-indexed
            (fn [idx e]
              {:id (str "e" (inc idx))
               :from (:source e)
               :to (:target e)
               :label (or (:label e) "")
               :kind (get kotoba-edge-kind->yv-edge-kind (:kind e) (name (or (:kind e) :provenance)))
               :meta (stringify-map-keys (:metadata e))})
            (sort-by native-phase-key edges))))
        yv-joins
        (mapv
         (fn [j]
           (let [ltype (or (:from-type j)
                           (when (str/starts-with? (str (:from-node j)) "type:")
                             (subs (:from-node j) 5))
                           (:from-node j))
                 rtype (or (:to-type j)
                           (when (str/starts-with? (str (:to-node j)) "type:")
                             (subs (:to-node j) 5))
                           (:to-node j))
                 lkey (or (:left-key j) (:from-attr j))
                 rkey (or (:right-key j) (:to-attr j))
                 mrows (or (:matched-rows j) (:matched-count j) 0)
                 ratio (if (some? (:coverage j))
                         (let [scaled (esc/round-int (* (double (:coverage j)) 1000.0))]
                           (if (zero? (rem scaled 1000))
                             (quot scaled 1000)
                             (/ scaled 1000.0)))
                         0)]
             {:name (or (:name j) (:id j))
              :leftType (str ltype)
              :rightType (str rtype)
              :leftKey (str lkey)
              :rightKey (str rkey)
              :kind (or (:join-kind j) "inner")
              :leftCount (or (:total-source-count j) 0)
              :rightCount (or (:right-count j) 0)
              :matchedLeft (or (:matched-count j) 0)
              :matchedRows mrows
              :coverageRatio ratio}))
         joins)
        layer-counts (frequencies (map :layer yv-nodes))
        ;; KotobaSpec v1.0: ALWAYS preserve standard 3 layers (connector, object-type, fact)
        ;; even when nodeCount is 0.
        yv-layers
        (if-let [preserved (:yataverse-layers basis)]
          (mapv (fn [l] (assoc l :nodeCount (get layer-counts (:id l) 0))) preserved)
          (let [standard-layers [["connector" "Connectors"]
                                 ["object-type" "Object Types"]
                                 ["fact" "Facts (Provenance-Tagged)"]]
                optional-layers [["attribute" "Attributes"]
                                 ["rdf-subject" "RDF Subjects"]
                                 ["ipld" "IPLD / DAG-CBOR"]]
                known-lids (set (map first (concat standard-layers optional-layers)))
                extra-lids (sort (remove known-lids (keys layer-counts)))
                all-layers (concat standard-layers
                                   (filter (fn [[lid _]] (pos? (get layer-counts lid 0))) optional-layers)
                                   (map (fn [lid] [lid lid]) extra-lids))]
            (vec (map-indexed (fn [idx [lid lbl]]
                                {:id lid
                                 :label lbl
                                 :order idx
                                 :nodeCount (get layer-counts lid 0)})
                              all-layers))))
        ;; On newly projected graphs (no preserved :yataverse-layers), canonicalize
        ;; node order by (layer order asc, id code-unit asc) and joins by name asc.
        yv-layer-rank (into {} (map (juxt :id :order) yv-layers))
        final-nodes (if (:yataverse-layers basis)
                      yv-nodes
                      (vec (sort-by (fn [n] [(get yv-layer-rank (:layer n) 999) (:id n)]) yv-nodes)))
        final-joins (if (:yataverse-layers basis)
                      yv-joins
                      (vec (sort-by :name yv-joins)))
        facts (filter #(= "fact" (:kind %)) final-nodes)
        by-connector (frequencies (keep #(get-in % [:meta "ontology/source"]) facts))
        by-type (frequencies (keep #(get-in % [:meta "ontology/type"]) facts))
        by-jur (frequencies (keep #(or (get-in % [:meta "jurisdiction"])
                                       (get-in % [:meta ":jurisdiction/code"]))
                                  facts))
        computed-coverage {:byConnector (into {} by-connector)
                           :byObjectType (into {} by-type)
                           :byJurisdiction (into {} by-jur)
                           :totalJoins (count final-joins)
                           :totalMatchedJoinRows (reduce + 0 (map :matchedRows final-joins))}
        stats (or (:stats basis)
                  {:objectTypes (count (filter #(= "object-type" (:kind %)) final-nodes))
                   :connectors (count (filter #(= "connector" (:kind %)) final-nodes))
                   :facts (count facts)
                   :quads (count (filter #(= "rdf-subject" (:kind %)) final-nodes))
                   :joins (count final-joins)})
        graph-id (or (:id basis) (:source basis) "kotoba-ontology-graph")
        node-cnt (count final-nodes)
        edge-cnt (count yv-edges)
        layer-cnt (count yv-layers)
        truncated? (boolean (:truncated basis))
        edges-truncated? (boolean (:edges-truncated basis))
        snap-schema (or (:snapshot-schema basis) "yataverse.ontology.snapshot/v1")
        top-meta {:id graph-id
                  :snapshotSchema snap-schema
                  :stats stats
                  :nodeCount node-cnt
                  :edgeCount edge-cnt
                  :layerCount layer-cnt
                  :truncated truncated?
                  :edgesTruncated edges-truncated?}
        body {:schema yataverse-graph-schema
              :version 1
              :basisCid (:root-cid basis)
              :id graph-id
              :stats stats
              :nodeCount node-cnt
              :meta top-meta
              :layers yv-layers
              :nodes final-nodes
              :edges yv-edges
              :joins final-joins
              :coverage (or (:coverage basis) computed-coverage)
              :truncated truncated?
              :edgesTruncated edges-truncated?}
        _ (v/assert-no-forbidden-wire-keys! body)
        {computed-graph-cid :cid} (dcbor/encode-ontology-graph-dag-cbor body)]
    (assoc body :graphCid computed-graph-cid)))
