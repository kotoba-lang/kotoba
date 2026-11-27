(ns kotoba.ontology-viz.yataverse
  "Explicit bidirectional wire adapter between Kotoba's canonical
  `ontology.graph/v1` model and Yataverse PR #83's `yataverse.ontology.graph/v1`
  schema (`schema`, numeric `version`, `basisCid`, `layers[].nodeCount`,
  `nodes[].meta`, `edges[].from/to/meta`, `joins[]`, `coverage`, `truncated`).

  Accepts both keyword-keyed EDN maps and string-keyed JSON-decoded maps."
  (:require [clojure.string :as str]
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
  `ontology.graph/v1` graph."
  ([yv] (<-yataverse-graph yv {}))
  ([yv {:keys [limits layout]}]
   (when-not (map? yv)
     (v/fail! :invalid-yataverse-graph "Yataverse graph must be a map" {:type (str (type yv))}))
   (let [schema (mget yv :schema)
         version (mget yv :version)
         basis-cid (mget yv :basisCid)
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
     (v/assert-bounded-and-no-remote-context! resolved-limits yv)
     (let [raw-nodes (or (mget yv :nodes) [])
           raw-edges (or (mget yv :edges) [])
           raw-joins (or (mget yv :joins) [])]
       (when-not (and (sequential? raw-nodes) (sequential? raw-edges) (sequential? raw-joins))
         (v/fail! :invalid-yataverse-graph "nodes, edges, and joins must be sequential" {}))
       (v/bounded-count-or-fail! raw-nodes (:max-nodes resolved-limits) :max-nodes-exceeded :nodes)
       (v/bounded-count-or-fail! raw-edges (:max-edges resolved-limits) :max-edges-exceeded :edges)
       (v/bounded-count-or-fail! raw-joins (:max-joins resolved-limits) :max-joins-exceeded :joins)
       (let [nodes
             (vec
              (sort-by
               :id
               (map
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
                raw-nodes)))
             edges
             (vec
              (sort-by
               :id
               (map
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
                raw-edges)))
             joins
             (vec
              (sort-by
               :id
               (map
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
                raw-joins)))
             layers (g/build-layers nodes)
             cids (vec (sort (distinct (keep identity (concat (when basis-cid [basis-cid])
                                                              (map :cid nodes))))))
             basis (cond-> {:schema-version g/schema-version
                            :codec "dag-cbor"
                            :hash-alg "sha2-256"
                            :cid-verification :syntax-only
                            :node-count (count nodes)
                            :edge-count (count edges)
                            :layer-count (count layers)
                            :join-count (count joins)
                            :cids cids
                            :bounds resolved-limits}
                     basis-cid (assoc :root-cid basis-cid)
                     (mget yv :id) (assoc :id (str (mget yv :id)))
                     (mget yv :stats) (assoc :stats (stringify-map-keys (mget yv :stats)))
                     (mget yv :coverage) (assoc :coverage (stringify-map-keys (mget yv :coverage)))
                     (contains? yv :truncated) (assoc :truncated (boolean (mget yv :truncated)))
                     (contains? yv "truncated") (assoc :truncated (boolean (mget yv :truncated))))
             graph {:schema/version g/schema-version
                    :schema/kind g/schema-kind
                    :basis basis
                    :layers layers
                    :nodes nodes
                    :edges edges
                    :joins joins}]
         (g/layout-graph graph (or layout {})))))))

(defn ->yataverse-graph
  "Validate and convert a Kotoba `ontology.graph/v1` graph into Yataverse PR #83's
  exact `yataverse.ontology.graph/v1` wire format."
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
        yv-edges
        (mapv
         (fn [e]
           {:id (:id e)
            :from (:source e)
            :to (:target e)
            :label (or (:label e) "")
            :kind (get kotoba-edge-kind->yv-edge-kind (:kind e) (name (or (:kind e) :provenance)))
            :meta (stringify-map-keys (:metadata e))})
         edges)
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
        yv-layer-order [["connector" "Connectors"]
                        ["object-type" "Object Types"]
                        ["attribute" "Attributes"]
                        ["fact" "Facts (Provenance-Tagged)"]
                        ["rdf-subject" "RDF Subjects"]
                        ["ipld" "IPLD / DAG-CBOR"]]
        known-lids (set (map first yv-layer-order))
        extra-lids (sort (remove known-lids (keys layer-counts)))
        all-layers (concat (filter (fn [[lid _]] (pos? (get layer-counts lid 0))) yv-layer-order)
                           (map (fn [lid] [lid lid]) extra-lids))
        yv-layers (vec (map-indexed (fn [idx [lid lbl]]
                                      {:id lid
                                       :label lbl
                                       :order idx
                                       :nodeCount (get layer-counts lid 0)})
                                    all-layers))
        facts (filter #(= "fact" (:kind %)) yv-nodes)
        by-connector (frequencies (keep #(get-in % [:meta "ontology/source"]) facts))
        by-type (frequencies (keep #(get-in % [:meta "ontology/type"]) facts))
        by-jur (frequencies (keep #(or (get-in % [:meta "jurisdiction"])
                                       (get-in % [:meta ":jurisdiction/code"]))
                                  facts))
        computed-coverage {:byConnector (into (sorted-map) by-connector)
                           :byObjectType (into (sorted-map) by-type)
                           :byJurisdiction (into (sorted-map) by-jur)
                           :totalJoins (count yv-joins)
                           :totalMatchedJoinRows (reduce + 0 (map :matchedRows yv-joins))}
        stats (or (:stats basis)
                  {:objectTypes (count (filter #(= "object-type" (:kind %)) yv-nodes))
                   :connectors (count (filter #(= "connector" (:kind %)) yv-nodes))
                   :facts (count facts)
                   :quads (count (filter #(= "rdf-subject" (:kind %)) yv-nodes))
                   :joins (count yv-joins)})]
    {:schema yataverse-graph-schema
     :version 1
     :basisCid (:root-cid basis)
     :id (or (:id basis) (:source basis) "kotoba-ontology-graph")
     :stats stats
     :layers yv-layers
     :nodes yv-nodes
     :edges yv-edges
     :joins yv-joins
     :coverage (or (:coverage basis) computed-coverage)
     :truncated (boolean (:truncated basis))}))
