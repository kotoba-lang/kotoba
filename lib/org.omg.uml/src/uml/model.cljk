(ns uml.model
  "OMG UML 2.5.1 Classes package (structural / class-diagram metamodel) as
  EDN. Zero third-party deps -- portable .cljc (JVM, ClojureScript, SCI).
  Scope: v1 covers ONLY the Classes package -- Kernel (clause 9, 11.4/11.8.3),
  AssociationClasses (11.8.2), Interfaces (10.4/10.5.5), PrimitiveTypes
  (clause 21), Dependencies (7.7/7.8.4) -- i.e. UML's *structural* /
  class-diagram metamodel. It deliberately does NOT cover any Behavior
  package (Activities, Interactions, UseCases, and especially
  StateMachines -- see README, `kotoba-lang/statechart` already covers
  Harel-statechart-style state machines).

  A model is a UML::Package (clause 12.2/12.4.5) -- a namespace tree of
  packagedElement children. Package nesting is real (a package's
  `:uml/packaged-element` may itself contain further `:uml/kind :package`
  elements, clause 12.4.5.6 `packagedElement`), but v1 resolves classifier
  references (Property/Parameter types, Generalization general/specific,
  Association memberEnd types) by simple NAME STRING, not a fully-qualified
  path -- this assumes classifier names are unique across the whole model,
  a real simplification of UML's actual qualifiedName resolution (sec
  7.4.3) -- see README Follow-ups.

  Element kinds (`:uml/kind`), each a UML::Classifier unless noted:
    :package            -- clause 12.2/12.4.5. Holds `:uml/packaged-element`
                            (name -> element map): nested classifiers,
                            associations, dependencies, packages.
    :class              -- clause 11.4/11.8.3 Class. `:uml/owned-attribute`
                            (Property vec), `:uml/owned-operation`
                            (Operation vec), `:uml/generalization`
                            (Generalization vec, sec 9.9.7 -- owned by the
                            SPECIFIC classifier), `:uml/interface-realization`
                            (vec of realized interface names, sec 10.5.6),
                            `:uml/abstract?` (sec 11.8.3.5 isAbstract).
    :interface          -- clause 10.4/10.5.5 Interface. `:uml/owned-attribute`
                            + `:uml/owned-operation` (sec 10.5.5.4 -- the real
                            metamodel DOES allow ownedAttribute on Interface;
                            see uml.validate for the nuance).
    :data-type          -- clause 10.5.2 DataType. `:uml/owned-attribute` +
                            `:uml/owned-operation`.
    :primitive-type     -- clause 10.5.7 PrimitiveType (a DataType with no
                            substructure). See `primitive-types` below for
                            the clause-21 standard library names.
    :enumeration        -- clause 10.5.3 Enumeration (a DataType).
                            `:uml/owned-literal` (EnumerationLiteral vec,
                            sec 10.5.4).
    :association        -- clause 11.5/11.8.1 Association. `:uml/member-end`
                            (>=2 Property-shaped end maps, sec 11.8.1.6).
    :association-class  -- clause 11.8.2 AssociationClass: both a Class
                            (`:uml/owned-attribute`/`:uml/owned-operation`)
                            and an Association (`:uml/member-end`) at once.
    :dependency         -- clause 7.7/7.8.4 Dependency (also covers Usage
                            sec 7.8.23 / Abstraction sec 7.8.1 via
                            `:uml/stereotype`). `:uml/client`/`:uml/supplier`
                            classifier names.

  `:uml/generalization` is owned by the SPECIFIC classifier per 9.9.7 (\"A
  Generalization is owned by the specific Classifier\"), so it lives as a
  vector of `{:uml/general \"OtherClassifierName\"}` maps on the specific
  classifier's own element map, not as a top-level packagedElement.

  This namespace has no execute/simulate analog (unlike xmile.execute) --
  a UML class model is a static structural description, not something you
  run."
  (:refer-clojure :exclude [class]))

;; --- shared enumerations (clause 9.9.1 / 9.9.14 / 7.8.24) ---

