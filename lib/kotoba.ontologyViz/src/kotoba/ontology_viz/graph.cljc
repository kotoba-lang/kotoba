(ns kotoba.ontology-viz.graph
  "Canonical ontology graph projection, scoped & ambiguity-safe external join
  coverage evaluation, chronological EAVT folding, full-provenance RDF quad
  projection, and deterministic layered DAG layout (`ontology.graph/v1`)."
  (:require [clojure.string :as str]
            [kotoba.ontology-viz.escape :as esc]
            [kotoba.ontology-viz.validate :as v]))

(def schema-version "ontology.graph/v1")
(def schema-kind "ontology.graph")

(def default-layer-specs
  "Canonical layer ordering and visual palette (strict #RRGGBB hex, self-contained)."
  {"connector" {:id "connector" :label "Connectors"        :order 0 :color "#0f766e" :bg "#f0fdfa"}
   "ontology"  {:id "ontology"  :label "Ontology Types"    :order 1 :color "#1d4ed8" :bg "#eff6ff"}
   "attribute" {:id "attribute" :label "Attributes"        :order 2 :color "#6d28d9" :bg "#f5f3ff"}
   "instance"  {:id "instance"  :label "Instances / EAVT"  :order 3 :color "#b45309" :bg "#fffbeb"}
   "rdf"       {:id "rdf"       :label "RDF / Named Graph" :order 4 :color "#0369a1" :bg "#f0f9ff"}
   "ipld"      {:id "ipld"      :label "IPLD / DAG-CBOR"   :order 5 :color "#be123c" :bg "#fff1f2"}})

(defn- id-str [x]
  (cond
    (keyword? x) (if (namespace x)
                   (str (namespace x) "/" (name x))
                   (name x))
    (symbol? x) (str x)
    (string? x) x
    :else (str x)))

(defn- kw-str [x]
  (cond
    (keyword? x) (str ":" (id-str x))
    (string? x) x
    :else (str x)))

(defn- layer-str [x fallback]
  (if (some? x) (id-str x) fallback))

(defn- rdf-term->str [term]
  (cond
    (and (map? term) (= :iri (:rdf/type term))) (:value term)
    (and (map? term) (= :blank (:rdf/type term))) (str "_:" (:id term))
    (and (map? term) (= :literal (:rdf/type term))) (str (:value term))
    (keyword? term) (kw-str term)
    :else (str term)))

(defn- rdf-term-kind [term]
  (cond
    (and (map? term) (= :iri (:rdf/type term))) :iri
    (and (map? term) (= :blank (:rdf/type term))) :blank
    (and (map? term) (= :literal (:rdf/type term))) :literal
    :else :literal))

(defn- rdf-datatype-str [dt]
  (cond
    (nil? dt) nil
    (and (map? dt) (= :iri (:rdf/type dt))) (:value dt)
    (string? dt) dt
    :else (str dt)))

(defn- format-rdf-literal
  "Preserve RDF 1.1 literal value, language tag, and datatype IRI."
  [term]
  (if (and (map? term) (= :literal (:rdf/type term)))
    (let [val-s (str (:value term))
          lang (:language term)
          dt (rdf-datatype-str (:datatype term))]
      (cond
        (and lang (not (str/blank? (str lang))))
        (str val-s "@" lang)

        (and dt (not= dt "http://www.w3.org/2001/XMLSchema#string"))
        (str val-s "^^<" dt ">")

        :else val-s))
    (str term)))

