(ns sysml.kerml
  "OMG Kernel Modeling Language (KerML) 1.0 kernel as EDN. Zero third-party
  deps -- portable .cljc (JVM, ClojureScript, SCI). KerML is the foundation
  layer SysML v2 is built on (OMG KerML 1.0, formal/26-03-01, adopted
  2025-07-21; 'general syntactic constructs for structuring models... core
  semantic constructs... based on classification... additional constructs
  for commonly needed modeling capabilities, such as associations and
  behaviors', per the OMG About-KerML page). This namespace models the six
  concepts `sysml.model` needs to build SysML's Definition/Usage duality on
  top of: `Type` / `Classifier` / `Feature` / `Specialization` / `Featuring`
  / `Multiplicity`.

  A kernel is a plain namespaced-key map:
    {:kerml/elements      {\"Name\" -> element-map}
     :kerml/relationships [relationship-map ...]}

  Elements (:kerml/kind :type|:classifier|:feature) are plain maps you can
  assoc/diff/store. Per the KerML metamodel (Pilot Implementation
  `org.omg.sysml/model/kerml.ecore`, a legitimate ground-truth source per
  this library's own scoping note -- see README):
    - `Classifier` specializes `Type` (kerml.ecore ~L1857/L802: 'Classifier
      eSuperTypes=Type').
    - `Feature` specializes `Type` too (~L1153: 'Feature eSuperTypes=Type')
      -- in KerML a Feature IS a kind of Type, which is what lets a
      `PartUsage` (a Feature, in SysML) itself be specialized/typed just
      like a `PartDefinition` (a Classifier) can.
    - `Multiplicity` specializes `Feature` (~L1748) and gives the allowed
      cardinalities of a typeWithMultiplicity. The real metamodel's bounds
      are themselves `Expression` trees (so a bound can be a computed
      value); this library simplifies bounds to plain integers
      (`:kerml/lower`/`:kerml/upper`) attached directly via
      `with-multiplicity` rather than modeling a nested Expression
      sub-language (v1 scope decision, see README Follow-ups).

  Relationships (:kerml/kind :specialization|:featuring|:conjugation) are
  plain maps appended to `:kerml/relationships`:
    - `Specialization` {:kerml/specific _ :kerml/general _} -- 'a
      Relationship between two Types that requires all instances of the
      specific type to also be instances of the general Type' (kerml.ecore
      ~L770-800, `general`/`specific` references, both lowerBound=1).
    - `Featuring` (KerML's actual metaclass is `TypeFeaturing`)
      {:kerml/feature _ :kerml/featuring-type _} -- 'the Type that features
      the featureOfType' (kerml.ecore ~L1562-1592, `featureOfType`/
      `featuringType`). This library uses `Featuring` as the simple
      belongs-to relation (a Feature belongs to a Type); the real metamodel
      keeps `TypeFeaturing` distinct from ownership (`FeatureMembership`) --
      see README for why `sysml.model` does not route nested-usage
      ownership through this relationship in v1.
    - `Conjugation` {:kerml/conjugated _ :kerml/original _} -- 'the
      conjugatedType inherits all the Features of the originalType, but
      with all input and output Features reversed' (kerml.ecore
      ~L1716-1746, `originalType`/`conjugatedType`).")

;; --- builders ---

(defn kernel
  "An empty kernel model."
  []
  {:kerml/elements {} :kerml/relationships []})

(defn- element [kind nm opts]
  (merge {:kerml/kind kind :kerml/name nm} opts))

(defn kernel-type
  "Build a bare `:kerml/kind :type` element -- the abstract base kind (KerML
  1.0 `Type` specializes `Namespace`, kerml.ecore ~L802). Most models only
  ever need `classifier`/`feature` (its two concrete subkinds); this is for
  the rare case of representing a Type from a kernel library
  (e.g. `Base::Anything`) that a model refers to without itself being a
  Classifier or Feature."
  ([nm] (kernel-type nm nil))
  ([nm opts] (element :type nm opts)))

(defn classifier
  "Build a `Classifier` element (KerML 1.0, kerml.ecore ~L1857: `Classifier`
  specializes `Type`). SysML's `PartDefinition`/`AttributeDefinition`/etc.
  are all, ultimately, Classifiers -- see `sysml.model`."
  ([nm] (classifier nm nil))
  ([nm opts] (element :classifier nm opts)))

(defn feature
  "Build a `Feature` element (KerML 1.0, kerml.ecore ~L1153: `Feature`
  specializes `Type`). SysML's `PartUsage`/`AttributeUsage`/etc. are all,
  ultimately, Features -- see `sysml.model`."
  ([nm] (feature nm nil))
  ([nm opts] (element :feature nm opts)))

