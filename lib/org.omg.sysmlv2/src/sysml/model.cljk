(ns sysml.model
  "OMG Systems Modeling Language (SysML) v2.0 kernel elements as EDN, built
  on `sysml.kerml`. Zero third-party deps -- portable .cljc. A model is a
  `sysml.kerml` kernel (`{:kerml/elements ... :kerml/relationships ...}`)
  plus a `:sysml/name`; every SysML element this namespace builds IS,
  underneath, a `sysml.kerml` `classifier` or `feature` tagged with
  `:sysml/element-kind`, so `sysml.kerml`'s specialization machinery
  (`specialize`/`all-supertypes`/`specializes?`) works directly on SysML
  Definitions and Usages too.

  **The Definition/Usage duality** (OMG SysML 2.0 Language spec,
  formal/26-03-02; ground-truthed here against the Pilot Implementation's
  `org.omg.sysml.model/src/main/resources/model/SysML.ecore`) is SysML v2's
  central structural idea: a `Definition` is a reusable type (KerML
  `Classifier` specialization, ecore ~L921: `Definition eSuperTypes=
  Classifier`), a `Usage` is an occurrence of one in a context (KerML
  `Feature` specialization, ecore ~L4827: `Usage eSuperTypes=Feature`).
  Optional `Usage.definition` names the Classifiers/Definitions typing a usage
  (ecore ~L4837-4847); `Definition.usage`/`Usage.nestedUsage` name a
  Definition's or Usage's owned Usages (ecore ~L925 / ~L4827 doc). A
  `PartUsage` can itself own nested `PartUsage`s typed by other
  `PartDefinition`s -- e.g. a `Vehicle` PartDefinition nests an `engine`
  PartUsage (typed by an `Engine` PartDefinition), which in turn nests a
  `fuelIn` PortUsage (typed by a `FuelPort` PortDefinition). See the
  `sysml.validate` and README Contract example for exactly this shape.

  Element shape: every element is `{:kerml/kind :classifier|:feature
  :kerml/name _ :sysml/element-kind _ ...}`. A typed Usage additionally
  carries `:sysml/definition` (the name of its Classifier/Definition) and,
  optionally, `:sysml/nested` (a set of names of Usages -- or, for a
  `:package`, arbitrary member elements -- it structurally contains).

  **v1 simplifications (see README Follow-ups for the full list):**
  - `Usage.definition` (real KerML: `FeatureTyping`, itself a kind of
    `Specialization` -- kerml.ecore ~L1529) is stored here as a direct
    `:sysml/definition` name reference rather than round-tripped through
    `sysml.kerml`'s generic Specialization relationship list. Definition-
    to-Definition (and Usage-to-Usage) generalization chains (e.g. `Car`
    specializes `Vehicle`) DO reuse `sysml.kerml/specialize` +
    `all-supertypes` directly, since that is a straightforward, faithful
    reuse of the kernel's own machinery.
  - Nested-usage ownership (real KerML: `FeatureMembership`, a kind of
    `OwningMembership` -- distinct from `TypeFeaturing`/`Featuring`) is
    likewise a direct `:sysml/nested` name-set rather than
    `sysml.kerml/add-featuring` relationships, for the same directness
    reason. `sysml.kerml`'s `Featuring` remains available and is exercised
    on its own in `sysml.kerml-test` for the generic 'a feature belongs to
    a type' case.
  - `ConnectionDefinition`/`ConnectionUsage` (ecore ~L737/~L753:
    `ConnectionDefinition eSuperTypes=PartDefinition+AssociationStructure`,
    `ConnectionUsage eSuperTypes=ConnectorAsUsage+PartUsage`) are modeled
    here as their own element kinds carrying `:sysml/ends` (a vector of
    connected Port/Part usage names, simplifying the real metamodel's
    `Connector::connectorEnd`/`relatedFeature`/n-ary `ReferenceSubsetting`
    machinery to plain name references). Likewise `InterfaceDefinition`/
    `InterfaceUsage` (ecore: `InterfaceDefinition eSuperTypes=
    ConnectionDefinition`) are modeled as their own sibling kinds rather
    than literally inheriting ConnectionDefinition/Usage's shape.
  - `RequirementDefinition`/`RequirementUsage`'s `requiredConstraint`
    (ecore ~L3647/~L3733: owned `ConstraintUsage`s) are modeled as plain
    constraint-expression strings in `:sysml/required-constraints`, not
    full `ConstraintUsage` elements -- constraint *solving* is out of
    scope entirely (see README), so there is nothing structural gained by
    a richer shape here in v1.
  - `SatisfyRequirementUsage` (ecore ~L3838: `SatisfyRequirementUsage
    eSuperTypes=RequirementUsage+AssertConstraintUsage`) and a `verify`
    counterpart (real KerML: `RequirementVerificationMembership`, which
    ties a `VerificationCase` -- not modeled at all here -- to a
    `RequirementUsage`) are both modeled as lightweight named relationship
    elements (`:satisfy-requirement-usage`/`:verify-requirement-usage`)
    referencing the requirement and the satisfying/verifying usage by
    name, purely for structural traceability -- no verification reasoning
    is performed (see `sysml.validate` `scope-out-problems`)."
  (:require [sysml.kerml :as kerml]))