(def aggregation-kinds
  "AggregationKind [Enumeration], sec 9.9.1."
  #{:none :shared :composite})

(def parameter-directions
  "ParameterDirectionKind [Enumeration], sec 9.9.14."
  #{:in :out :inout :return})

(def visibility-kinds
  "VisibilityKind [Enumeration], sec 7.8.24."
  #{:public :private :protected :package})

(def primitive-types
  "The UML::PrimitiveTypes standard library (clause 21, sec 21.1/21.2):
  Integer, Boolean, String, UnlimitedNatural, Real. `uml.validate` treats
  these five names as always-resolvable Classifier references even when a
  model does not bother declaring an explicit `:primitive-type` element for
  them -- the same convenience xmile.model/xmile.validate extends to the
  TIME/DT built-in identifiers."
  #{"Integer" "Boolean" "String" "UnlimitedNatural" "Real"})

;; --- builders: Package (clause 12.2/12.4.5) ---

(defn package
  "Build a `:package` element (also used as the whole model's root Package,
  sec 12.4.5)."
  ([nm] (package nm nil))
  ([nm opts] (merge {:uml/kind :package :uml/name nm :uml/packaged-element {}} opts)))

(defn add-element
  "assoc `el` into `pkg`'s `:uml/packaged-element`, keyed by its `:uml/name`
  (sec 12.4.5.6 packagedElement)."
  [pkg el]
  (assoc-in pkg [:uml/packaged-element (:uml/name el)] el))

;; --- builders: Classifiers (Class 11.4/11.8.3, Interface 10.4/10.5.5,
;;     DataType 10.5.2, PrimitiveType 10.5.7, Enumeration 10.5.3) ---

(defn- classifier
  [kind nm opts]
  (merge {:uml/kind kind :uml/name nm :uml/visibility :public
          :uml/owned-attribute [] :uml/owned-operation [] :uml/generalization []}
         opts))

(defn class
  "Build a `:class` element (sec 11.4/11.8.3). `opts` may set `:uml/abstract?`
  (sec 11.8.3.5 isAbstract) or `:uml/interface-realization` (vec of realized
  interface names, sec 10.5.6)."
  ([nm] (class nm nil))
  ([nm opts]
   (classifier :class nm (merge {:uml/abstract? false :uml/interface-realization []} opts))))

(defn interface
  "Build an `:interface` element (sec 10.4/10.5.5)."
  ([nm] (interface nm nil))
  ([nm opts] (classifier :interface nm opts)))

(defn data-type
  "Build a `:data-type` element (sec 10.5.2)."
  ([nm] (data-type nm nil))
  ([nm opts] (classifier :data-type nm opts)))

(defn primitive-type
  "Build a `:primitive-type` element (sec 10.5.7). Prefer referencing one of
  `primitive-types` by name unless you need a custom primitive."
  ([nm] (primitive-type nm nil))
  ([nm opts] (classifier :primitive-type nm opts)))

(defn enumeration
  "Build an `:enumeration` element (sec 10.5.3). `opts` may set
  `:uml/owned-literal` directly; otherwise use `add-literal`."
  ([nm] (enumeration nm nil))
  ([nm opts] (classifier :enumeration nm (merge {:uml/owned-literal []} opts))))

(defn enumeration-literal
  "Build an EnumerationLiteral map (sec 10.5.4)."
  [nm] {:uml/name nm})

(defn add-literal
  "conj `lit` (an enumeration-literal map) onto `enum`'s `:uml/owned-literal`
  (sec 10.5.3.4 ownedLiteral)."
  [enum lit]
  (update enum :uml/owned-literal (fnil conj []) lit))

;; --- builders: Property / attribute (sec 9.5/9.9.17), Operation (sec
;;     9.6/9.9.11), Parameter (sec 9.9.13) ---

(defn property
  "Build a Property (attribute) map (sec 9.9.17). `type-name` is the
  referenced Classifier's `:uml/name` (this library resolves type
  references by name, not by object identity -- `uml.validate` checks that
  the name resolves to a known Classifier or a `primitive-types` name).

  Multiplicity (sec 7.8.8 MultiplicityElement, notation `[lower..upper]`
  sec 7.8.8.4): `:uml/lower`/`:uml/upper` default to 1/1 (a library
  convenience default -- the spec itself does not mandate a default
  multiplicity for Property). `:uml/upper` may be a non-negative integer or
  `:*` for UnlimitedNatural's unlimited value (sec 7.8.8.5 /upper, clause 21
  UnlimitedNatural).

  `:uml/aggregation` (sec 9.9.17.5, one of `aggregation-kinds`) defaults to
  `:none`. `:uml/static?` (sec 9.9.6 Feature::isStatic) and
  `:uml/read-only?` (sec 9.9.21 StructuralFeature::isReadOnly) default to
  false. `:uml/default-value` (sec 9.9.17.6 defaultValue) is an opaque
  string, unset by default."
  ([nm type-name] (property nm type-name nil))
  ([nm type-name opts]
   (merge {:uml/name nm :uml/type type-name
           :uml/lower 1 :uml/upper 1
           :uml/aggregation :none
           :uml/visibility :public
           :uml/static? false
           :uml/read-only? false}
          opts)))

(defn assoc-end
  "Build a Property map to use as an Association's member end (sec 9.9.17.6
  Association Ends / 11.8.1.6 memberEnd). Adds `:uml/navigable?` (default
  true) on top of `property` -- sec 11.5.3.1 defines navigability as derived
  from WHERE the end Property is owned (a navigableOwnedEnd of the
  Association vs. owned by the Classifier at the opposite end); this
  library's v1 instead stores navigability as an explicit boolean flag per
  end rather than modeling that ownership distinction (see README
  Follow-ups)."
  ([nm type-name] (assoc-end nm type-name nil))
  ([nm type-name opts] (property nm type-name (merge {:uml/navigable? true} opts))))

