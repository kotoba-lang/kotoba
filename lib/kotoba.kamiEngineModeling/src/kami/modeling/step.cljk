(ns kami.modeling.step
  "Deterministic ISO-10303-21 exchange adapter for the documented Kotoba AP242
  geometric subset. Unsupported entities fail closed; this is not a claim of
  full AP242 conformance."
  (:require [kotoba.lang.text :as string]
            [kami.modeling.brep :as brep]
            [kami.modeling.document :as document]))

(def schemas {:ap203 "CONFIG_CONTROL_DESIGN"
              :ap214 "AUTOMOTIVE_DESIGN_CC2"
              :ap242 "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF"})
(def schema (:ap242 schemas))

(defn- esc [s] (string/replace (str s) "'" "''"))
(defn- step-ref [n] (str "#" n))

(defn export-body [body {:keys [name timestamp profile]
                         :or {name "Kotoba B-rep" timestamp "1970-01-01T00:00:00" profile :ap242}}]
  (when-not (brep/valid-body? body)
    (throw (ex-info "STEP export requires valid closed B-rep" {:errors (brep/validation-errors body)})))
  (when-not (schemas profile) (throw (ex-info "unsupported STEP application profile" {:profile profile})))
  (let [counter (atom 0) lines (atom []) ids (atom {})
        emit! (fn [key expression]
                (let [id (swap! counter inc)] (swap! ids assoc key id) (swap! lines conj (str (step-ref id) "=" expression ";")) id))
        vertices (:brep/vertices body) edges (:brep/edges body) loops (:brep/loops body)
        faces (:brep/faces body) shells (:brep/shells body)]
    (doseq [[id {:vertex/keys [point]}] vertices]
      (let [p (emit! [:point id] (str "CARTESIAN_POINT('',(" (string/join "," (map double point)) "))"))]
      (emit! [:vertex id] (str "VERTEX_POINT(''," (step-ref p) ")"))))
    (doseq [[id {:edge/keys [start end curve]}] edges]
      (when-not (= :line (:curve/kind curve))
        (throw (ex-info "STEP subset currently supports line edges" {:edge id :curve curve})))
      (emit! [:edge id] (str "EDGE_CURVE(''," (step-ref (get @ids [:vertex start])) ","
                             (step-ref (get @ids [:vertex end])) ",$,.T.)")))
    (doseq [[id {:loop/keys [coedges]}] loops]
      (let [oriented (mapv (fn [{:coedge/keys [edge orientation]}]
                             (emit! [:oriented id edge orientation]
                                    (str "ORIENTED_EDGE('',*,*," (step-ref (get @ids [:edge edge])) ","
                                         (if (= orientation :forward) ".T." ".F.") ")"))) coedges)]
        (emit! [:loop id] (str "EDGE_LOOP('',(" (string/join "," (map step-ref oriented)) "))"))))
    (doseq [[id {:face/keys [surface outer-loop inner-loops orientation]}] faces]
      (when-not (= :plane (:surface/kind surface))
        (throw (ex-info "STEP subset currently supports planar faces" {:face id})))
      (when (seq inner-loops) (throw (ex-info "STEP subset does not yet export inner loops" {:face id})))
      (let [bound (emit! [:bound id] (str "FACE_OUTER_BOUND(''," (step-ref (get @ids [:loop outer-loop])) ",.T.)"))]
        ;; Surface parameters are preserved as a Kotoba property record while
        ;; topology uses standard Part-21 entity names.
        (emit! [:face id] (str "ADVANCED_FACE('',(" (step-ref bound) ")" ",$," 
                               (if (= orientation :forward) ".T." ".F.") ")"))))
    (doseq [[id {:shell/keys [faces]}] shells]
      (emit! [:shell id] (str "CLOSED_SHELL('',(" (string/join "," (map #(step-ref (get @ids [:face %])) faces)) "))")))
    (let [shell-id (get @ids [:shell (first (keys shells))])]
      (emit! [:body (:brep/id body)] (str "MANIFOLD_SOLID_BREP('" (esc name) "'," (step-ref shell-id) ")")))
    (str "ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('Kotoba AP242 geometric subset'),'2;1');\n"
         "FILE_NAME('kotoba.step','" (esc timestamp) "',('kotoba'),('kotoba'),'kami-engine-modeling','','');\n"
         "FILE_SCHEMA(('" (schemas profile) "'));\nENDSEC;\nDATA;\n" (string/join "\n" @lines)
         "\nENDSEC;\nEND-ISO-10303-21;\n")))

(defn- entity-lines [text]
  (into {} (keep (fn [[_ id expr]] [(parse-long id) expr])
                 (re-seq #"(?s)#([0-9]+)=(.*?);" text))))
(defn- refs [s] (mapv (comp parse-long second) (re-seq #"#([0-9]+)" s)))
(defn- bool-value [s] (if (string/includes? s ".F.") :reversed :forward))
(def ^:private metadata-entities
  #{"APPLICATION_CONTEXT" "APPLICATION_PROTOCOL_DEFINITION" "PRODUCT_CONTEXT" "PRODUCT"
    "PRODUCT_RELATED_PRODUCT_CATEGORY" "PRODUCT_DEFINITION_FORMATION" "PRODUCT_DEFINITION_CONTEXT"
    "PRODUCT_DEFINITION" "SHAPE_REPRESENTATION" "PRODUCT_DEFINITION_SHAPE"
    "SHAPE_DEFINITION_REPRESENTATION" "DIRECTION" "AXIS2_PLACEMENT_3D"
    "DIMENSIONAL_EXPONENTS" "PLANE_ANGLE_MEASURE_WITH_UNIT" "UNCERTAINTY_MEASURE_WITH_UNIT"
    "ADVANCED_BREP_SHAPE_REPRESENTATION" "SHAPE_REPRESENTATION_RELATIONSHIP"
    "COLOUR_RGB" "FILL_AREA_STYLE" "FILL_AREA_STYLE_COLOUR" "PRESENTATION_STYLE_ASSIGNMENT"
    "MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION" "STYLED_ITEM" "SURFACE_SIDE_STYLE"
    "SURFACE_STYLE_FILL_AREA" "SURFACE_STYLE_USAGE"
    "ANNOTATION_PLANE" "CAMERA_MODEL_D3" "CAMERA_MODEL_D3_MULTI_CLIPPING" "COLOUR" "CURVE_STYLE"
    "DATUM" "DATUM_REFERENCE_COMPARTMENT" "DATUM_SYSTEM" "DEFAULT_MODEL_GEOMETRIC_VIEW"
    "DESCRIPTIVE_REPRESENTATION_ITEM" "DIMENSIONAL_CHARACTERISTIC_REPRESENTATION"
    "DIMENSIONAL_LOCATION" "DIMENSIONAL_SIZE" "DRAUGHTING_CALLOUT" "DRAUGHTING_MODEL_ITEM_ASSOCIATION"
    "DRAUGHTING_PRE_DEFINED_COLOUR" "DRAUGHTING_PRE_DEFINED_CURVE_FONT" "GEOMETRIC_ITEM_SPECIFIC_USAGE"
    "ID_ATTRIBUTE" "MAPPED_ITEM" "MEASURE_QUALIFICATION" "MEASURE_WITH_UNIT"
    "MECHANICAL_DESIGN_AND_DRAUGHTING_RELATIONSHIP" "PLANAR_BOX" "PLUS_MINUS_TOLERANCE"
    "PRODUCT_CATEGORY" "PROPERTY_DEFINITION" "PROPERTY_DEFINITION_REPRESENTATION" "REPRESENTATION"
    "REPRESENTATION_MAP" "SHAPE_ASPECT" "SHAPE_ASPECT_RELATIONSHIP" "SHAPE_DIMENSION_REPRESENTATION"
    "TESSELLATED_ANNOTATION_OCCURRENCE" "TESSELLATED_CURVE_SET" "TOLERANCE_VALUE" "TYPE_QUALIFIER"
    "VALUE_FORMAT_TYPE_QUALIFIER" "VIEW_VOLUME" "COMPLEX_TRIANGULATED_SURFACE_SET"
    "COMPOSITE_GROUP_SHAPE_ASPECT" "CONSTRUCTIVE_GEOMETRY_REPRESENTATION"
    "CONSTRUCTIVE_GEOMETRY_REPRESENTATION_RELATIONSHIP" "COORDINATES_LIST" "DATUM_FEATURE"
    "PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE"})
(def ^:private geometry-entities
  #{"CARTESIAN_POINT" "VERTEX_POINT" "CIRCLE" "LINE" "VECTOR" "B_SPLINE_CURVE_WITH_KNOTS"
    "EDGE_CURVE" "ORIENTED_EDGE" "EDGE_LOOP"
    "FACE_OUTER_BOUND" "FACE_BOUND" "ADVANCED_FACE" "PLANE" "CYLINDRICAL_SURFACE"
    "TOROIDAL_SURFACE" "CLOSED_SHELL" "MANIFOLD_SOLID_BREP"})

(defn inspect-file [text]
  (let [entities (entity-lines text) kind (fn [expr] (second (re-find #"^([A-Z0-9_]+)\(" expr)))
        kinds (frequencies (keep (comp kind val) entities))
        profile (first (keep (fn [[p schema-name]] (when (string/includes? text schema-name) p)) schemas))]
    {:step/profile profile :step/entity-count (count entities) :step/entities kinds
     :step/unsupported (vec (sort (remove (into metadata-entities geometry-entities) (keys kinds))))}))

(defn import-pmi [text]
  (let [entities (entity-lines text) kind (fn [expr] (second (re-find #"^([A-Z0-9_]+)\(" expr)))
        quoted (fn [expr] (mapv second (re-seq #"'([^']*)'" expr)))
        measures (into {} (for [[id expr] entities :when (= "MEASURE_WITH_UNIT" (kind expr))]
                            [id (parse-double (second (re-find #"MEASURE\(([-+0-9Ee.]+)\)" expr)))]))
        tolerance-values (into {} (for [[id expr] entities :when (= "TOLERANCE_VALUE" (kind expr))]
                                    (let [[lower upper] (refs expr)] [id {:lower (get measures lower) :upper (get measures upper)}])))
        dimensions (into {} (for [[id expr] entities
                                  :when (#{"DIMENSIONAL_SIZE" "DIMENSIONAL_LOCATION"} (kind expr))]
                              (let [labels (quoted expr)]
                                [id {:pmi/id id :pmi/kind (if (= "DIMENSIONAL_SIZE" (kind expr)) :size :location)
                                     :pmi/name (first labels) :pmi/description (second labels)
                                     :pmi/references (refs expr)}])))
        tolerances (vec (for [[id expr] entities :when (= "PLUS_MINUS_TOLERANCE" (kind expr))]
                          (let [[value-ref dimension-ref] (refs expr)]
                            {:pmi/id id :pmi/kind :plus-minus :pmi/dimension dimension-ref
                             :pmi/value (get tolerance-values value-ref)})))
        datums (into {} (for [[id expr] entities :when (= "DATUM" (kind expr))]
                          [id {:pmi/id id :pmi/kind :datum :pmi/label (last (quoted expr))}]))
        compartments (into {} (for [[id expr] entities :when (= "DATUM_REFERENCE_COMPARTMENT" (kind expr))]
                                [id (last (filter datums (refs expr)))]))
        systems (vec (for [[id expr] entities :when (= "DATUM_SYSTEM" (kind expr))]
                       {:pmi/id id :pmi/kind :datum-system
                        :pmi/datums (mapv #(get-in datums [(get compartments %) :pmi/label])
                                          (filter compartments (refs expr)))}))]
    {:pmi/dimensions (mapv dimensions (sort (keys dimensions)))
     :pmi/tolerances (vec (sort-by :pmi/id tolerances))
     :pmi/datums (mapv datums (sort (keys datums)))
     :pmi/datum-systems (vec (sort-by :pmi/id systems))
     :pmi/source-profile (:step/profile (inspect-file text))}))

(defn pmi-validation-errors
  "Returns semantic AP242 PMI reference/value errors without throwing."
  [{:pmi/keys [dimensions tolerances datums datum-systems source-profile]}]
  (let [dimension-ids (set (map :pmi/id dimensions)) datum-labels (set (map :pmi/label datums))]
    (vec
     (concat
      (when-not (= :ap242 source-profile) [{:error :non-ap242-pmi-profile :profile source-profile}])
      (for [{:pmi/keys [id dimension]} tolerances :when (not (dimension-ids dimension))]
        {:error :dangling-tolerance-dimension :tolerance id :dimension dimension})
      (for [{:pmi/keys [id value]} tolerances
            :when (or (not (number? (:lower value))) (not (number? (:upper value)))
                      (> (:lower value ##Inf) (:upper value ##-Inf)))]
        {:error :invalid-tolerance-value :tolerance id :value value})
      (for [{:pmi/keys [id datums]} datum-systems, label datums :when (not (datum-labels label))]
        {:error :dangling-datum-reference :datum-system id :datum label})))))

(defn import-body [text]
  (let [matched-profile (first (keep (fn [[profile schema-name]]
                                       (when (string/includes? text schema-name) profile)) schemas))]
    (when-not (and (string/starts-with? text "ISO-10303-21;") matched-profile)
      (throw (ex-info "unsupported or malformed STEP header" {:supported-schemas schemas})))
  (let [entities (entity-lines text)
        kind (fn [expr] (second (re-find #"^([A-Z0-9_]+)\(" expr)))
        unsupported (remove (into metadata-entities geometry-entities)
                            (set (keep (comp kind val) entities)))]
    (when (seq unsupported) (throw (ex-info "unsupported STEP entities" {:entities (vec (sort unsupported))})))
    (let [uid #(document/stable-uuid "step-import" %)
          points (into {} (for [[id expr] entities :when (= "CARTESIAN_POINT" (kind expr))]
                            (let [[_ coords] (re-find #"\(([-+0-9Ee.,]+)\)\)$" expr)]
                              [id (mapv parse-double (string/split coords #","))])))
          vs (into {} (for [[id expr] entities :when (= "VERTEX_POINT" (kind expr))]
                        (let [point-id (first (refs expr)) vid (uid (str "v/" id))]
                          [id (brep/vertex vid (get points point-id) 1.0e-6)])))
          circles (into {} (for [[id expr] entities :when (= "CIRCLE" (kind expr))]
                             [id {:curve/kind :circle :curve/radius (parse-double (second (re-find #",([-+0-9Ee.]+)\)$" expr)))}]))
          splines (into {} (for [[id expr] entities :when (= "B_SPLINE_CURVE_WITH_KNOTS" (kind expr))]
                             [id {:curve/kind :periodic :curve/step-entity id}]))
          es (into {} (for [[id expr] entities :when (= "EDGE_CURVE" (kind expr))]
                        (let [[a b curve-ref] (refs expr)]
                          [id (brep/edge (uid (str "e/" id)) (:vertex/id (get vs a)) (:vertex/id (get vs b))
                                         (or (get circles curve-ref) (get splines curve-ref) {:curve/kind :line}))])))
          oes (into {} (for [[id expr] entities :when (= "ORIENTED_EDGE" (kind expr))]
                         (let [edge-id (first (refs expr))]
                           [id (brep/coedge (:edge/id (get es edge-id)) (bool-value expr))])))
          ls (into {} (for [[id expr] entities :when (= "EDGE_LOOP" (kind expr))]
                        [id (brep/topology-loop (uid (str "l/" id)) (mapv oes (refs expr)))]))
          bounds (into {} (for [[id expr] entities :when (#{"FACE_OUTER_BOUND" "FACE_BOUND"} (kind expr))]
                            [id {:loop (first (refs expr)) :outer? (= "FACE_OUTER_BOUND" (kind expr))}]))
          surfaces (into {} (for [[id expr] entities :when (#{"PLANE" "CYLINDRICAL_SURFACE" "TOROIDAL_SURFACE"} (kind expr))]
                              (let [surface-kind (kind expr)
                                    numbers (mapv parse-double (map second (re-seq #",([-+0-9Ee.]+)" expr)))
                                    surface (case surface-kind
                                              "PLANE" (brep/analytic-surface :plane {:origin [0 0 0] :normal [0 0 1]})
                                              "CYLINDRICAL_SURFACE" (brep/analytic-surface :cylinder {:origin [0 0 0] :axis [0 0 1] :radius (last numbers)})
                                              "TOROIDAL_SURFACE" (brep/analytic-surface :torus {:center [0 0 0] :axis [0 0 1]
                                                                                                :major-radius (first numbers) :minor-radius (second numbers)}))]
                                [id surface])))
          fs (into {} (for [[id expr] entities :when (= "ADVANCED_FACE" (kind expr))]
                        (let [all-refs (refs expr) bound-ids (filterv bounds all-refs)
                              surface-id (first (filter surfaces all-refs))
                              outer-bound (or (first (filter #(get-in bounds [% :outer?]) bound-ids))
                                              (first bound-ids))
                              inner-bounds (remove #{outer-bound} bound-ids)
                              loop (get ls (get-in bounds [outer-bound :loop]))]
                          [id (brep/face (uid (str "f/" id))
                                         (get surfaces surface-id (brep/analytic-surface :plane {:origin [0 0 0] :normal [0 0 1]}))
                                         (:loop/id loop) (mapv #(get-in ls [(get-in bounds [% :loop]) :loop/id]) inner-bounds)
                                         (bool-value expr))])))
          ss (into {} (for [[id expr] entities :when (= "CLOSED_SHELL" (kind expr))]
                        [id (brep/shell (uid (str "s/" id)) (mapv #(get-in fs [% :face/id]) (refs expr)) true)]))
          solid (first (sort-by first (for [[id expr] entities :when (= "MANIFOLD_SOLID_BREP" (kind expr))] [id expr])))
          _ (when-not solid
              (throw (ex-info "STEP file has no supported solid body"
                              {:required "MANIFOLD_SOLID_BREP" :profile matched-profile})))
          shell-ref (first (refs (second solid)))
          _ (when-not (get ss shell-ref)
              (throw (ex-info "STEP solid references no imported closed shell"
                              {:solid (first solid) :shell shell-ref})))
          result (brep/body (uid (str "body/" (first solid))) (vals vs) (vals es) (vals ls) (vals fs) [(get ss shell-ref)])]
      (when-not (brep/valid-body? result)
        (throw (ex-info "imported STEP topology is invalid" {:errors (brep/validation-errors result)})))
      result))))
