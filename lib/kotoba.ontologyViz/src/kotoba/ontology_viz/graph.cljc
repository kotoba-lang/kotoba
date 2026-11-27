(ns kotoba.ontology-viz.graph
  "Canonical ontology graph projection, external join coverage evaluation, and
  deterministic layered DAG layout compatible with Yataverse `ontology.graph/v1`."
  (:require [clojure.string :as str]
            [kotoba.ontology-viz.validate :as v]))

(def schema-version "ontology.graph/v1")
(def schema-kind "ontology.graph")

(def default-layer-specs
  "Canonical layer ordering and visual palette (neutral/semantic, zero DDS tokens)."
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

(defn- compact-iri-label [iri]
  (let [s (str iri)]
    (cond
      (str/includes? s "#") (let [frag (last (str/split s #"#"))]
                              (if (str/blank? frag) s frag))
      (str/includes? s "/") (let [seg (last (str/split s #"/"))]
                              (if (str/blank? seg) s seg))
      :else s)))

(defn- merge-node [existing incoming limits]
  (let [merged-attrs (merge (:attributes existing) (:attributes incoming))]
    (v/assert-attributes-count! limits (:id incoming) (count merged-attrs))
    (cond-> (merge existing incoming)
      (seq merged-attrs) (assoc :attributes merged-attrs)
      (and (:cid existing) (nil? (:cid incoming))) (assoc :cid (:cid existing))
      (and (:provenance existing) (:provenance incoming))
      (assoc :provenance (merge (:provenance existing) (:provenance incoming))))))

(defn- add-node [state node]
  (let [limits (:limits state)
        id (:id node)]
    (v/assert-label-length! limits :node/id id)
    (v/assert-label-length! limits :node/label (:label node))
    (when-let [attrs (:attributes node)]
      (v/assert-attributes-count! limits id (count attrs)))
    (let [nodes (:nodes state)
          updated (if-let [prev (get nodes id)]
                    (assoc nodes id (merge-node prev node limits))
                    (let [next-nodes (assoc nodes id node)]
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

(defn- record-attr-value [state attr val]
  (if (and (some? attr) (some? val))
    (update-in state [:observed-attr-values (kw-str attr)] (fnil conj []) val)
    state))

;; ── Projectors per source domain ─────────────────────────────────────────────

(defn- project-ontology-registry [state onto]
  (reduce
   (fn [st ot]
     (let [type-id (str "type:" (id-str (:id ot)))
           type-label (or (:name ot) (id-str (:id ot)))
           layer (layer-str (:layer ot) "ontology")
           cid (v/extract-cid (:cid ot))
           attrs (or (:attributes ot) {})
           key-attrs (mapv kw-str (or (:key ot) []))
           st1 (add-node st (cond-> {:id type-id
                                     :label type-label
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
                           :kind :attribute
                           :layer "attribute"
                           :attributes {:value-type (id-str attr-type)
                                        :key? is-key?
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
                                     :kind :connector
                                     :layer (layer-str (:layer c) "connector")
                                     :attributes (cond-> {:object-type (id-str (:object-type c))
                                                          :status (id-str (or (:status c) :unknown))}
                                                   safe-repo (assoc :repo safe-repo))
                                     :provenance (cond-> {:connector-id (id-str (:id c))
                                                          :status (id-str (or (:status c) :unknown))}
                                                   safe-repo (assoc :repo safe-repo))}
                              cid (assoc :cid cid)))
           ;; Ensure target object-type node exists even if only connectors were supplied
           st2 (if (contains? (:nodes st1) target-id)
                 st1
                 (add-node st1 {:id target-id
                                :label (id-str (:object-type c))
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
                                 :kind :attribute
                                 :layer "attribute"
                                 :attributes (cond-> {:value-type vtype
                                                      :cardinality card}
                                               (:db/doc d) (assoc :doc (:db/doc d)))})]
           (if owner-id
             (-> st1
                 (add-node {:id owner-id
                            :label ns-part
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
           node-id (str "entity:" (id-str ent-key))
           payload (dissoc fact :ontology/type :ontology/source :ontology/fetched-at :ontology/confidence)
           provenance (cond-> {}
                        otype (assoc :type (id-str otype))
                        src (assoc :source (id-str src))
                        (:ontology/fetched-at fact) (assoc :fetched-at (str (:ontology/fetched-at fact)))
                        (contains? fact :ontology/confidence) (assoc :confidence (:ontology/confidence fact)))
           st1 (add-node st (cond-> {:id node-id
                                     :label (str (or (:name fact) (:title fact) (id-str ent-key)))
                                     :kind :entity
                                     :layer "instance"
                                     :attributes (into {} (map (fn [[k val]] [(kw-str k) (if (v/ipld-link? val) (v/extract-cid val) (str val))]) payload))
                                     :provenance provenance}
                              cid (assoc :cid cid)))
           st2 (reduce-kv (fn [acc k val] (record-attr-value acc k val)) st1 payload)
           st3 (if otype
                 (let [t-id (str "type:" (id-str otype))]
                   (-> st2
                       (add-node {:id t-id :label (id-str otype) :kind :object-type :layer "ontology"})
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
                       (add-node {:id c-id :label (id-str src) :kind :connector :layer "connector"})
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

(defn- normalize-datom [d]
  (if (vector? d)
    {:e (nth d 0)
     :a (nth d 1)
     :v (nth d 2)
     :tx (when (>= (count d) 4) (nth d 3))
     :added? (if (>= (count d) 5) (nth d 4) true)}
    {:e (:e d)
     :a (:a d)
     :v (:v d)
     :tx (:tx d)
     :added? (if (contains? d :added?) (:added? d) true)}))

(defn- project-datoms [state datoms]
  (let [normalized (filter :added? (map normalize-datom datoms))
        known-entities (set (map #(id-str (:e %)) normalized))]
    (reduce
     (fn [st {:keys [e a v tx]}]
       (let [e-str (id-str e)
             e-node-id (str "entity:" e-str)
             a-str (kw-str a)
             st1 (-> st
                     (add-node {:id e-node-id
                                :label e-str
                                :kind :entity
                                :layer "instance"})
                     (record-attr-value a v))]
         (cond
           (v/ipld-link? v)
           (let [cid (v/extract-cid v)
                 t-id (str "ipld:" cid)]
             (-> st1
                 (add-node {:id t-id
                            :label (str "IPLD " (subs cid 0 (min 14 (count cid))))
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

           (and (or (keyword? v) (string? v))
                (contains? known-entities (id-str v))
                (not= e-str (id-str v)))
           (let [t-id (str "entity:" (id-str v))]
             (-> st1
                 (add-node {:id t-id :label (id-str v) :kind :entity :layer "instance"})
                 (add-edge {:id (str "edge:" e-node-id "->" t-id ":" (id-str a))
                            :source e-node-id
                            :target t-id
                            :label a-str
                            :kind :datom-ref
                            :layer "instance"
                            :metadata (cond-> {:attribute a-str} tx (assoc :tx tx))})))

           :else
           (add-node st1 {:id e-node-id
                          :label e-str
                          :kind :entity
                          :layer "instance"
                          :attributes {a-str (str v)}}))))
     state
     normalized)))

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
           st1 (-> st
                   (add-node (cond-> {:id s-id
                                      :label (compact-iri-label s-str)
                                      :kind (if (= :blank (rdf-term-kind subj)) :rdf-blank :rdf-resource)
                                      :layer layer
                                      :attributes {:iri s-str}}
                               graph-name (assoc-in [:provenance :named-graph] graph-name)))
                   (record-attr-value p-str o-str))]
       (if (or (= o-kind :iri) (= o-kind :blank))
         (let [o-id (str "rdf:" o-str)]
           (-> st1
               (add-node (cond-> {:id o-id
                                  :label (compact-iri-label o-str)
                                  :kind (if (= o-kind :blank) :rdf-blank :rdf-resource)
                                  :layer layer
                                  :attributes {:iri o-str}}
                           graph-name (assoc-in [:provenance :named-graph] graph-name)))
               (add-edge {:id (str "edge:" s-id "->" o-id ":" p-label)
                          :source s-id
                          :target o-id
                          :label p-label
                          :kind :rdf-predicate
                          :layer layer
                          :metadata (cond-> {:predicate p-str}
                                      graph-name (assoc :graph graph-name))})))
         (add-node st1 {:id s-id
                        :label (compact-iri-label s-str)
                        :kind (if (= :blank (rdf-term-kind subj)) :rdf-blank :rdf-resource)
                        :layer layer
                        :attributes {p-label o-str}}))))
   state
   quads))

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
             label (or (:label entry)
                       (when (map? node-val) (or (get node-val "name") (get node-val :name)))
                       (str "IPLD " (subs cid 0 (min 14 (count cid)))))
             scalar-attrs (if (map? node-val)
                            (into {}
                                  (keep (fn [[k v]]
                                          (when (or (string? v) (number? v) (boolean? v) (keyword? v))
                                            [(id-str k) (str v)])))
                                  node-val)
                            {})
             st1 (add-node st {:id node-id
                               :label (str label)
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

;; ── External Join Coverage Evaluation ────────────────────────────────────────

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

(defn- round-int [x]
  #?(:clj (Math/round (double x))
     :cljs (js/Math.round x)))

(defn- round4 [x]
  (/ (round-int (* (double x) 10000.0)) 10000.0))

(defn evaluate-join
  "Pure evaluator for external join coverage (e.g. `:jurisdiction/code` <->
  `:country/iso3`) with match rules, explicit correspondence mapping, and
  exclusion rules."
  ([join-spec] (evaluate-join join-spec {}))
  ([join-spec observed-attr-values]
   (let [from-attr (kw-str (:from-attr join-spec))
         to-attr (kw-str (:to-attr join-spec))
         join-id (or (:id join-spec) (str "join:" (id-str (:from-attr join-spec)) "->" (id-str (:to-attr join-spec))))
         rule (or (:match-rule join-spec) (if (seq (:mapping join-spec)) :mapping :exact))
         mapping (into {} (map (fn [[k v]] [(str k) (str v)])) (or (:mapping join-spec) {}))
         exclude-set (set (concat (:exclude join-spec) (:exclude-values join-spec)))
         src-raw (distinct (or (:source-values join-spec)
                               (get observed-attr-values from-attr)
                               []))
         tgt-raw (distinct (or (:target-values join-spec)
                               (get observed-attr-values to-attr)
                               []))
         tgt-index (reduce
                    (fn [m tv]
                      (let [k (case rule
                                :exact-uppercase (str/upper-case (str tv))
                                :exact-lowercase (str/lower-case (str tv))
                                (str tv))]
                        (assoc m k (str tv))))
                    {}
                    tgt-raw)
         {:keys [matched unmatched excluded]}
         (reduce
          (fn [acc sv]
            (let [s (str sv)]
              (if (excluded-value? exclude-set sv)
                (update acc :excluded conj s)
                (let [norm (normalize-join-val rule mapping sv)
                      hit (cond
                            (= rule :prefix)
                            (first (filter #(or (str/starts-with? (str %) norm)
                                                (str/starts-with? norm (str %)))
                                           tgt-raw))
                            :else
                            (get tgt-index norm))]
                  (if (some? hit)
                    (update acc :matched conj [s (str hit)])
                    (update acc :unmatched conj s))))))
          {:matched [] :unmatched [] :excluded []}
          src-raw)
         total (count src-raw)
         excl-n (count excluded)
         eligible (- total excl-n)
         match-n (count matched)
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
              :cardinality (or (:cardinality join-spec) :many-to-one)
              :exclude (vec (sort (map str exclude-set)))
              :matched-count match-n
              :unmatched-count unmatch-n
              :excluded-count excl-n
              :total-source-count total
              :eligible-count eligible
              :coverage coverage
              :status status
              :matched-pairs (vec (take 50 (sort matched)))
              :unmatched-values (vec (take 50 (sort unmatched)))
              :excluded-values (vec (take 50 (sort excluded)))}
       (:description join-spec) (assoc :description (:description join-spec))))))

(defn- project-joins [state joins]
  (reduce
   (fn [st jspec]
     (let [evaluated (evaluate-join jspec (:observed-attr-values st))
           from-id (:from-node evaluated)
           to-id (:to-node evaluated)
           cov-label (if (some? (:coverage evaluated))
                       (str "join " (round-int (* 100.0 (double (:coverage evaluated)))) "%")
                       "join")
           st1 (if (contains? (:nodes st) from-id)
                 st
                 (add-node st {:id from-id
                               :label (:from-attr evaluated)
                               :kind (if (str/starts-with? from-id "type:") :object-type :attribute)
                               :layer (if (str/starts-with? from-id "type:") "ontology" "attribute")}))
           st2 (if (contains? (:nodes st1) to-id)
                 st1
                 (add-node st1 {:id to-id
                                :label (:to-attr evaluated)
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

(defn- build-layers [nodes]
  (let [counts (frequencies (map :layer nodes))
        known-keys (keys default-layer-specs)
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
  "Assign deterministic layered DAG coordinates to every node and compute
  canvas geometry. Supports `:direction` `:horizontal` (default) or `:vertical`."
  ([graph] (layout-graph graph {}))
  ([graph {:keys [direction node-width node-height col-gap row-gap pad-x pad-y]
           :or {direction :horizontal
                node-width 216
                node-height 68
                col-gap 92
                row-gap 28
                pad-x 40
                pad-y 84}}]
   (let [layers (:layers graph)
         layer-index (into {} (map-indexed (fn [i l] [(:id l) i]) layers))
         grouped (group-by :layer (:nodes graph))
         positioned-nodes
         (vec
          (mapcat
           (fn [{:keys [id]}]
             (let [col (get layer-index id 0)
                   members (sort-by :id (get grouped id []))]
               (map-indexed
                (fn [row node]
                  (let [x (if (= direction :vertical)
                            (+ pad-x (* row (+ node-width row-gap)))
                            (+ pad-x (* col (+ node-width col-gap))))
                        y (if (= direction :vertical)
                            (+ pad-y (* col (+ node-height col-gap)))
                            (+ pad-y (* row (+ node-height row-gap))))]
                    (assoc node :layout {:x x
                                         :y y
                                         :width node-width
                                         :height node-height
                                         :column col
                                         :row row})))
                members)))
           layers))
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
                 :pad-y pad-y}]
     (assoc graph
            :nodes positioned-nodes
            :layout canvas))))

;; ── Public Projection Entry Point ────────────────────────────────────────────

(defn project-graph
  "Project ontology registries, connectors, Kotoba schemas, facts, EAVT datoms,
  RDF quads, external joins, and IPLD DAG-CBOR nodes into a normalized,
  deterministic, laid-out `ontology.graph/v1` structure."
  [input]
  (let [limits (v/validate-input! input)
        init-state {:limits limits
                    :nodes {}
                    :edges {}
                    :joins []
                    :observed-attr-values {}}
        state (-> init-state
                  (cond-> (:ontology input) (project-ontology-registry (:ontology input)))
                  (cond-> (:connectors input) (project-connectors (:connectors input)))
                  (cond-> (:kotoba-schema input) (project-kotoba-schema (:kotoba-schema input)))
                  (cond-> (seq (:facts input)) (project-facts (:facts input)))
                  (cond-> (seq (:datoms input)) (project-datoms (:datoms input)))
                  (cond-> (seq (:quads input)) (project-rdf-quads (:quads input)))
                  (cond-> (seq (:ipld-nodes input)) (project-ipld-nodes (:ipld-nodes input)))
                  (cond-> (seq (:joins input)) (project-joins (:joins input))))
        nodes (vec (sort-by :id (vals (:nodes state))))
        edges (vec (sort-by :id (vals (:edges state))))
        joins (vec (sort-by :id (:joins state)))
        layers (build-layers nodes)
        raw-basis (or (:basis input) {})
        root-cid (v/extract-cid (or (:root-cid raw-basis) (:root-link raw-basis)))
        all-cids (vec (sort (distinct (keep identity (concat (when root-cid [root-cid])
                                                             (map :cid nodes)
                                                             (map :cid edges))))))
        basis (cond-> {:schema-version schema-version
                       :codec (str (or (:codec raw-basis) "dag-cbor"))
                       :hash-alg (str (or (:hash-alg raw-basis) "sha2-256"))
                       :node-count (count nodes)
                       :edge-count (count edges)
                       :layer-count (count layers)
                       :join-count (count joins)
                       :cids all-cids
                       :bounds limits}
                root-cid (assoc :root-cid root-cid)
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

(defn filter-graph
  "Filter a normalized graph by `:layers` (set/seq of layer IDs), `:kinds`
  (set/seq of node kinds), and/or `:query` (case-insensitive substring over
  node id, label, or CID). Re-runs layout cleanly on the filtered subgraph."
  [graph {:keys [layers kinds query]}]
  (let [layer-set (when (seq layers) (set (map id-str layers)))
        kind-set (when (seq kinds) (set kinds))
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
        kept-layers (build-layers kept-nodes)
        updated (-> graph
                    (assoc :nodes kept-nodes
                           :edges kept-edges
                           :layers kept-layers)
                    (update :basis assoc
                            :node-count (count kept-nodes)
                            :edge-count (count kept-edges)
                            :layer-count (count kept-layers)))]
    (layout-graph updated (select-keys (:layout graph) [:direction :node-width :node-height :col-gap :row-gap :pad-x :pad-y]))))
