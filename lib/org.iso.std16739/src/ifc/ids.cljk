(ns ifc.ids
  "Portable buildingSMART IDS 1.0 validation over an `ifc.core` exchange
  document. XML transport is isolated in `ifc.ids.xml`; this namespace owns
  deterministic facet evaluation and reports."
  (:require [kotoba.lang.text :as string]))

(def contract-version 1)
(def facet-types #{:entity :attribute :property :classification :material :part-of})
(def cardinalities #{:required :optional :prohibited})

(defn restriction
  "Create an IDS value restriction. Supported keys are `:value`, `:values`,
  `:pattern`, inclusive/exclusive numeric bounds, and string length bounds."
  [value-or-map]
  (if (map? value-or-map) value-or-map {:value value-or-map}))

(defn facet [{:keys [type cardinality] :as value}]
  (when-not (contains? facet-types type)
    (throw (ex-info "unsupported IDS facet" {:facet value})))
  (when (and cardinality (not (contains? cardinalities cardinality)))
    (throw (ex-info "invalid IDS facet cardinality" {:facet value})))
  (update value :cardinality #(or % :required)))

(defn specification
  [{:keys [name ifc-versions applicability requirements min-occurs max-occurs]
    :as value}]
  (when-not (and (string? name) (some? applicability))
    (throw (ex-info "invalid IDS specification" {:specification value})))
  {:ids.specification/name name
   :ids.specification/ifc-versions (set (or ifc-versions ["IFC4" "IFC4X3_ADD2"]))
   :ids.specification/min-occurs (if (nil? min-occurs) 1 min-occurs)
   :ids.specification/max-occurs (or max-occurs :unbounded)
   :ids.specification/applicability (mapv facet applicability)
   :ids.specification/requirements (mapv facet requirements)})

(defn document [{:keys [title version author specifications] :as value}]
  (when-not (and (string? title) (seq specifications))
    (throw (ex-info "invalid IDS document" {:document value})))
  {:ids/version (or version "1.0") :ids/contract-version contract-version
   :ids/title title :ids/author author
   :ids/specifications (mapv specification specifications)})

(def numeric-pattern #"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?")

(defn- parsed-number [value]
  (cond
    (number? value) (double value)
    (and (string? value) (re-matches numeric-pattern value))
    (#?(:clj Double/parseDouble :cljs js/parseFloat) value)
    :else nil))

(defn- lexical-value [value]
  (cond
    (true? value) "true"
    (false? value) "false"
    (keyword? value) (string/upper (name value))
    (nil? value) nil
    :else (str value)))

(defn- numeric-tolerance [_ expected]
  (* 1.0e-6 (inc (#?(:clj Math/abs :cljs js/Math.abs) expected))))

(defn- floating-slack [a b]
  (* 1.0e-15 (max 1.0 (#?(:clj Math/abs :cljs js/Math.abs) a)
                         (#?(:clj Math/abs :cljs js/Math.abs) b))))

(defn- values-equivalent? [actual expected]
  (let [a (parsed-number actual) b (parsed-number expected)]
    (cond
      (and (some? a) (some? b))
      (<= (#?(:clj Math/abs :cljs js/Math.abs) (- a b))
          (+ (numeric-tolerance a b) (floating-slack a b)))
      :else (= (lexical-value actual) (lexical-value expected)))))

(defn- numeric-bound? [operator actual expected]
  (let [actual (parsed-number actual) expected (parsed-number expected)]
    (and (some? actual) (some? expected) (operator actual expected))))

(defn matches-restriction?
  [actual value-restriction]
  (if (nil? value-restriction)
    true
    (let [{:keys [value values pattern patterns min-inclusive max-inclusive
                  min-exclusive max-exclusive length min-length max-length]}
          (restriction value-restriction)
          ;; xs:restriction combines multiple xs:pattern facets with OR --
          ;; a value need only match one of them. `:pattern` (singular) and
          ;; `:patterns` (a collection) are both accepted so existing
          ;; single-pattern callers keep working unchanged.
          all-patterns (cond-> (vec patterns) pattern (conj pattern))
          text (when (some? actual) (str actual))]
      (and (if (contains? (restriction value-restriction) :value)
             (values-equivalent? actual value) true)
           (if (seq values) (boolean (some #(values-equivalent? actual %) values)) true)
           (if (seq all-patterns)
             (and text (boolean (some #(re-matches (re-pattern %) (lexical-value actual))
                                      all-patterns)))
             true)
           (if (some? min-inclusive) (numeric-bound? >= actual min-inclusive) true)
           (if (some? max-inclusive) (numeric-bound? <= actual max-inclusive) true)
           (if (some? min-exclusive) (numeric-bound? > actual min-exclusive) true)
           (if (some? max-exclusive) (numeric-bound? < actual max-exclusive) true)
           (if (some? length) (and text (= (count text) length)) true)
           (if (some? min-length) (and text (>= (count text) min-length)) true)
           (if (some? max-length) (and text (<= (count text) max-length)) true)))))

(def quantity-data-types
  {:length :ifclengthmeasure :area :ifcareameasure :volume :ifcvolumemeasure
   :count :ifccountmeasure :weight :ifcmassmeasure :time :ifctimemeasure
   :number :ifcnumericmeasure})

;; Attribute positions are the flattened EXPRESS order used by Part 21.  The
;; common supertypes cover all rooted objects; the explicit entries cover
;; resource/process entities which are valid IDS targets even though they are
;; not IfcProducts.
(def ^:private root-attribute-indexes
  {"GLOBALID" 0 "OWNERHISTORY" 1 "NAME" 2 "DESCRIPTION" 3})

(def ^:private raw-attribute-indexes
  {:ifctasktime
   {"NAME" 0 "DATAORIGIN" 1 "USERDEFINEDDATAORIGIN" 2 "DURATIONTYPE" 3
    "SCHEDULEDURATION" 4 "SCHEDULESTART" 5 "SCHEDULEFINISH" 6
    "EARLYSTART" 7 "EARLYFINISH" 8 "LATESTART" 9 "LATEFINISH" 10
    "FREEFLOAT" 11 "TOTALFLOAT" 12 "ISCRITICAL" 13 "STATUSTIME" 14
    "ACTUALDURATION" 15 "ACTUALSTART" 16 "ACTUALFINISH" 17
    "REMAININGTIME" 18 "COMPLETION" 19}
   :ifcsurfacestylerefraction {"REFRACTIONINDEX" 0 "DISPERSIONFACTOR" 1}
   :ifcclassification
   {"SOURCE" 0 "EDITION" 1 "EDITIONDATE" 2 "NAME" 3 "DESCRIPTION" 4
    "LOCATION" 5 "REFERENCETOKENS" 6}
   :ifcperson
   {"IDENTIFICATION" 0 "FAMILYNAME" 1 "GIVENNAME" 2 "MIDDLENAMES" 3
    "PREFIXTITLES" 4 "SUFFIXTITLES" 5 "ROLES" 6 "ADDRESSES" 7}
   :ifcquantitycount
   {"NAME" 0 "DESCRIPTION" 1 "UNIT" 2 "COUNTVALUE" 3 "FORMULA" 4}
   :ifcmateriallayerset
   {"MATERIALLAYERS" 0 "LAYERSETNAME" 1 "DESCRIPTION" 2}
   :ifcpresentationlayerwithstyle
   {"NAME" 0 "DESCRIPTION" 1 "ASSIGNEDITEMS" 2 "IDENTIFIER" 3
    "LAYERON" 4 "LAYERFROZEN" 5 "LAYERBLOCKED" 6 "LAYERSTYLES" 7}
   :ifcrelconnectspathelements
   (merge root-attribute-indexes
          {"CONNECTIONGEOMETRY" 4 "RELATINGELEMENT" 5 "RELATEDELEMENT" 6
           "RELATINGPRIORITIES" 7 "RELATEDPRIORITIES" 8
           "RELATEDCONNECTIONTYPE" 9 "RELATINGCONNECTIONTYPE" 10})
   :ifccartesianpoint {"COORDINATES" 0}
   :ifcsurfacestylerendering
   {"SURFACECOLOUR" 0 "TRANSPARENCY" 1 "DIFFUSECOLOUR" 2
    "TRANSMISSIONCOLOUR" 3 "DIFFUSEREFLECTIONCOLOUR" 4
    "REFLECTIONCOLOUR" 5 "SPECULARCOLOUR" 6
    "SPECULARHIGHLIGHT" 7 "REFLECTANCEMETHOD" 8}
   :ifctask
   (merge root-attribute-indexes
          {"OBJECTTYPE" 4 "IDENTIFICATION" 5 "LONGDESCRIPTION" 6
           "STATUS" 7 "WORKMETHOD" 8 "ISMILESTONE" 9 "PRIORITY" 10
           "TASKTIME" 11 "PREDEFINEDTYPE" 12})
   :ifcstairflight
   (merge root-attribute-indexes
          {"OBJECTTYPE" 4 "OBJECTPLACEMENT" 5 "REPRESENTATION" 6 "TAG" 7
           "NUMBEROFRISERS" 8 "NUMBEROFTREADS" 9 "RISERHEIGHT" 10
           "TREADLENGTH" 11 "PREDEFINEDTYPE" 12})
   :ifcwall (merge root-attribute-indexes {"OBJECTTYPE" 4 "TAG" 7 "PREDEFINEDTYPE" 8})
   :ifcwallstandardcase
   (merge root-attribute-indexes {"OBJECTTYPE" 4 "TAG" 7 "PREDEFINEDTYPE" 8})
   :ifcbeam (merge root-attribute-indexes {"OBJECTTYPE" 4 "TAG" 7 "PREDEFINEDTYPE" 8})
   :ifcslab (merge root-attribute-indexes {"OBJECTTYPE" 4 "TAG" 7 "PREDEFINEDTYPE" 8})
   :ifcspace (merge root-attribute-indexes {"OBJECTTYPE" 4 "PREDEFINEDTYPE" 9})
   :ifcfurniture
   (merge root-attribute-indexes {"OBJECTTYPE" 4 "TAG" 7 "PREDEFINEDTYPE" 8})
   :ifcinventory
   (merge root-attribute-indexes {"OBJECTTYPE" 4 "PREDEFINEDTYPE" 5})
   :ifcwalltype
   (merge root-attribute-indexes {"ELEMENTTYPE" 8 "PREDEFINEDTYPE" 9})
   :ifctasktype
   (merge root-attribute-indexes {"PROCESSTYPE" 8 "PREDEFINEDTYPE" 9})})

(defn- raw-null? [value]
  (or (nil? value) (= :$ value) (= :* value)))

(defn- valid-attribute-value? [value]
  (and (not (raw-null? value))
       (not (#{:unknown :u} value))
       (not (and (string? value) (empty? value)))
       (not (and (sequential? value)
                 (or (empty? value)
                     (and (= :list (first value)) (= 1 (count value))))))))

(defn- raw-object [entity]
  {:id (:id entity)
   :ifc/entity-type (:type entity)
   :ids/raw-args (:args entity)
   :ids/attribute-indexes
   (merge (when (string/starts-with? (name (:type entity)) "ifc")
            root-attribute-indexes)
          (get raw-attribute-indexes (:type entity)))})

(defn- validation-objects [ifc-document]
  (let [classifications (:ifc/classifications-by-object ifc-document)
        raw (into {}
                  (map (fn [entity]
                         [(:id entity)
                          (assoc (raw-object entity) :classifications
                                 (get classifications (:id entity) []))]))
                  (:ifc/raw-entities ifc-document))
        spatial (when-let [project (:ifc/project ifc-document)]
                  (tree-seq #(seq (:children %)) :children project))
        elements (:ifc/elements ifc-document)
        rich (concat spatial (:ifc/groups ifc-document) elements
                     (keep :type-object elements))]
    (->> rich
         (reduce (fn [objects object]
                   (update objects (:id object) merge
                           (assoc object :ids/units (:ifc/units ifc-document)))) raw)
         vals
         (filter #(or (:ifc/entity-type %) (:type %) (:kind %)))
         (sort-by :id)
         vec)))

(defn- property-values [element]
  (let [property-sets (merge (:property-sets (:type-object element))
                             (:property-sets element))]
   (concat
   (for [[set-name property-set] property-sets
         [property-name property] (:properties property-set)]
     {:set set-name :name property-name
      :value (cond
               (contains? property :value) (:value property)
               (= :bounded (:kind property))
               (remove nil? [(:lower property) (:upper property) (:set-point property)])
               :else (:values property))
      :data-type (:value-type property) :typed-values (:typed-values property)
      :unit (:unit property) :source :property})
   (for [[set-name quantity-set] (:quantity-sets element)
         [quantity-name quantity] (:quantities quantity-set)]
     {:set set-name :name quantity-name :value (:value quantity)
      :data-type (get quantity-data-types (:kind quantity) (:kind quantity))
      :source :quantity}))))

(def ^:private measure-unit-types
  {:ifclengthmeasure :lengthunit :ifcareameasure :areaunit
   :ifcvolumemeasure :volumeunit :ifctimemeasure :timeunit
   :ifcmassmeasure :massunit})

(defn- normalized-property-value [element property value]
  (if (number? value)
    (let [unit-type (get measure-unit-types (:data-type property))
          unit (or (:unit property) (get (:ids/units element) unit-type))
          scale (or (:scale unit) 1.0)]
      (* value scale))
    value))

(defn- property-requirement-matches? [element facet property]
  (let [typed-values (:typed-values property)
        values (if (seq typed-values)
                 (keep (fn [{:keys [value value-type]}]
                         (when (or (nil? (:data-type facet))
                                   (= (:data-type facet) value-type)) value))
                       typed-values)
                 (let [value (:value property)]
                   (if (sequential? value) value [value])))
        data-type-pass? (if (seq typed-values)
                          (seq values)
                          (or (nil? (:data-type facet))
                              (= (:data-type facet) (:data-type property))))]
    (and data-type-pass?
         (if (:value facet)
           (boolean
            (some #(matches-restriction?
                    (normalized-property-value element property %)
                    (:value facet)) values))
           ;; no value restriction: existence alone is not enough per IDS --
           ;; an empty string or a logical unknown is treated as "not set"
           ;; and must not satisfy the requirement.
           (boolean (some valid-attribute-value? values))))))

(defn- material-values [element]
  (let [assignment (or (:material element) (get-in element [:type-object :material]))]
    (letfn [(values [node]
              (when node
                (concat
                 (remove nil? [(:name node) (:category node)])
                 (values (:material node))
                 (values (:layer-set node))
                 (mapcat values (:layers node))
                 (mapcat values (:materials node))
                 (mapcat values (:constituents node))
                 (mapcat values (:profiles node)))))]
      (values assignment))))

(defn- classification-values [element]
  (let [occurrence (:classifications element)
        occurrence-systems (set (keep #(get-in % [:source :name]) occurrence))
        inherited (remove #(contains? occurrence-systems (get-in % [:source :name]))
                          (get-in element [:type-object :classifications]))]
    (mapcat (fn [classification]
              (let [values (or (seq (:identification-path classification))
                               [(:identification classification)])]
                (map (fn [value]
                       {:system (get-in classification [:source :name])
                        :value value :name (:name classification)})
                     values)))
            (concat occurrence inherited))))

(defn- spatial-index [project]
  (into {}
        (map (juxt :id identity))
        (tree-seq #(seq (:children %)) :children project)))

(defn- ref-id [value]
  (when (and (vector? value) (= :ref (first value))) (second value)))

(defn- refs [value]
  (keep ref-id (if (and (vector? value) (= :list (first value))) (rest value) [])))

(defn- relation-index [entities]
  (reduce
   (fn [index entity]
     (let [args (:args entity)
           [relation children parent]
           (case (:type entity)
             :ifcrelaggregates [:IFCRELAGGREGATES (refs (get args 5)) (ref-id (get args 4))]
             :ifcrelnests [:IFCRELNESTS (refs (get args 5)) (ref-id (get args 4))]
             :ifcrelcontainedinspatialstructure
             [:IFCRELCONTAINEDINSPATIALSTRUCTURE (refs (get args 4)) (ref-id (get args 5))]
             :ifcrelassignstogroup [:IFCRELASSIGNSTOGROUP (refs (get args 4)) (ref-id (get args 6))]
             nil)]
       (if (and relation parent)
         (reduce #(assoc-in %1 [relation %2] parent) index children)
         index)))
   {} entities))

(defn- parent-chain [parents id]
  (loop [current id result [] seen #{}]
    (if-let [parent (get parents current)]
      (if (contains? seen parent) result
          (recur parent (conj result parent) (conj seen parent)))
      result)))

(defn- part-of-objects [element context facet]
  (let [relation (:relation facet)
        relations (::relations context)
        ids (if relation
              (parent-chain (get relations relation {}) (:id element))
              (mapcat #(parent-chain % (:id element)) (vals relations)))]
    (keep context ids)))

(defn- entity-name [element]
  (let [value (-> (or (:ifc/entity-type element) (:ifc/type element)
                      (:type element) (:kind element))
                  name string/upper)]
    (if (string/starts-with? value "IFC") value (str "IFC" value))))

(declare attribute-value)

(defn- defined-predefined-type [value user-defined]
  (when-not (or (raw-null? value) (= :notdefined value))
    (if (= :userdefined value) user-defined value)))

(defn- effective-predefined-type [element]
  (or (defined-predefined-type
       (or (:predefined-type element) (attribute-value element "PREDEFINEDTYPE"))
       (or (:object-type element) (attribute-value element "OBJECTTYPE")
           (attribute-value element "ELEMENTTYPE")
           (attribute-value element "PROCESSTYPE")))
      (let [type-object (:type-object element)]
        (defined-predefined-type
         (:predefined-type type-object)
         (or (:element-type type-object) (:process-type type-object))))))

(defn- predefined-lexical [value]
  (cond
    (keyword? value) (string/upper (name value))
    (some? value) (str value)
    :else nil))

(defn- predefined-values [element]
  (remove nil?
          [(predefined-lexical (or (:predefined-type element)
                                   (attribute-value element "PREDEFINEDTYPE")))
           (predefined-lexical (effective-predefined-type element))]))

(defn- attribute-pairs [element]
  (let [raw-args (:ids/raw-args element)]
    (concat
     (for [[attribute index] (:ids/attribute-indexes element)
           :let [value (get raw-args index)]
           :when (not (raw-null? value))]
       [attribute value])
     (remove (comp raw-null? second)
             [["NAME" (:name element)] ["GLOBALID" (:global-id element)]
              ["DESCRIPTION" (:description element)] ["OBJECTTYPE" (:object-type element)]
              ["TAG" (:tag element)] ["PREDEFINEDTYPE" (:predefined-type element)]]))))

(defn- matching-attributes [element facet]
  (let [name-restriction (or (:name-restriction facet)
                             (when (some? (:name facet)) {:value (:name facet)}))
        name-restriction (if (contains? name-restriction :value)
                           (update name-restriction :value
                                   #(string/upper (str %)))
                           name-restriction)]
    (filter (fn [[attribute _]]
              (let [canonical (get {"GLOBALID" "GlobalId"
                                    "OWNERHISTORY" "OwnerHistory"
                                    "PREDEFINEDTYPE" "PredefinedType"
                                    "OBJECTTYPE" "ObjectType"
                                    "LAYERSETNAME" "LayerSetName"}
                                   attribute
                                   (string/capitalize (string/lower attribute)))]
                (or (matches-restriction? attribute name-restriction)
                    (matches-restriction? canonical name-restriction))))
            (attribute-pairs element))))

(defn- attribute-value [element attribute-name]
  (some (fn [[attribute value]]
          (when (= attribute (string/upper (str attribute-name))) value))
        (attribute-pairs element)))

(declare facet-matches?)

(defn- base-facet-matches? [element spatial facet]
  (case (:type facet)
    :entity
    (and (matches-restriction? (entity-name element) (:name facet))
         (if (:predefined-type facet)
           (boolean (some #(matches-restriction? % (:predefined-type facet))
                          (predefined-values element)))
           true))

    :attribute
    (boolean
     (some (fn [[_ actual]]
             (and (valid-attribute-value? actual)
                  (or (nil? (:value facet))
                      ;; IDS value restrictions apply only to simple values.
                      (and (not (coll? actual))
                           (matches-restriction? actual (:value facet))))))
           (matching-attributes element facet)))

    :property
    (let [sets (->> (property-values element)
                    (filter #(matches-restriction? (:set %) (:property-set facet)))
                    (group-by :set))]
      (and (seq sets)
           (every? (fn [[_ properties]]
                     (let [matching (filter #(matches-restriction? (:name %) (:name facet))
                                            properties)]
                       (and (seq matching)
                            (every? #(property-requirement-matches? element facet %)
                                    matching))))
                   sets)))

    :classification
    (boolean
     (some #(and (matches-restriction? (:system %) (:system facet))
                 (matches-restriction? (:value %) (:value facet))
                 (if (:name facet) (matches-restriction? (:name %) (:name facet)) true))
           (classification-values element)))

    :material
    (boolean (some #(matches-restriction? % (:value facet))
                   (material-values element)))

    :part-of
    (boolean
     (some (fn [whole]
             (if-let [entity (:entity facet)]
               (facet-matches? whole spatial (assoc entity :type :entity)) true))
           (part-of-objects element spatial facet)))
    false))

(defn facet-matches? [element spatial facet]
  (let [matches? (base-facet-matches? element spatial facet)]
    (if (= :prohibited (:cardinality facet)) (not matches?) matches?)))

(defn- facet-present? [element spatial facet]
  (case (:type facet)
    :entity true
    :attribute (boolean (seq (matching-attributes element facet)))
    :property
    (boolean
     (some #(and (matches-restriction? (:set %) (:property-set facet))
                 (matches-restriction? (:name %) (:name facet)))
           (property-values element)))
    :classification
    (boolean (seq (classification-values element)))
    :material (seq (material-values element))
    :part-of (boolean (seq (part-of-objects element spatial facet)))
    false))

(defn- requirement-result [element spatial requirement]
  (let [base-match? (base-facet-matches? element spatial requirement)
        cardinality (:cardinality requirement)
        pass? (case cardinality
                :prohibited (not base-match?)
                :optional (or (not (facet-present? element spatial requirement)) base-match?)
                :required base-match?)]
    {:ids.requirement/type (:type requirement)
     :ids.requirement/cardinality cardinality
     :ids.requirement/pass? pass?
     :ids.requirement/facet requirement}))

(defn- specification-result [ifc-document spatial spec]
  (let [schema (:ifc/schema ifc-document)
        schema-supported? (contains? (:ids.specification/ifc-versions spec) schema)
        applicable (filterv #(every? (partial facet-matches? % spatial)
                                     (:ids.specification/applicability spec))
                            (validation-objects ifc-document))
        count-applicable (count applicable)
        min-occurs (:ids.specification/min-occurs spec)
        max-occurs (:ids.specification/max-occurs spec)
        occurrence-pass? (and (>= count-applicable min-occurs)
                              (or (= :unbounded max-occurs)
                                  (<= count-applicable max-occurs)))
        objects
        (mapv (fn [element]
                (let [requirements
                      (mapv #(requirement-result element spatial %)
                            (:ids.specification/requirements spec))]
                  {:ids.object/global-id (:global-id element)
                   :ids.object/name (:name element)
                   :ids.object/entity (entity-name element)
                   :ids.object/pass? (every? :ids.requirement/pass? requirements)
                   :ids.object/requirements requirements}))
              applicable)
        pass? (and occurrence-pass?
                   (every? :ids.object/pass? objects))]
    {:ids.specification/name (:ids.specification/name spec)
     :ids.specification/pass? pass?
     :ids.specification/schema-supported? schema-supported?
     :ids.specification/applicable-count count-applicable
     :ids.specification/occurrence-pass? occurrence-pass?
     :ids.specification/objects objects}))

(defn validate
  "Validate an IFC exchange document against a normalized IDS document."
  [ifc-document ids-document]
  (let [spatial (spatial-index (:ifc/project ifc-document))
        objects (validation-objects ifc-document)
        spatial (assoc spatial
                       ::relations (relation-index (:ifc/raw-entities ifc-document)))
        spatial (into spatial (map (juxt :id identity)) objects)
        specifications
        (mapv #(specification-result ifc-document spatial %)
              (:ids/specifications ids-document))
        issues
        (vec
         (mapcat (fn [spec]
                   (if-not (:ids.specification/pass? spec)
                     (let [failed (filterv (complement :ids.object/pass?)
                                           (:ids.specification/objects spec))]
                       (if (seq failed)
                         (mapv (fn [object]
                                 {:ids.issue/specification (:ids.specification/name spec)
                                  :ids.issue/global-id (:ids.object/global-id object)
                                  :ids.issue/entity (:ids.object/entity object)
                                  :ids.issue/failed-requirements
                                  (filterv (complement :ids.requirement/pass?)
                                           (:ids.object/requirements object))})
                               failed)
                         [{:ids.issue/specification (:ids.specification/name spec)
                           :ids.issue/reason
                           (cond
                             (not (:ids.specification/schema-supported? spec)) :schema
                             (not (:ids.specification/occurrence-pass? spec)) :occurrence
                             :else :unknown)}]))
                     []))
                 specifications))]
    {:ids.report/version contract-version
     :ids.report/title (:ids/title ids-document)
     :ids.report/pass? (every? :ids.specification/pass? specifications)
     :ids.report/specification-count (count specifications)
     :ids.report/applicable-object-count
     (reduce + (map :ids.specification/applicable-count specifications))
     :ids.report/specifications specifications
     :ids.report/issues issues}))