(defn operation
  "Build an Operation map (sec 9.9.11). `:uml/abstract?` (sec 9.9.2
  BehavioralFeature::isAbstract) and `:uml/static?` (sec 9.9.6
  Feature::isStatic) default to false."
  ([nm] (operation nm nil))
  ([nm opts]
   (merge {:uml/name nm :uml/owned-parameter []
           :uml/visibility :public
           :uml/abstract? false
           :uml/static? false}
          opts)))

(defn parameter
  "Build a Parameter map (sec 9.9.13). `:uml/direction` (sec 9.9.14
  ParameterDirectionKind: `:in`/`:out`/`:inout`/`:return`) defaults to `:in`
  per sec 9.9.13.4. Multiplicity defaults mirror `property`."
  ([nm type-name] (parameter nm type-name nil))
  ([nm type-name opts]
   (merge {:uml/name nm :uml/type type-name :uml/direction :in
           :uml/lower 1 :uml/upper 1}
          opts)))

(defn add-attribute [classifier* prop] (update classifier* :uml/owned-attribute (fnil conj []) prop))
(defn add-operation [classifier* op] (update classifier* :uml/owned-operation (fnil conj []) op))
(defn add-parameter [op param] (update op :uml/owned-parameter (fnil conj []) param))

(defn add-generalization
  "conj a Generalization (sec 9.9.7: general/specific) onto `classifier*`'s
  own `:uml/generalization` -- a Generalization is owned by the SPECIFIC
  classifier, so `classifier*` plays the specific role and `general-name`
  names the general Classifier."
  [classifier* general-name]
  (update classifier* :uml/generalization (fnil conj []) {:uml/general general-name}))

(defn add-interface-realization
  "conj `interface-name` onto a Class's `:uml/interface-realization` (sec
  10.5.6 InterfaceRealization: this Class is the implementingClassifier,
  `interface-name` is the contract)."
  [class* interface-name]
  (update class* :uml/interface-realization (fnil conj []) interface-name))

;; --- builders: Association / AssociationClass (sec 11.5/11.8.1, 11.8.2),
;;     Dependency (sec 7.7/7.8.4) ---

(defn association
  "Build an `:association` element (sec 11.5/11.8.1). `ends` is a vector of
  >=2 `assoc-end` maps (sec 11.8.1.6 memberEnd). Association is itself a
  Classifier (sec 11.8.1.3 Generalizations: Relationship, Classifier), so
  it carries the same baseline `:uml/owned-attribute`/`:uml/owned-operation`/
  `:uml/generalization` vectors as `class`/`interface`/etc (sec 11.8.1.8's
  \"specialized_end_number\" constraint presupposes Associations can
  specialize other Associations) -- in practice these are usually empty for
  a plain (non-AssociationClass) Association."
  ([nm ends] (association nm ends nil))
  ([nm ends opts]
   (merge (classifier :association nm nil)
          {:uml/member-end (vec ends)}
          opts)))

(defn association-class
  "Build an `:association-class` element (sec 11.8.2): both a Class
  (`:uml/owned-attribute`, `:uml/abstract?`, `:uml/interface-realization` --
  sec 11.8.2.3 Generalizations lists Class, Association) and an Association
  (`:uml/member-end`) at once."
  ([nm ends] (association-class nm ends nil))
  ([nm ends opts]
   (merge (classifier :association-class nm {:uml/abstract? false :uml/interface-realization []})
          {:uml/member-end (vec ends)}
          opts)))