(defn- compact-iri-label [iri]
  (let [s (str iri)]
    (cond
      (str/includes? s "#") (let [frag (last (str/split s #"#"))]
                              (if (str/blank? frag) s frag))
      (str/includes? s "/") (let [seg (last (str/split s #"/"))]
                              (if (str/blank? seg) s seg))
      :else s)))

(defn- append-attr-val
  "Preserve multi-valued attribute entries deterministically without silently
  discarding prior distinct values."
  [existing incoming]
  (cond
    (nil? existing) incoming
    (= existing incoming) existing
    (vector? existing) (if (some #(= % incoming) existing)
                         existing
                         (vec (sort (conj existing incoming))))
    :else (vec (sort [existing incoming]))))

(defn- merge-attrs [a b]
  (reduce-kv (fn [acc k val]
               (update acc k append-attr-val val))
             (or a {})
             (or b {})))

(defn- merge-provenance
  "Merge provenance maps without dropping multi-graph provenance: `:named-graphs`
  is merged as a deterministically sorted union."
  [a b]
  (let [base (merge a b)
        ng-a (:named-graphs a)
        ng-b (:named-graphs b)]
    (if (or ng-a ng-b)
      (assoc base :named-graphs (vec (sort (distinct (concat ng-a ng-b)))))
      base)))

(defn- merge-node
  "Merge incoming node into existing node while preserving higher-priority
  human-readable labels and multi-graph provenance union."
  [existing incoming limits]
  (let [merged-attrs (merge-attrs (:attributes existing) (:attributes incoming))
        ex-prio (or (::label-priority existing) 1)
        in-prio (or (::label-priority incoming) 1)
        chosen-label (if (>= in-prio ex-prio)
                       (or (:label incoming) (:label existing))
                       (:label existing))
        chosen-prio (max ex-prio in-prio)]
    (v/assert-attributes-count! limits (:id incoming) (count merged-attrs))
    (cond-> (merge existing incoming)
      true (assoc :label chosen-label ::label-priority chosen-prio)
      (seq merged-attrs) (assoc :attributes merged-attrs)
      (and (:cid existing) (nil? (:cid incoming))) (assoc :cid (:cid existing))
      (and (:keys existing) (empty? (:keys incoming))) (assoc :keys (:keys existing))
      (or (:provenance existing) (:provenance incoming))
      (assoc :provenance (merge-provenance (:provenance existing) (:provenance incoming))))))

(defn- add-node [state node]
  (let [limits (:limits state)
        id (:id node)
        prio (or (::label-priority node) 1)
        node* (assoc node ::label-priority prio)]
    (v/assert-label-length! limits :node/id id)
    (v/assert-label-length! limits :node/label (:label node*))
    (when-let [attrs (:attributes node*)]
      (v/assert-attributes-count! limits id (count attrs)))
    (let [nodes (:nodes state)
          updated (if-let [prev (get nodes id)]
                    (assoc nodes id (merge-node prev node* limits))
                    (let [next-nodes (assoc nodes id node*)]
                      (v/assert-node-count! limits (count next-nodes))
                      next-nodes))]
      (assoc state :nodes updated))))

(defn- add-edge [state edge]
  (let [limits (:limits state)
        id (:id edge)]
    (v/assert-label-length! limits :edge/id id)
    (v/assert-label-length! limits :edge/label (:label edge))
    (let [edges (:edges state)
          updated (if (contains? edges id)
                    (update edges id merge edge)
                    (let [next-edges (assoc edges id edge)]
                      (v/assert-edge-count! limits (count next-edges))
                      next-edges))]
      (assoc state :edges updated))))

(defn- record-attr-value
  "Record observed attribute values both globally and scoped by `owner-type`
  so join coverage cleanly isolates values per declared object type."
  ([state attr val] (record-attr-value state nil attr val))
  ([state owner-type attr val]
   (if (and (some? attr) (some? val))
     (let [ak (kw-str attr)
           st1 (update-in state [:observed-attr-values ak] (fnil conj []) val)]
       (if owner-type
         (update-in st1 [:observed-typed-values [(id-str owner-type) ak]] (fnil conj []) val)
         st1))
     state)))

;; ── Projectors per source domain ─────────────────────────────────────────────

(defn- collect-ref-attributes
  "Identify attributes explicitly declared as entity references (`:ref` or
  `:db.type/ref`) in `:ontology` or `:kotoba-schema`."
  [input]
  (let [onto-refs
        (for [ot (get-in input [:ontology :object-types])
              [k vtype] (:attributes ot)
              :when (contains? #{:ref :db.type/ref "ref" "db.type/ref"} vtype)]
          (kw-str k))
        ks (:kotoba-schema input)
        ks-decls (cond
                   (sequential? ks) ks
                   (map? ks) (concat (:attributes ks) (:db/attributes ks) (:classes ks) (:object-types ks))
                   :else [])
        ks-refs
        (for [d ks-decls
              :when (and (map? d)
                         (:db/ident d)
                         (contains? #{:ref :db.type/ref "ref" "db.type/ref"} (:db/valueType d)))]
          (kw-str (:db/ident d)))]
    (set (concat onto-refs ks-refs))))

(defn- project-ontology-registry [state onto]
  (reduce
   (fn [st ot]
     (let [type-id (str "type:" (id-str (:id ot)))
           type-label (or (:name ot) (id-str (:id ot)))
           label-prio (if (:name ot) 3 2)
           layer (layer-str (:layer ot) "ontology")
           cid (v/extract-cid (:cid ot))
           attrs (or (:attributes ot) {})
           key-attrs (mapv kw-str (or (:key ot) []))
           st1 (add-node st (cond-> {:id type-id
                                     :label type-label
                                     ::label-priority label-prio
                                     :kind :object-type
                                     :layer layer
                                     :attributes (into {} (map (fn [[k val]] [(kw-str k) (id-str val)]) attrs))
                                     :keys key-attrs}
                              cid (assoc :cid cid)
                              (:doc ot) (assoc :doc (:doc ot))))
           st2 (if cid
                 (-> st1
                     (add-node {:id (str "ipld:" cid)
                                :label (str "IPLD " (subs cid 0 (min 14 (count cid))))
                                ::label-priority 1
                                :kind :ipld-node
                                :layer "ipld"
                                :cid cid})
                     (add-edge {:id (str "edge:" type-id "->ipld:" cid ":cid")
                                :source type-id
                                :target (str "ipld:" cid)
                                :label "ipld:cid"
                                :kind :ipld-link
                                :layer "ipld"
                                :cid cid}))
                 st1)]
       (reduce-kv
        (fn [acc attr-k attr-type]
          (let [attr-node-id (str "attr:" (id-str attr-k))
                is-key? (boolean (some #(= % attr-k) (:key ot)))]
            (-> acc
                (add-node {:id attr-node-id
                           :label (kw-str attr-k)
                           ::label-priority 2
                           :kind :attribute
                           :layer "attribute"
                           :attributes {:value-type (id-str attr-type)
                                        :key? (str is-key?)
                                        :owner-type (id-str (:id ot))}})
                (add-edge {:id (str "edge:" type-id "->" attr-node-id ":has-attribute")
                           :source type-id
                           :target attr-node-id
                           :label (if is-key? "key-attr" "has-attr")
                           :kind :has-attribute
                           :layer "attribute"
                           :metadata {:value-type (id-str attr-type) :key? is-key?}}))))
        st2
        attrs)))
   state
   (:object-types onto)))

(defn- project-connectors [state conn-reg]
  (reduce
   (fn [st c]
     (let [conn-id (str "connector:" (id-str (:id c)))
           target-id (str "type:" (id-str (:object-type c)))
           cid (v/extract-cid (:cid c))
           safe-repo (v/safe-display-https-url (:repo c))
           st1 (add-node st (cond-> {:id conn-id
                                     :label (or (:name c) (id-str (:id c)))
                                     ::label-priority (if (:name c) 3 2)
                                     :kind :connector
                                     :layer (layer-str (:layer c) "connector")
                                     :attributes (cond-> {:object-type (id-str (:object-type c))
                                                          :status (id-str (or (:status c) :unknown))}
                                                   safe-repo (assoc :repo safe-repo))
                                     :provenance (cond-> {:connector-id (id-str (:id c))
                                                          :status (id-str (or (:status c) :unknown))}
                                                   safe-repo (assoc :repo safe-repo))}
                              cid (assoc :cid cid)))
           st2 (if (contains? (:nodes st1) target-id)
                 st1
                 (add-node st1 {:id target-id
                                :label (id-str (:object-type c))
                                ::label-priority 1
                                :kind :object-type
                                :layer "ontology"}))]
       (add-edge st2 {:id (str "edge:" conn-id "->" target-id ":produces")
                      :source conn-id
                      :target target-id
                      :label "produces"
                      :kind :produces
                      :layer "connector"
                      :metadata {:status (id-str (or (:status c) :unknown))}})))
   state
   (:connectors conn-reg)))

(defn- project-kotoba-schema [state ks]
  (let [decls (cond
                (sequential? ks) ks
                (map? ks) (concat (:attributes ks) (:db/attributes ks) (:classes ks) (:object-types ks))
                :else [])]
    (reduce
     (fn [st d]
       (cond
         (and (map? d) (:db/ident d))
         (let [ident (:db/ident d)
               attr-id (str "attr:" (id-str ident))
               ns-part (namespace ident)
               owner-id (when ns-part (str "type:" ns-part))
               vtype (id-str (or (:db/valueType d) :any))
               card (id-str (or (:db/cardinality d) :db.cardinality/one))
               st1 (add-node st {:id attr-id
                                 :label (kw-str ident)
                                 ::label-priority 2
                                 :kind :attribute
                                 :layer "attribute"
                                 :attributes (cond-> {:value-type vtype
                                                      :cardinality card}
                                               (:db/doc d) (assoc :doc (:db/doc d)))})]
           (if owner-id
             (-> st1
                 (add-node {:id owner-id
                            :label ns-part
                            ::label-priority 1
                            :kind :object-type
                            :layer "ontology"})
                 (add-edge {:id (str "edge:" owner-id "->" attr-id ":has-attribute")
                            :source owner-id
                            :target attr-id
                            :label "has-attr"
                            :kind :has-attribute
                            :layer "attribute"
                            :metadata {:value-type vtype :cardinality card}}))
             st1))

         (and (map? d) (:id d))
         (project-ontology-registry st {:object-types [d]})

         :else st))
     state
     decls)))

(defn- project-facts [state facts]
  (reduce
   (fn [st [idx fact]]
     (let [otype (:ontology/type fact)
           src (:ontology/source fact)
           cid (v/extract-cid (or (:ipld/cid fact) (:cid fact)))
           ent-key (or (:id fact) (:db/id fact) (str "fact-" idx))
           ent-str (id-str ent-key)
           node-id (str "entity:" ent-str)
           payload (dissoc fact :ontology/type :ontology/source :ontology/fetched-at :ontology/confidence)
           provenance (cond-> {}
                        otype (assoc :type (id-str otype))
                        src (assoc :source (id-str src))
                        (:ontology/fetched-at fact) (assoc :fetched-at (str (:ontology/fetched-at fact)))
                        (contains? fact :ontology/confidence) (assoc :confidence (:ontology/confidence fact)))
           human-label (or (:name fact) (:title fact))
           st0 (if otype
                 (assoc-in st [:entity-types ent-str] (id-str otype))
                 st)
           st1 (add-node st0 (cond-> {:id node-id
                                      :label (str (or human-label ent-str))
                                      ::label-priority (if human-label 3 2)
                                      :kind :entity
                                      :layer "instance"
                                      :attributes (into {}
                                                        (map (fn [[k val]]
                                                               [(kw-str k)
                                                                (if (v/ipld-link? val) (v/extract-cid val) (str val))]))
                                                        payload)
                                      :provenance provenance}
                               cid (assoc :cid cid)))
           st2 (reduce-kv (fn [acc k val] (record-attr-value acc otype k val)) st1 payload)
           st3 (if otype
                 (let [t-id (str "type:" (id-str otype))]
                   (-> st2
                       (add-node {:id t-id :label (id-str otype) ::label-priority 1 :kind :object-type :layer "ontology"})
                       (add-edge {:id (str "edge:" node-id "->" t-id ":instance-of")
                                  :source node-id
                                  :target t-id
                                  :label "instance-of"
                                  :kind :instance-of
                                  :layer "instance"})))
                 st2)
           st4 (if src
                 (let [c-id (str "connector:" (id-str src))]
                   (-> st3
                       (add-node {:id c-id :label (id-str src) ::label-priority 1 :kind :connector :layer "connector"})
                       (add-edge {:id (str "edge:" c-id "->" node-id ":ingested")
                                  :source c-id
                                  :target node-id
                                  :label "ingested"
                                  :kind :provenance
                                  :layer "connector"})))
                 st3)]
       (if cid
         (-> st4
             (add-node {:id (str "ipld:" cid)
                        :label (str "IPLD " (subs cid 0 (min 14 (count cid))))
                        ::label-priority 1
                        :kind :ipld-node
                        :layer "ipld"
                        :cid cid})
             (add-edge {:id (str "edge:" node-id "->ipld:" cid ":cid")
                        :source node-id
                        :target (str "ipld:" cid)
                        :label "ipld:cid"
                        :kind :ipld-link
                        :layer "ipld"
                        :cid cid}))
         st4)))
   state
   (map-indexed vector facts)))

;; ── EAVT Datom Temporal Folding & Explicit Reference Projection ──────────────

(defn- normalize-datom [idx d]
  (if (vector? d)
    {:e (nth d 0)
     :a (nth d 1)
     :v (nth d 2)
     :tx (when (>= (count d) 4) (nth d 3))
     :added? (if (>= (count d) 5) (boolean (nth d 4)) true)
     :idx idx}
    {:e (:e d)
     :a (:a d)
     :v (:v d)
     :tx (:tx d)
     :added? (if (contains? d :added?) (boolean (:added? d)) true)
     :idx idx}))

(defn- fold-eavt-datoms
  "Fold EAVT datoms chronologically by `[tx idx]` so retractions (`added? false`)
  cancel prior matching assertions and later re-assertions restore them.
  Retains multi-valued attributes per `[e a]`."
  [datoms]
  (let [ordered (sort-by (fn [{:keys [tx idx]}] [(if (number? tx) tx 0) idx])
                         (map-indexed normalize-datom datoms))
        active (reduce
                (fn [acc {:keys [e a v added?] :as d}]
                  (let [k [e a v]]
                    (if added?
                      (assoc acc k d)
                      (dissoc acc k))))
                {}
                ordered)]
    (sort-by :idx (vals active))))

(defn- explicit-entity-ref
  "Return referenced entity ID ONLY when `v` is an explicit reference wrapper
  (`{:db/id ...}` / `{:entity/ref ...}`) or `a-str` is schema-declared `:ref`
  / `:db.type/ref`. Never infers reference edges from untyped plain strings or
  untyped namespaced keywords accidentally matching another entity ID."
  [a-str v ref-attrs]
  (cond
    (and (map? v) (contains? v :db/id)) (:db/id v)
    (and (map? v) (contains? v :entity/ref)) (:entity/ref v)
    (contains? ref-attrs a-str) v
    :else nil))

(defn- resolve-datom-owner-type
  "Resolve owner type for entity `e` using declared `:entity-types` (from facts
  or `:ontology/type` datoms) first, falling back to keyword namespace."
  [e entity-types]
  (or (get entity-types (id-str e))
      (when (and (keyword? e) (namespace e))
        (namespace e))))

(defn- project-datoms [state datoms ref-attrs]
  (let [active (fold-eavt-datoms datoms)
        ;; Also harvest any `:ontology/type` assertions from active datoms
        datom-types (reduce
                     (fn [m {:keys [e a v]}]
                       (if (= :ontology/type a)
                         (assoc m (id-str e) (id-str v))
                         m))
                     (:entity-types state)
                     active)
        state* (assoc state :entity-types datom-types)]
    (reduce
     (fn [st {:keys [e a v tx]}]
       (let [e-str (id-str e)
             e-node-id (str "entity:" e-str)
             a-str (kw-str a)
             owner-type (resolve-datom-owner-type e datom-types)
             st1 (-> st
                     (add-node {:id e-node-id
                                :label e-str
                                ::label-priority 1
                                :kind :entity
                                :layer "instance"})
                     (record-attr-value owner-type a v))
             ref-target (when-not (v/ipld-link? v)
                          (explicit-entity-ref a-str v ref-attrs))]
         (cond
           (v/ipld-link? v)
           (let [cid (v/extract-cid v)
                 t-id (str "ipld:" cid)]
             (-> st1
                 (add-node {:id t-id
                            :label (str "IPLD " (subs cid 0 (min 14 (count cid))))
                            ::label-priority 1
                            :kind :ipld-node
                            :layer "ipld"
                            :cid cid})
                 (add-edge {:id (str "edge:" e-node-id "->" t-id ":" (id-str a))
                            :source e-node-id
                            :target t-id
                            :label a-str
                            :kind :ipld-link
                            :layer "ipld"
                            :cid cid
                            :metadata (cond-> {:attribute a-str} tx (assoc :tx tx))})))

           ;; Preserve genuine self-references as self-edges (do NOT collapse to scalar)
           (some? ref-target)
           (let [t-id (str "entity:" (id-str ref-target))]
             (-> st1
                 (add-node {:id t-id :label (id-str ref-target) ::label-priority 1 :kind :entity :layer "instance"})
                 (add-edge {:id (str "edge:" e-node-id "->" t-id ":" (id-str a))
                            :source e-node-id
                            :target t-id
                            :label a-str
                            :kind :datom-ref
                            :layer "instance"
                            :metadata (cond-> {:attribute a-str}
                                        tx (assoc :tx tx)
                                        (= e-node-id t-id) (assoc :self-ref true))})))

           :else
           (add-node st1 {:id e-node-id
                          :label e-str
                          ::label-priority 1
                          :kind :entity
                          :layer "instance"
                          :attributes {a-str (str v)}}))))
     state*
     active)))

;; ── Full-Fidelity RDF Quad Projection (`org.w3.rdf` shape) ───────────────────

(defn- project-rdf-quads [state quads]
  (reduce
   (fn [st q]
     (let [subj (:subject q)
           pred (:predicate q)
           obj (:object q)
           graph-name (when (:graph q) (rdf-term->str (:graph q)))
           s-str (rdf-term->str subj)
           p-str (rdf-term->str pred)
           o-str (rdf-term->str obj)
           s-id (str "rdf:" s-str)
           p-label (compact-iri-label p-str)
           o-kind (rdf-term-kind obj)
           layer "rdf"
           graph-suffix (when graph-name (str "@graph:" graph-name))
           st1 (-> st
                   (add-node (cond-> {:id s-id
                                      :label (compact-iri-label s-str)
                                      ::label-priority 1
                                      :kind (if (= :blank (rdf-term-kind subj)) :rdf-blank :rdf-resource)
                                      :layer layer
                                      :attributes {:iri s-str}}
                               graph-name (assoc :provenance {:named-graphs [graph-name]})))
                   (record-attr-value nil p-str o-str))]
       (if (or (= o-kind :iri) (= o-kind :blank))
         (let [o-id (str "rdf:" o-str)
               edge-id (str "edge:" s-id "->" o-id "|" p-str (or graph-suffix ""))]
           (-> st1
               (add-node (cond-> {:id o-id
                                  :label (compact-iri-label o-str)
                                  ::label-priority 1
                                  :kind (if (= o-kind :blank) :rdf-blank :rdf-resource)
                                  :layer layer
                                  :attributes {:iri o-str}}
                           graph-name (assoc :provenance {:named-graphs [graph-name]})))
               (add-edge {:id edge-id
                          :source s-id
                          :target o-id
                          :label p-label
                          :kind :rdf-predicate
                          :layer layer
                          :metadata (cond-> {:predicate-iri p-str}
                                      graph-name (assoc :graph graph-name))})))
         (let [lit-val (format-rdf-literal obj)
               attr-key (if graph-name (str p-str " [" graph-name "]") p-str)]
           (add-node st1 {:id s-id
                          :label (compact-iri-label s-str)
                          ::label-priority 1
                          :kind (if (= :blank (rdf-term-kind subj)) :rdf-blank :rdf-resource)
                          :layer layer
                          :attributes {attr-key lit-val}})))))
   state
   quads))

;; ── IPLD Block / Link Projection ─────────────────────────────────────────────

(defn- collect-links-from-value
  "Recursively collect [path-label cid] pairs from an IPLD DAG-CBOR block value."
  [val path]
  (cond
    (v/ipld-link? val)
    [[(if (seq path) (str/join "." path) "link") (v/extract-cid val)]]

    (map? val)
    (mapcat (fn [[k child]]
              (collect-links-from-value child (conj path (id-str k))))
            val)

    (sequential? val)
    (mapcat (fn [[idx child]]
              (collect-links-from-value child (conj path (str idx))))
            (map-indexed vector val))

    :else []))

(defn- project-ipld-nodes [state ipld-nodes]
  (let [entries (if (map? ipld-nodes)
                  (map (fn [[cid node]] {:cid cid :node node}) ipld-nodes)
                  ipld-nodes)]
    (reduce
     (fn [st entry]
       (let [cid (v/extract-cid (or (:cid entry) (:link entry)))
             node-val (or (:node entry) (:data entry) (dissoc entry :cid :link :label :codec))
             node-id (str "ipld:" cid)
             explicit-label (or (:label entry)
                                (when (map? node-val) (or (get node-val "name") (get node-val :name))))
             label (or explicit-label (str "IPLD " (subs cid 0 (min 14 (count cid)))))
             scalar-attrs (if (map? node-val)
                            (into {}
                                  (keep (fn [[k val]]
                                          (when (or (string? val) (number? val) (boolean? val) (keyword? val))
                                            [(id-str k) (str val)])))
                                  node-val)
                            {})
             st1 (add-node st {:id node-id
                               :label (str label)
                               ::label-priority (if explicit-label 2 1)
                               :kind :ipld-node
                               :layer "ipld"
                               :cid cid
                               :attributes (assoc scalar-attrs :codec (str (or (:codec entry) "dag-cbor")))})
             links (collect-links-from-value node-val [])]
         (reduce
          (fn [acc [field-path target-cid]]
            (let [t-id (str "ipld:" target-cid)]
              (-> acc
                  (add-node {:id t-id
                             :label (str "IPLD " (subs target-cid 0 (min 14 (count target-cid))))
                             ::label-priority 1
                             :kind :ipld-node
                             :layer "ipld"
                             :cid target-cid})
                  (add-edge {:id (str "edge:" node-id "->" t-id ":" field-path)
                             :source node-id
                             :target t-id
                             :label field-path
                             :kind :ipld-link
                             :layer "ipld"
                             :cid target-cid
                             :metadata {:from-cid cid :to-cid target-cid}}))))
          st1
          links)))
     state
     entries)))

;; ── Scoped, Ambiguity-Safe & Pair-Bounded External Join Coverage ─────────────

(defn- normalize-join-val [rule mapping v]
  (let [s (str v)]
    (case rule
      :exact s
      :exact-uppercase (str/upper-case s)
      :exact-lowercase (str/lower-case s)
      :mapping (get mapping s (get mapping (str/upper-case s) s))
      :prefix s
      s)))

(defn- excluded-value? [exclude-set v]
  (let [s (str v)]
    (or (contains? exclude-set v)
        (contains? exclude-set s)
        (contains? exclude-set (str/upper-case s)))))

(defn- round4 [x]
  (/ (esc/round-int (* (double x) 10000.0)) 10000.0))

(defn- resolve-scoped-values
  "Prefer values scoped to `(type-id, attr)` when `type-id` is declared,
  preventing cross-type collisions when two types share an attribute name."
  [explicit type-id attr-k observed-typed observed-global]
  (cond
    (some? explicit) (vec (distinct explicit))
    (some? type-id) (vec (distinct (get observed-typed [(id-str type-id) attr-k] [])))
    :else (vec (distinct (get observed-global attr-k [])))))

(defn evaluate-join
  "Pure evaluator for external join coverage with match rules, explicit mapping,
  exclusions, type-scoped extraction, fail-closed ambiguity handling, and an
  explicit candidate-pair bound (`:max-join-pairs`) enforced incrementally."
  ([join-spec] (evaluate-join join-spec {} {} v/default-limits))
  ([join-spec observed-attr-values] (evaluate-join join-spec observed-attr-values {} v/default-limits))
  ([join-spec observed-attr-values observed-typed-values]
   (evaluate-join join-spec observed-attr-values observed-typed-values v/default-limits))
  ([join-spec observed-attr-values observed-typed-values limits]
   (let [from-attr (kw-str (:from-attr join-spec))
         to-attr (kw-str (:to-attr join-spec))
         join-id (or (:id join-spec)
                     (str "join:" (id-str (:from-attr join-spec)) "->" (id-str (:to-attr join-spec))))
         rule (or (:match-rule join-spec) (if (seq (:mapping join-spec)) :mapping :exact))
         on-ambiguous (or (:on-ambiguous join-spec) :error)
         max-pairs (or (:max-join-pairs limits) (:max-join-pairs v/default-limits))
         max-comparisons (or (:max-join-comparisons limits) (:max-join-comparisons v/default-limits))
         comparisons (volatile! 0)
         mapping (into {} (map (fn [[k val]] [(str k) (str val)])) (or (:mapping join-spec) {}))
         exclude-set (set (concat (:exclude join-spec) (:exclude-values join-spec)))
         src-raw (resolve-scoped-values (:source-values join-spec) (:from-type join-spec) from-attr
                                        observed-typed-values observed-attr-values)
         tgt-raw (resolve-scoped-values (:target-values join-spec) (:to-type join-spec) to-attr
                                        observed-typed-values observed-attr-values)
         tgt-index (reduce
                    (fn [m tv]
                      (let [ts (str tv)
                            k (case rule
                                :exact-uppercase (str/upper-case ts)
                                :exact-lowercase (str/lower-case ts)
                                ts)]
                        (update m k (fnil (fn [v] (if (some #(= % ts) v) v (vec (sort (conj v ts))))) []))))
                    {}
                    tgt-raw)
         tgt-sorted (vec (sort (distinct (map str tgt-raw))))
         {:keys [matched-sources matched-pairs pair-count unmatched excluded]}
         (reduce
          (fn [acc sv]
            (let [s (str sv)]
              (if (excluded-value? exclude-set sv)
                (update acc :excluded conj s)
                (let [norm (normalize-join-val rule mapping sv)
                      candidates (if (= rule :prefix)
                                   (persistent!
                                    (reduce
                                     (fn [matches tv]
                                       (let [c (vswap! comparisons inc)]
                                         (when (> c max-comparisons)
                                           (v/fail! :max-join-comparisons-exceeded
                                                    (str "join " join-id " exceeded max-join-comparisons (" max-comparisons ")")
                                                    {:join-id join-id :limit max-comparisons :comparisons c})))
                                       (if (or (str/starts-with? tv norm)
                                               (str/starts-with? norm tv))
                                         (conj! matches tv)
                                         matches))
                                     (transient [])
                                     tgt-sorted))
                                   (get tgt-index norm []))]
                  (cond
                    (empty? candidates)
                    (update acc :unmatched conj s)

                    (and (> (count candidates) 1) (= on-ambiguous :error))
                    (v/fail! :ambiguous-join-match
                             (str "ambiguous join match in " join-id " for value " (pr-str s)
                                  ": matched " (pr-str candidates))
                             {:join-id join-id :source-value s :candidates candidates :match-rule rule})

                    :else
                    (let [next-pair-count (+ (:pair-count acc) (count candidates))]
                      (when (> next-pair-count max-pairs)
                        (v/fail! :max-join-pairs-exceeded
                                 (str "join " join-id " exceeded max-join-pairs (" max-pairs ")")
                                 {:join-id join-id :limit max-pairs :actual next-pair-count}))
                      (let [existing-sample (:matched-pairs acc)
                            room (max 0 (- 50 (count existing-sample)))
                            sample-add (if (pos? room)
                                         (map (fn [c] [s c]) (take room candidates))
                                         [])]
                        (-> acc
                            (assoc :pair-count next-pair-count)
                            (update :matched-sources conj s)
                            (update :matched-pairs into sample-add)))))))))
          {:matched-sources [] :matched-pairs [] :pair-count 0 :unmatched [] :excluded []}
          (sort-by str src-raw))
         total (count src-raw)
         excl-n (count excluded)
         eligible (- total excl-n)
         match-n (count matched-sources)
         unmatch-n (count unmatched)
         coverage (when (pos? eligible) (round4 (/ (double match-n) (double eligible))))
         status (cond
                  (zero? total) :schema-only
                  (zero? eligible) :all-excluded
                  (= match-n eligible) :full
                  (pos? match-n) :partial
                  :else :unmatched)
         from-node (or (:from-node join-spec)
                       (when-let [ft (:from-type join-spec)] (str "type:" (id-str ft)))
                       (str "attr:" (id-str (:from-attr join-spec))))
         to-node (or (:to-node join-spec)
                     (when-let [tt (:to-type join-spec)] (str "type:" (id-str tt)))
                     (str "attr:" (id-str (:to-attr join-spec))))]
     (cond-> {:id join-id
              :from-node from-node
              :from-attr from-attr
              :to-node to-node
              :to-attr to-attr
              :match-rule rule
              :on-ambiguous on-ambiguous
              :cardinality (or (:cardinality join-spec) :many-to-one)
              :exclude (vec (sort (map str exclude-set)))
              :matched-count match-n
              :matched-rows pair-count
              :unmatched-count unmatch-n
              :excluded-count excl-n
              :total-source-count total
              :eligible-count eligible
              :coverage coverage
              :status status
              :matched-pairs (vec (sort matched-pairs))
              :unmatched-values (vec (take 50 (sort unmatched)))
              :excluded-values (vec (take 50 (sort excluded)))}
       (:description join-spec) (assoc :description (:description join-spec))))))

(defn- project-joins [state joins]
  (reduce
   (fn [st jspec]
     (let [evaluated (evaluate-join jspec (:observed-attr-values st) (:observed-typed-values st) (:limits st))
           from-id (:from-node evaluated)
           to-id (:to-node evaluated)
           cov-label (if (some? (:coverage evaluated))
                       (str "join " (esc/round-int (* 100.0 (double (:coverage evaluated)))) "%")
                       "join")
           st1 (if (contains? (:nodes st) from-id)
                 st
                 (add-node st {:id from-id
                               :label (:from-attr evaluated)
                               ::label-priority 1
                               :kind (if (str/starts-with? from-id "type:") :object-type :attribute)
                               :layer (if (str/starts-with? from-id "type:") "ontology" "attribute")}))
           st2 (if (contains? (:nodes st1) to-id)
                 st1
                 (add-node st1 {:id to-id
                                :label (:to-attr evaluated)
                                ::label-priority 1
                                :kind (if (str/starts-with? to-id "type:") :object-type :attribute)
                                :layer (if (str/starts-with? to-id "type:") "ontology" "attribute")}))
           st3 (add-edge st2 {:id (str "edge:" (:id evaluated))
                              :source from-id
                              :target to-id
                              :label cov-label
                              :kind :join
                              :layer "ontology"
                              :metadata {:join-id (:id evaluated)
                                         :from-attr (:from-attr evaluated)
                                         :to-attr (:to-attr evaluated)
                                         :coverage (:coverage evaluated)
                                         :status (:status evaluated)}})]
       (update st3 :joins conj evaluated)))
   state
   joins))

;; ── Deterministic Layered DAG Layout ─────────────────────────────────────────

(defn build-layers
  "Derive ordered layer descriptors with strict `#RRGGBB` palette and counts."
  [nodes]
  (let [counts (frequencies (map :layer nodes))
        known-keys ["connector" "ontology" "attribute" "instance" "rdf" "ipld"]
        extra-keys (sort (remove #(contains? default-layer-specs %) (keys counts)))
        all-keys (concat (filter #(contains? counts %) known-keys) extra-keys)]
    (vec
     (map-indexed
      (fn [idx layer-id]
        (let [spec (get default-layer-specs layer-id
                        {:id layer-id
                         :label layer-id
                         :order (+ 10 idx)
                         :color "#475569"
                         :bg "#f8fafc"})]
          (assoc spec
                 :order idx
                 :node-count (get counts layer-id 0))))
      all-keys))))

(defn layout-graph
  "Validate input graph AND caller layout options, assign deterministic layered
  DAG coordinates preserving `(:nodes graph)` order, and validate the resulting
  graph before returning."
  ([graph] (layout-graph graph {} {}))
  ([graph opts] (layout-graph graph opts {}))
  ([graph opts validate-opts]
   (v/validate-graph! graph validate-opts)
   (v/validate-layout-options! opts)
   (let [{:keys [direction node-width node-height col-gap row-gap pad-x pad-y]
          :or {direction :horizontal
               node-width 216
               node-height 68
               col-gap 92
               row-gap 28
               pad-x 40
               pad-y 84}} (or opts {})
         layers (:layers graph)
         layer-index (into {} (map-indexed (fn [i l] [(:id l) i]) layers))
         {:keys [positioned-nodes]}
         (reduce
          (fn [{:keys [row-counts positioned-nodes]} node]
            (let [lid (:layer node)
                  col (get layer-index lid 0)
                  row (get row-counts lid 0)
                  x (if (= direction :vertical)
                      (+ pad-x (* row (+ node-width row-gap)))
                      (+ pad-x (* col (+ node-width col-gap))))
                  y (if (= direction :vertical)
                      (+ pad-y (* col (+ node-height col-gap)))
                      (+ pad-y (* row (+ node-height row-gap))))]
              {:row-counts (assoc row-counts lid (inc row))
               :positioned-nodes (conj positioned-nodes
                                       (assoc node :layout {:x x
                                                            :y y
                                                            :width node-width
                                                            :height node-height
                                                            :column col
                                                            :row row}))}))
          {:row-counts {} :positioned-nodes []}
          (:nodes graph))
         max-x (reduce max (+ pad-x node-width)
                       (map (fn [n] (+ (get-in n [:layout :x]) (get-in n [:layout :width])))
                            positioned-nodes))
         max-y (reduce max (+ pad-y node-height)
                       (map (fn [n] (+ (get-in n [:layout :y]) (get-in n [:layout :height])))
                            positioned-nodes))
         canvas {:width (+ max-x pad-x)
                 :height (+ max-y 64)
                 :direction direction
                 :node-width node-width
                 :node-height node-height
                 :col-gap col-gap
                 :row-gap row-gap
                 :pad-x pad-x
                 :pad-y pad-y}
         result (assoc graph
                       :nodes positioned-nodes
                       :layout canvas)]
     (v/validate-graph! result validate-opts)
     result)))

;; ── Public Projection Entry Point ────────────────────────────────────────────

(defn- strip-internal-keys [node]
  (dissoc node ::label-priority))

(defn project-graph
  "Project ontology registries, connectors, Kotoba schemas, facts, EAVT datoms,
  RDF quads, external joins, and IPLD DAG-CBOR nodes into a normalized,
  deterministic, laid-out `ontology.graph/v1` structure."
  [input]
  (let [limits (v/validate-input! input)
        ref-attrs (collect-ref-attributes input)
        init-state {:limits limits
                    :nodes {}
                    :edges {}
                    :joins []
                    :entity-types {}
                    :observed-attr-values {}
                    :observed-typed-values {}}
        state (-> init-state
                  (cond-> (:ontology input) (project-ontology-registry (:ontology input)))
                  (cond-> (:connectors input) (project-connectors (:connectors input)))
                  (cond-> (:kotoba-schema input) (project-kotoba-schema (:kotoba-schema input)))
                  (cond-> (seq (:facts input)) (project-facts (:facts input)))
                  (cond-> (seq (:datoms input)) (project-datoms (:datoms input) ref-attrs))
                  (cond-> (seq (:quads input)) (project-rdf-quads (:quads input)))
                  (cond-> (seq (:ipld-nodes input)) (project-ipld-nodes (:ipld-nodes input)))
                  (cond-> (seq (:joins input)) (project-joins (:joins input))))
        nodes (vec (sort-by :id (map strip-internal-keys (vals (:nodes state)))))
        edges (vec (sort-by :id (vals (:edges state))))
        joins (vec (sort-by :id (:joins state)))
        layers (build-layers nodes)
        raw-basis (or (:basis input) {})
        root-cid (v/extract-cid (or (:root-cid raw-basis) (:root-link raw-basis)))
        all-cids (vec (sort (distinct (keep identity (concat (when root-cid [root-cid])
                                                             (map :cid nodes)
                                                             (map :cid edges))))))
        ;; Unverified projection never self-promotes basisCid to :verified
        cid-ver :syntax-only
        basis (cond-> {:schema-version schema-version
                       :codec (str (or (:codec raw-basis) "dag-cbor"))
                       :hash-alg (str (or (:hash-alg raw-basis) "sha2-256"))
                       :cid-verification cid-ver
                       :basis-cid-verification cid-ver
                       :graph-cid-verification :absent
                       :node-count (count nodes)
                       :edge-count (count edges)
                       :layer-count (count layers)
                       :join-count (count joins)
                       :cids all-cids
                       :bounds limits}
                root-cid (assoc :root-cid root-cid)
                (:id raw-basis) (assoc :id (str (:id raw-basis)))
                (:source raw-basis) (assoc :source (str (:source raw-basis)))
                (:snapshot-at raw-basis) (assoc :snapshot-at (str (:snapshot-at raw-basis)))
                (some? (:tx-id raw-basis)) (assoc :tx-id (:tx-id raw-basis)))
        graph {:schema/version schema-version
               :schema/kind schema-kind
               :basis basis
               :layers layers
               :nodes nodes
               :edges edges
               :joins joins}]
    (layout-graph graph (or (:layout input) {}))))

;; ── Normalized Filtering (Agent / Browser Equivalence incl. empty []) ────────

(defn- normalize-kind-filter [k]
  (let [kw (cond
             (keyword? k) k
             (string? k) (keyword k)
             :else nil)]
    (when-not (contains? v/valid-node-kinds kw)
      (v/fail! :invalid-kind
               (str "unsupported node kind filter: " (pr-str k))
               {:kind k :allowed (vec (sort (map name v/valid-node-kinds)))}))
    kw))

(defn filter-graph
  "Validate and filter a normalized graph by `:layers`, `:kinds` (strings or
  keywords, strictly validated against `valid-node-kinds`), and/or `:query`.

  Crucially distinguishes `nil` (no filter) from explicit empty `[]`: passing
  `{:layers []}` or `{:kinds []}` returns 0 nodes, 0 edges, and 0 joins,
  matching the interactive HTML viewer when all layer checkboxes are unchecked."
  ([graph params] (filter-graph graph params {}))
  ([graph {:keys [layers kinds query]} validate-opts]
   (v/validate-graph! graph validate-opts)
   (let [layer-set (when (some? layers) (set (map id-str layers)))
         kind-set (when (some? kinds) (set (map normalize-kind-filter kinds)))
         q (when-not (str/blank? query) (str/lower-case (str/trim query)))
         keep-node? (fn [n]
                      (and (or (nil? layer-set) (contains? layer-set (:layer n)))
                           (or (nil? kind-set) (contains? kind-set (:kind n)))
                           (or (nil? q)
                               (str/includes? (str/lower-case (str (:id n))) q)
                               (str/includes? (str/lower-case (str (:label n))) q)
                               (and (:cid n) (str/includes? (str/lower-case (str (:cid n))) q)))))
         kept-nodes (vec (filter keep-node? (:nodes graph)))
         kept-ids (set (map :id kept-nodes))
         kept-edges (vec (filter #(and (contains? kept-ids (:source %))
                                       (contains? kept-ids (:target %)))
                                 (:edges graph)))
         kept-joins (vec (filter #(and (contains? kept-ids (:from-node %))
                                       (contains? kept-ids (:to-node %)))
                                 (:joins graph)))
         kept-layers (build-layers kept-nodes)
         truncated? (or (boolean (get-in graph [:basis :truncated]))
                        (< (count kept-nodes) (count (:nodes graph))))
         updated (-> graph
                     (assoc :nodes kept-nodes
                            :edges kept-edges
                            :joins kept-joins
                            :layers kept-layers)
                     (update :basis (fn [b]
                                      (-> b
                                          (dissoc :graph-cid :stats :coverage :yataverse-layers)
                                          (assoc :graph-cid-verification :absent
                                                 :truncated truncated?
                                                 :node-count (count kept-nodes)
                                                 :edge-count (count kept-edges)
                                                 :layer-count (count kept-layers)
                                                 :join-count (count kept-joins))))))]
     (layout-graph updated (select-keys (:layout graph) [:direction :node-width :node-height :col-gap :row-gap :pad-x :pad-y])))))