;; --- model container ---

(defn model
  "Build an empty (or opts-seeded) SysML model: a `sysml.kerml` kernel
  tagged with `:sysml/name`."
  ([nm] (model nm nil))
  ([nm opts] (merge (kerml/kernel) {:sysml/name nm} opts)))

(defn add-element
  "assoc `el` into `m`, keyed by its `:kerml/name` (delegates to
  `sysml.kerml/add-element`)."
  [m el]
  (kerml/add-element m el))

(defn specialize
  "Definition-to-Definition (or Usage-to-Usage) generalization: `specific`
  specializes `general`. Delegates directly to `sysml.kerml/specialize` --
  see namespace docstring on why this, unlike Usage-typed-by-Definition, is
  a direct kernel reuse."
  [m specific general]
  (kerml/specialize m specific general))

(def ^{:doc "Re-exported from `sysml.kerml` -- see `specialize`."} all-supertypes kerml/all-supertypes)
(def ^{:doc "Re-exported from `sysml.kerml`."} specializes? kerml/specializes?)

(defn nest
  "assoc `member-name` into owner-element `el`'s `:sysml/nested` set. Used
  both for a Definition/Usage owning nested Usages, and for a `:package`
  owning arbitrary member elements (the underlying mechanism -- 'this named
  element structurally contains these other named elements' -- is
  identical in both cases; see namespace docstring)."
  [el member-name]
  (update el :sysml/nested (fnil conj #{}) member-name))

;; --- builders: Definition/Usage pairs ---

(defn- definition [kind nm opts]
  (merge (kerml/classifier nm) {:sysml/element-kind kind} opts))

(defn- usage [kind nm definition-name opts]
  (merge (kerml/feature nm)
         (cond-> {:sysml/element-kind kind}
           definition-name (assoc :sysml/definition definition-name))
         opts))

(defn part-definition
  "A `PartDefinition` (SysML 2.0, ecore ~L3296: `PartDefinition
  eSuperTypes=ItemDefinition`) -- 'an ItemDefinition of a Class of systems
  or parts of systems.'"
  ([nm] (part-definition nm nil))
  ([nm opts] (definition :part-definition nm opts)))

(defn part-usage
  "A `PartUsage` (ecore ~L3301), optionally typed by the Definition named
  `definition-name`. SysML v2 permits untyped Usages."
  ([nm definition-name] (part-usage nm definition-name nil))
  ([nm definition-name opts] (usage :part-usage nm definition-name opts)))

(defn attribute-definition
  "An `AttributeDefinition` (ecore ~L400: `AttributeDefinition
  eSuperTypes=Definition+DataType`) -- a value property's type; all its
  features must be referential (non-composite) per the real metamodel."
  ([nm] (attribute-definition nm nil))
  ([nm opts] (definition :attribute-definition nm opts)))

(defn attribute-usage
  "An `AttributeUsage` (ecore ~L405) typed by the Definition named
  `definition-name`."
  ([nm definition-name] (attribute-usage nm definition-name nil))
  ([nm definition-name opts] (usage :attribute-usage nm definition-name opts)))

(defn port-definition
  "A `PortDefinition` (ecore ~L3362: `PortDefinition eSuperTypes=
  OccurrenceDefinition+Structure`) -- 'a point at which external entities
  can connect to and interact with a system or part of a system.'"
  ([nm] (port-definition nm nil))
  ([nm opts] (definition :port-definition nm opts)))

(defn port-usage
  "A `PortUsage` (ecore ~L3376) typed by the Definition named
  `definition-name`."
  ([nm definition-name] (port-usage nm definition-name nil))
  ([nm definition-name opts] (usage :port-usage nm definition-name opts)))

(defn item-definition
  "An `ItemDefinition` (ecore ~L2626: `ItemDefinition eSuperTypes=
  OccurrenceDefinition+Structure`) -- things acted on by a system (e.g.
  water, an electrical signal) that need not perform actions themselves."
  ([nm] (item-definition nm nil))
  ([nm opts] (definition :item-definition nm opts)))

(defn item-usage
  "An `ItemUsage` (ecore ~L2631) typed by the Definition named
  `definition-name`."
  ([nm definition-name] (item-usage nm definition-name nil))
  ([nm definition-name opts] (usage :item-usage nm definition-name opts)))

(defn action-definition
  "An `ActionDefinition` (ecore ~L51: `ActionDefinition eSuperTypes=
  OccurrenceDefinition+Behavior`). Structural only in this library -- no
  execution semantics (see README and `sysml.validate`
  `scope-out-problems`, which flags any Action element with a `:warn`)."
  ([nm] (action-definition nm nil))
  ([nm opts] (definition :action-definition nm opts)))

(defn action-usage
  "An `ActionUsage` (ecore ~L67) typed by the Definition named
  `definition-name`. Structural only -- see `action-definition`."
  ([nm definition-name] (action-usage nm definition-name nil))
  ([nm definition-name opts] (usage :action-usage nm definition-name opts)))

(defn connection-definition
  "A `ConnectionDefinition` (ecore ~L737: `ConnectionDefinition
  eSuperTypes=PartDefinition+AssociationStructure`)."
  ([nm] (connection-definition nm nil))
  ([nm opts] (definition :connection-definition nm opts)))

(defn connection-usage
  "A `ConnectionUsage` (ecore ~L753) typed by the Definition named
  `definition-name`, connecting `ends` (a seq of Port/Part usage names --
  simplifying the real metamodel's n-ary `connectorEnd`/`relatedFeature`;
  see namespace docstring)."
  ([nm definition-name ends] (connection-usage nm definition-name ends nil))
  ([nm definition-name ends opts]
   (usage :connection-usage nm definition-name (merge {:sysml/ends (vec ends)} opts))))

(defn interface-definition
  "An `InterfaceDefinition` (ecore ~L2547: `InterfaceDefinition
  eSuperTypes=ConnectionDefinition`). Modeled as a sibling kind of
  `connection-definition` in v1, not a literal specialization of it -- see
  namespace docstring."
  ([nm] (interface-definition nm nil))
  ([nm opts] (definition :interface-definition nm opts)))

(defn interface-usage
  "An `InterfaceUsage` (ecore ~L2563) typed by the Definition named
  `definition-name`, connecting `ends` -- see `connection-usage`."
  ([nm definition-name ends] (interface-usage nm definition-name ends nil))
  ([nm definition-name ends opts]
   (usage :interface-usage nm definition-name (merge {:sysml/ends (vec ends)} opts))))

(defn requirement-definition
  "A `RequirementDefinition` (ecore ~L3603: `RequirementDefinition
  eSuperTypes=ConstraintDefinition`) -- 'a constraint that a valid solution
  must satisfy,' relative to a subject, possibly in collaboration with
  actors. `opts` may set `:sysml/text` (ecore `text`) and `:sysml/req-id`
  (ecore `reqId`, 'an optional modeler-specified identifier... used, e.g.,
  to link it to an original requirement text in some source document')."
  ([nm] (requirement-definition nm nil))
  ([nm opts] (definition :requirement-definition nm opts)))

(defn requirement-usage
  "A `RequirementUsage` (ecore ~L3689) typed by the Definition named
  `definition-name`. Build up `:sysml/subject`/`:sysml/actors`/
  `:sysml/required-constraints` with `with-subject`/`with-actors`/
  `require-constraint`."
  ([nm definition-name] (requirement-usage nm definition-name nil))
  ([nm definition-name opts] (usage :requirement-usage nm definition-name opts)))

(defn with-subject
  "Set `req`'s subject (ecore `subjectParameter`: 'the parameter... that
  represents its subject') to the Usage named `usage-name`."
  [req usage-name]
  (assoc req :sysml/subject usage-name))

(defn with-actors
  "Set `req`'s actors (ecore `actorParameter`: 'parameters... that represent
  actors involved in the requirement') to the Usage names in `names`."
  [req names]
  (assoc req :sysml/actors (set names)))

(defn with-stakeholders
  "Set `req`'s stakeholders (ecore `stakeholderParameter`) to the Usage
  names in `names`."
  [req names]
  (assoc req :sysml/stakeholders (set names)))

(defn require-constraint
  "Append a required-constraint expression string to `req`'s
  `:sysml/required-constraints` (a v1 simplification of ecore
  `requiredConstraint`'s owned `ConstraintUsage`s -- see namespace
  docstring)."
  [req expr-str]
  (update req :sysml/required-constraints (fnil conj []) expr-str))

(defn satisfy-requirement-usage
  "A `SatisfyRequirementUsage` (ecore ~L3838) asserting `satisfied-by`
  (a Usage name) satisfies the requirement `requirement-name`."
  ([nm requirement-name satisfied-by] (satisfy-requirement-usage nm requirement-name satisfied-by nil))
  ([nm requirement-name satisfied-by opts]
   (merge (kerml/feature nm)
          {:sysml/element-kind :satisfy-requirement-usage
           :sysml/satisfies requirement-name
           :sysml/satisfied-by satisfied-by}
          opts)))

(defn verify-requirement-usage
  "A structural stand-in for KerML's `RequirementVerificationMembership`
  (which, in the real metamodel, ties a `VerificationCase` -- not modeled
  by this library -- to a `RequirementUsage`): asserts `verified-by` (a
  Usage name) verifies the requirement `requirement-name`, for
  traceability purposes only."
  ([nm requirement-name verified-by] (verify-requirement-usage nm requirement-name verified-by nil))
  ([nm requirement-name verified-by opts]
   (merge (kerml/feature nm)
          {:sysml/element-kind :verify-requirement-usage
           :sysml/verifies requirement-name
           :sysml/verified-by verified-by}
          opts)))

(defn package
  "A `Package` (ecore ~L3251: `Package eSuperTypes=Namespace`) -- a
  container for top-level Definitions/Usages/Packages. Add members with
  `nest` (Package containment reuses the same `:sysml/nested` mechanism as
  Usage nesting -- see namespace docstring)."
  ([nm] (package nm nil))
  ([nm opts] (merge {:kerml/name nm :sysml/element-kind :package :sysml/nested #{}} opts)))

;; --- queries ---

(def definition-kinds
  #{:part-definition :attribute-definition :port-definition :item-definition
    :action-definition :connection-definition :interface-definition :requirement-definition})

(def usage-kinds
  #{:part-usage :attribute-usage :port-usage :item-usage
    :action-usage :connection-usage :interface-usage :requirement-usage})

(defn elements [m] (kerml/elements m))
(defn lookup [m nm] (kerml/lookup m nm))

(defn element-kind? [kw el] (= kw (:sysml/element-kind el)))
(defn definition? [el] (contains? definition-kinds (:sysml/element-kind el)))
(defn usage? [el] (contains? usage-kinds (:sysml/element-kind el)))
(defn package? [el] (element-kind? :package el))

(defn part-definition? [el] (element-kind? :part-definition el))
(defn part-usage? [el] (element-kind? :part-usage el))
(defn port-definition? [el] (element-kind? :port-definition el))
(defn port-usage? [el] (element-kind? :port-usage el))
(defn connection-usage? [el] (element-kind? :connection-usage el))
(defn requirement-definition? [el] (element-kind? :requirement-definition el))
(defn requirement-usage? [el] (element-kind? :requirement-usage el))

(defn definitions [m] (filter definition? (elements m)))
(defn usages [m] (filter usage? (elements m)))

(defn definition-of
  "The Definition element typing the Usage named `usage-name` (ecore
  `Usage.definition`), or nil."
  [m usage-name]
  (when-let [u (lookup m usage-name)]
    (when-let [dn (:sysml/definition u)]
      (lookup m dn))))

(defn nested-usages
  "The elements directly nested in the owner named `owner-name` (ecore
  `Usage.nestedUsage`/`Definition.usage`; or, for a `:package`, its
  members) -- one step, not transitive. See `all-nested-usages` for the
  transitive closure."
  [m owner-name]
  (map #(lookup m %) (:sysml/nested (lookup m owner-name) #{})))

(defn all-nested-usages
  "Transitive closure of nested-usage NAMES under `owner-name` (same
  worklist/frontier-closure technique as `sysml.kerml/all-supertypes`, so
  it is cycle-safe even over a structurally invalid model). Does NOT
  include `owner-name` itself."
  [m owner-name]
  (loop [frontier (set (:sysml/nested (lookup m owner-name) #{})) seen #{}]
    (if (empty? frontier)
      seen
      (let [n (first frontier)
            frontier* (disj frontier n)]
        (if (seen n)
          (recur frontier* seen)
          (recur (into frontier* (:sysml/nested (lookup m n) #{})) (conj seen n)))))))