(defn dependency
  "Build a `:dependency` element (sec 7.7/7.8.4). `:uml/stereotype` may be
  `:usage` (sec 7.8.23 Usage) or `:abstraction` (sec 7.8.1 Abstraction) to
  narrow the generic Dependency; defaults to plain `:dependency`."
  ([client-name supplier-name] (dependency client-name supplier-name nil))
  ([client-name supplier-name opts]
   (merge {:uml/kind :dependency :uml/name (str client-name "-to-" supplier-name)
           :uml/client client-name :uml/supplier supplier-name
           :uml/stereotype :dependency}
          opts)))

;; --- queries ---

(def classifier-kinds
  #{:class :interface :data-type :primitive-type :enumeration :association :association-class})

(defn- packaged-elements [pkg] (vals (:uml/packaged-element pkg {})))

(defn all-elements
  "Flatten `pkg` and every nested `:package` element into a single {name
  element} map (v1 assumes globally-unique classifier names -- see
  namespace docstring)."
  [pkg]
  (reduce (fn [acc el]
            (if (= :package (:uml/kind el))
              (merge acc (all-elements el))
              (assoc acc (:uml/name el) el)))
          {}
          (packaged-elements pkg)))

(defn lookup [pkg nm] (get (all-elements pkg) nm))

(defn kind? [k el] (= k (:uml/kind el)))

(defn classifiers [pkg] (filter #(contains? classifier-kinds (:uml/kind %)) (vals (all-elements pkg))))
(defn classes [pkg] (filter (partial kind? :class) (classifiers pkg)))
(defn interfaces [pkg] (filter (partial kind? :interface) (classifiers pkg)))
(defn data-types [pkg] (filter (partial kind? :data-type) (classifiers pkg)))
(defn primitive-type-elements [pkg] (filter (partial kind? :primitive-type) (classifiers pkg)))
(defn enumerations [pkg] (filter (partial kind? :enumeration) (classifiers pkg)))
(defn associations [pkg] (filter #(contains? #{:association :association-class} (:uml/kind %)) (classifiers pkg)))
(defn dependencies [pkg] (filter (partial kind? :dependency) (vals (all-elements pkg))))
(defn packages [pkg] (filter (partial kind? :package) (packaged-elements pkg)))

(defn attributes-of [pkg classifier-name] (:uml/owned-attribute (lookup pkg classifier-name) []))
(defn operations-of [pkg classifier-name] (:uml/owned-operation (lookup pkg classifier-name) []))
(defn literals-of [pkg enum-name] (:uml/owned-literal (lookup pkg enum-name) []))
(defn member-ends [pkg assoc-name] (:uml/member-end (lookup pkg assoc-name) []))

(defn generalizations-of
  "This classifier's own Generalizations (sec 9.9.7), each annotated with
  `:uml/specific` for convenience."
  [pkg classifier-name]
  (mapv #(assoc % :uml/specific classifier-name)
        (:uml/generalization (lookup pkg classifier-name) [])))

(defn all-supertypes
  "Transitive closure of `classifier-name`'s Generalization graph (sec 9.9.7
  general/specific) -- every direct-or-indirect general Classifier, as a
  set of names. Cycle-safe (a legal model has none -- see uml.validate --
  but this query must not hang on an illegal one)."
  [pkg classifier-name]
  (loop [frontier [classifier-name] seen #{} result #{}]
    (if (empty? frontier)
      result
      (let [nm (first frontier)
            more (rest frontier)]
        (if (contains? seen nm)
          (recur more seen result)
          (let [generals (map :uml/general (:uml/generalization (lookup pkg nm) []))]
            (recur (into more generals) (conj seen nm) (into result generals))))))))

(defn associations-touching
  "All Association/AssociationClass elements with a member end typed
  `classifier-name`."
  [pkg classifier-name]
  (filter (fn [a] (some #(= classifier-name (:uml/type %)) (:uml/member-end a)))
          (associations pkg)))

(defn interface-realizations-of
  "The names of Interfaces `classifier-name` realizes (sec 10.5.6)."
  [pkg classifier-name]
  (:uml/interface-realization (lookup pkg classifier-name) []))