(defn multiplicity
  "Build a `:kerml/multiplicity` bounds map. `lower`/`upper` are plain
  integers (a v1 simplification of KerML's `Multiplicity`, which is really
  a Feature whose bounds are `Expression` trees -- see namespace docstring).
  `upper` may be `:*` for the normative unbounded `*` upper bound."
  [lower upper]
  {:kerml/lower lower :kerml/upper upper})

(defn with-multiplicity
  "assoc a `:kerml/multiplicity` map (built by `multiplicity`) onto `el`."
  [el mult]
  (assoc el :kerml/multiplicity mult))

(defn add-element
  "assoc `el` into kernel `k`'s `:kerml/elements`, keyed by its `:kerml/name`."
  [k el]
  (assoc-in k [:kerml/elements (:kerml/name el)] el))

(defn- add-relationship [k kind m]
  (update k :kerml/relationships conj (assoc m :kerml/kind kind)))

(defn specialize
  "Add a `Specialization`: `specific` specializes (is a subtype of)
  `general`. Per KerML 1.0 (kerml.ecore ~L770-800): every instance of
  `specific` must also be an instance of `general`."
  [k specific general]
  (add-relationship k :specialization {:kerml/specific specific :kerml/general general}))

(defn add-featuring
  "Add a `Featuring` (KerML `TypeFeaturing`): `feature-name` belongs to
  `featuring-type` (kerml.ecore ~L1562-1592)."
  [k feature-name featuring-type]
  (add-relationship k :featuring {:kerml/feature feature-name :kerml/featuring-type featuring-type}))

(defn conjugate
  "Add a `Conjugation`: `conjugated` is the conjugate of `original`, with
  input/output Features reversed (kerml.ecore ~L1716-1746). Structural only
  in v1 -- this library does not flip Feature direction automatically; see
  README Follow-ups."
  [k conjugated original]
  (add-relationship k :conjugation {:kerml/conjugated conjugated :kerml/original original}))

;; --- queries ---

(defn elements [k] (vals (:kerml/elements k {})))
(defn element-names [k] (set (keys (:kerml/elements k {}))))
(defn lookup [k nm] (get (:kerml/elements k {}) nm))

(defn kind? [kw el] (= kw (:kerml/kind el)))
(defn classifier? [el] (kind? :classifier el))
(defn feature? [el] (kind? :feature el))
(defn type?
  "True for any element kind that IS a KerML `Type` -- `:type` itself, or
  either of its two concrete subkinds `:classifier`/`:feature`."
  [el]
  (contains? #{:type :classifier :feature} (:kerml/kind el)))

(defn relationships-of-kind [k kw]
  (filter #(= kw (:kerml/kind %)) (:kerml/relationships k [])))

(defn specializations [k] (relationships-of-kind k :specialization))
(defn featurings [k] (relationships-of-kind k :featuring))
(defn conjugations [k] (relationships-of-kind k :conjugation))

(defn direct-supertypes
  "The `general` types of `nm`'s owned Specializations (one DFS-frontier step)."
  [k nm]
  (set (keep (fn [s] (when (= nm (:kerml/specific s)) (:kerml/general s)))
             (specializations k))))

(defn all-supertypes
  "Per KerML 1.0 `Type::allSupertypes()` (kerml.ecore ~L885-889): 'return
  this Type and all Types that are directly or transitively supertypes of
  this Type.' Note this literally includes `nm` itself, per the spec
  operation's own wording -- callers wanting strict ancestors only should
  `(disj (all-supertypes k nm) nm)`.

  Implemented as a worklist/frontier closure over `direct-supertypes`: at
  each step, pop an unseen name off the frontier, mark it seen, and push
  its own direct supertypes onto the frontier. The `seen` set doubles as
  cycle protection, so this terminates even over a (structurally invalid,
  see `sysml.validate`) cyclic Specialization graph."
  [k nm]
  (loop [frontier #{nm} seen #{}]
    (if (empty? frontier)
      seen
      (let [n (first frontier)
            frontier* (disj frontier n)]
        (if (seen n)
          (recur frontier* seen)
          (recur (into frontier* (direct-supertypes k n)) (conj seen n)))))))

(defn specializes?
  "True if `specific` transitively specializes `general` (and is not itself
  `general` -- see `all-supertypes` docstring on self-inclusion)."
  [k specific general]
  (and (not= specific general)
       (contains? (all-supertypes k specific) general)))

(defn features-of
  "The `:kerml/feature` names of Featuring relationships whose
  `:kerml/featuring-type` is `featuring-type-name`."
  [k featuring-type-name]
  (set (keep (fn [f] (when (= featuring-type-name (:kerml/featuring-type f)) (:kerml/feature f)))
             (featurings k))))
