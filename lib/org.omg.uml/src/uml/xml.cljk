(ns uml.xml
  "Convert between an already-parsed XMI element tree and the uml.model EDN.
  Does NOT parse XML text -- the host parses XML first (e.g.
  clojure.data.xml on the JVM, DOMParser/goog.dom.xml on ClojureScript)
  into the generic shape `{:tag :packagedElement :attrs {:xmi:type
  \"uml:Class\" :name \"...\"} :content [...]}` (exactly what
  clojure.data.xml/parse or cljs.xml/parse already produce); this namespace
  is pure data transformation, zero I/O, zero XML-parsing deps.

  XMI (XML Metadata Interchange) is the real OMG-standard wire format UML
  tools (Papyrus, MagicDraw, Enterprise Architect, ...) export/import. This
  namespace models a PRAGMATIC SUBSET of what those tools actually emit for
  Class-diagram content -- `packagedElement` children discriminated by an
  `xmi:type` attribute (e.g. `xmi:type=\"uml:Class\"`), `ownedAttribute`,
  `ownedOperation`/`ownedParameter`, and Association's `ownedEnd` pattern --
  NOT the full XMI 2.x conformance machinery (no `xmi:id`/`xmi:idref`
  cross-reference resolution, no `xmlns`/namespace-prefix handling, no
  `xmi:XMI` envelope, no Diagram Interchange `uml:Diagram`/notation layer).
  Concretely:

  - Cross-references (a Property's type, a Generalization's general, an
    Association's memberEnd, an InterfaceRealization's contract) are
    resolved by the referenced Classifier's plain `name` STRING, not by
    `xmi:id`/`xmi:idref`. Real XMI-conformant tools always assign an
    `xmi:id` to every element and reference it by `xmi:idref` (or `href` for
    externally-defined types, e.g. the standard PrimitiveTypes library) --
    this library's `uml.model` identifies classifiers by name, not object
    identity, so name-based reference strings are the natural fit, but a
    document `uml.xml/emit-doc` produces is therefore only guaranteed to
    round-trip back through `uml.xml/parse-doc`, not to import cleanly into
    a real XMI-conformant tool (see README Follow-ups).
  - Every Association end is emitted uniformly as a nested `ownedEnd`
    Property with an explicit `navigable` boolean attribute. Real UML
    instead DERIVES navigability from ownership location (sec 11.5.3.1: an
    end owned by the Classifier at the OPPOSITE end, or listed in
    `navigableOwnedEnd`, is navigable) and lets a non-navigable end be
    either an `ownedEnd` of the Association OR a class-owned `ownedAttribute`
    elsewhere in the document. This library does not model that ownership
    distinction (see uml.model/assoc-end and README Follow-ups).
  - Multiplicity is flattened to `lower`/`upper` attributes directly on the
    owning element. Real tools typically nest `lowerValue`/`upperValue`
    child elements typed `uml:LiteralInteger`/`uml:LiteralUnlimitedNatural`
    (sec 7.8.8.6) -- this library trades that fidelity for simplicity.

  Round-trip guarantee (for well-formed data, produced by this library):
    (= model (parse-doc (emit-doc model)))"
  (:require [kotoba.lang.text :as str]))

;; --- generic parsed-XML element accessors (same shape xmile.xml uses) ---

(defn- tag-kw [t] (keyword (name t)))
(defn- tag= [elem t] (and (map? elem) (= (tag-kw (:tag elem)) t)))
(defn- elem-children [elem] (filter map? (:content elem)))
(defn- by-tag [elem t] (filter #(tag= % t) (elem-children elem)))
(defn- attr [elem k] (get (:attrs elem) k))
(defn- elem [tag attrs content] (cond-> {:tag tag} (seq attrs) (assoc :attrs attrs) true (assoc :content (vec content))))
(defn- text-elem [tag s] (elem tag {} [s]))
(defn- text-of [elem] (str/trim (apply str (filter string? (:content elem)))))
(defn- child-text [elem t]
  (some-> (first (by-tag elem t)) text-of (as-> s (when (seq s) s))))

(defn- parse-int* [s] #?(:clj (Integer/parseInt s) :cljs (js/parseInt s 10)))
(defn- bool-attr [elem k] (= "true" (attr elem k)))
(defn- bool->str [b] (str (boolean b)))

(defn- parse-upper [s] (if (= s "*") :* (parse-int* s)))
(defn- upper->str [u] (if (= u :*) "*" (str u)))

;; --- VisibilityKind (sec 7.8.24) ---

(defn- parse-visibility [elem] (if-let [v (attr elem :visibility)] (keyword v) :public))
(defn- visibility->str [v] (name (or v :public)))

;; --- Property / attribute or association end (sec 9.9.17) ---

(defn parse-property
  "Parse an `ownedAttribute`/`ownedEnd` element into a Property map. `end?`
  controls whether a `navigable` attribute is read (association ends only,
  sec 9.9.17.6 / 11.8.1.6)."
  [e end?]
  (cond-> {:uml/name (attr e :name)
           :uml/type (attr e :type)
           :uml/lower (parse-int* (or (attr e :lower) "1"))
           :uml/upper (parse-upper (or (attr e :upper) "1"))
           :uml/aggregation (keyword (or (attr e :aggregation) "none"))
           :uml/visibility (parse-visibility e)
           :uml/static? (bool-attr e :isStatic)
           :uml/read-only? (bool-attr e :isReadOnly)}
    end? (assoc :uml/navigable? (not= "false" (attr e :navigable)))
    (child-text e :defaultValue) (assoc :uml/default-value (child-text e :defaultValue))))

(defn emit-property
  [tag prop]
  (elem tag
        (cond-> {:name (:uml/name prop)
                 :type (:uml/type prop)
                 :lower (str (:uml/lower prop 1))
                 :upper (upper->str (:uml/upper prop 1))
                 :aggregation (name (:uml/aggregation prop :none))
                 :visibility (visibility->str (:uml/visibility prop))
                 :isStatic (bool->str (:uml/static? prop))
                 :isReadOnly (bool->str (:uml/read-only? prop))}
          (contains? prop :uml/navigable?) (assoc :navigable (bool->str (:uml/navigable? prop))))
        (cond-> []
          (:uml/default-value prop) (conj (text-elem :defaultValue (:uml/default-value prop))))))

;; --- Parameter (sec 9.9.13) ---

(defn parse-parameter [e]
  (cond-> {:uml/name (attr e :name)
           :uml/type (attr e :type)
           :uml/direction (keyword (or (attr e :direction) "in"))
           :uml/lower (parse-int* (or (attr e :lower) "1"))
           :uml/upper (parse-upper (or (attr e :upper) "1"))}
    (child-text e :defaultValue) (assoc :uml/default-value (child-text e :defaultValue))))

(defn emit-parameter [param]
  (elem :ownedParameter
        {:name (:uml/name param)
         :type (:uml/type param)
         :direction (name (:uml/direction param :in))
         :lower (str (:uml/lower param 1))
         :upper (upper->str (:uml/upper param 1))}
        (cond-> []
          (:uml/default-value param) (conj (text-elem :defaultValue (:uml/default-value param))))))

;; --- Operation (sec 9.9.11) ---

(defn parse-operation [e]
  {:uml/name (attr e :name)
   :uml/visibility (parse-visibility e)
   :uml/abstract? (bool-attr e :isAbstract)
   :uml/static? (bool-attr e :isStatic)
   :uml/owned-parameter (mapv parse-parameter (by-tag e :ownedParameter))})

(defn emit-operation [op]
  (elem :ownedOperation
        {:name (:uml/name op)
         :visibility (visibility->str (:uml/visibility op))
         :isAbstract (bool->str (:uml/abstract? op))
         :isStatic (bool->str (:uml/static? op))}
        (mapv emit-parameter (:uml/owned-parameter op []))))

;; --- EnumerationLiteral (sec 10.5.4) ---

(defn parse-literal [e] {:uml/name (attr e :name)})
(defn emit-literal [lit] (elem :ownedLiteral {:name (:uml/name lit)} []))

;; --- Generalization (sec 9.9.7) / InterfaceRealization (sec 10.5.6) ---

(defn parse-generalization [e] {:uml/general (attr e :general)})
(defn emit-generalization [g] (elem :generalization {:general (:uml/general g)} []))

(defn- parse-interface-realization [e] (attr e :contract))
(defn- emit-interface-realization [interface-name] (elem :interfaceRealization {:contract interface-name} []))

;; --- xmi:type <-> :uml/kind ---

(def ^:private kind->xmi-type
  {:class "uml:Class" :interface "uml:Interface" :data-type "uml:DataType"
   :primitive-type "uml:PrimitiveType" :enumeration "uml:Enumeration"
   :association "uml:Association" :association-class "uml:AssociationClass"
   :package "uml:Package"})

(def ^:private xmi-type->kind (into {} (map (fn [[k v]] [v k]) kind->xmi-type)))

(def ^:private dependency-stereotype->xmi-type
  {:dependency "uml:Dependency" :usage "uml:Usage" :abstraction "uml:Abstraction"})

(def ^:private xmi-type->dependency-stereotype
  (into {} (map (fn [[k v]] [v k]) dependency-stereotype->xmi-type)))

;; --- Classifier dispatch (Class 11.8.3, Interface 10.5.5, DataType
;;     10.5.2, PrimitiveType 10.5.7, Enumeration 10.5.3, Association
;;     11.8.1, AssociationClass 11.8.2) ---

(defn- classifier-attrs [el]
  (cond-> {:xmi:type (kind->xmi-type (:uml/kind el))
           :name (:uml/name el)
           :visibility (visibility->str (:uml/visibility el :public))}
    (contains? el :uml/abstract?) (assoc :isAbstract (bool->str (:uml/abstract? el)))))

(defn- classifier-content [el]
  (concat (mapv #(emit-property :ownedAttribute %) (:uml/owned-attribute el []))
          (mapv emit-operation (:uml/owned-operation el []))
          (mapv emit-literal (:uml/owned-literal el []))
          (mapv emit-generalization (:uml/generalization el []))
          (mapv emit-interface-realization (:uml/interface-realization el []))
          (mapv #(emit-property :ownedEnd %) (:uml/member-end el []))))

(declare emit-element parse-element)

(defn emit-classifier [el] (elem :packagedElement (classifier-attrs el) (classifier-content el)))

(defn- parse-classifier-common
  "Note the `(= kind ...)` gates below (rather than gating on whether any
  child elements are actually present) deliberately mirror uml.model's
  builders: `:uml/owned-literal` is a baseline key ONLY on `:enumeration`
  (always present, even `[]`) and `:uml/interface-realization` ONLY on
  `:class`/`:association-class` -- gating on child presence instead would
  make an element with zero literals/realizations parse back MISSING the
  key entirely, breaking round-trip `=` against a builder-made model that
  always includes it as `[]` (the same 'round-trip default-value
  asymmetry' class of bug XMILE's build ran into)."
  [e kind]
  (cond-> {:uml/kind kind
           :uml/name (attr e :name)
           :uml/visibility (parse-visibility e)
           :uml/owned-attribute (mapv #(parse-property % false) (by-tag e :ownedAttribute))
           :uml/owned-operation (mapv parse-operation (by-tag e :ownedOperation))
           :uml/generalization (mapv parse-generalization (by-tag e :generalization))}
    (contains? (:attrs e) :isAbstract) (assoc :uml/abstract? (bool-attr e :isAbstract))
    (= kind :enumeration) (assoc :uml/owned-literal (mapv parse-literal (by-tag e :ownedLiteral)))
    (contains? #{:class :association-class} kind)
    (assoc :uml/interface-realization (mapv parse-interface-realization (by-tag e :interfaceRealization)))))

(defn parse-classifier [e]
  (let [kind (xmi-type->kind (attr e :xmi:type))]
    (cond-> (parse-classifier-common e kind)
      (contains? #{:association :association-class} kind)
      (assoc :uml/member-end (mapv #(parse-property % true) (by-tag e :ownedEnd))))))

;; --- Dependency (sec 7.7/7.8.4) ---

(defn emit-dependency [d]
  (elem :packagedElement
        {:xmi:type (dependency-stereotype->xmi-type (:uml/stereotype d :dependency))
         :name (:uml/name d)
         :client (:uml/client d)
         :supplier (:uml/supplier d)}
        []))

(defn parse-dependency [e]
  {:uml/kind :dependency
   :uml/name (attr e :name)
   :uml/client (attr e :client)
   :uml/supplier (attr e :supplier)
   :uml/stereotype (xmi-type->dependency-stereotype (attr e :xmi:type) :dependency)})

;; --- Package (sec 12.2/12.4.5), the recursive packagedElement container ---

(defn- emit-children [pkg] (mapv emit-element (vals (:uml/packaged-element pkg {}))))

(defn- parse-children [e]
  (into {} (for [c (elem-children e)
                 :when (tag= c :packagedElement)
                 :let [pel (parse-element c)]]
             [(:uml/name pel) pel])))

(defn emit-package [pkg]
  (elem :packagedElement {:xmi:type "uml:Package" :name (:uml/name pkg)} (emit-children pkg)))

(defn parse-package [e]
  {:uml/kind :package :uml/name (attr e :name) :uml/packaged-element (parse-children e)})

;; --- top-level element dispatch ---

(defn emit-element [el]
  (case (:uml/kind el)
    :package (emit-package el)
    :dependency (emit-dependency el)
    (emit-classifier el)))

(defn parse-element [e]
  (let [xt (attr e :xmi:type)]
    (cond
      (= xt "uml:Package") (parse-package e)
      (contains? xmi-type->dependency-stereotype xt) (parse-dependency e)
      :else (parse-classifier e))))

;; --- whole-document root (real XMI wraps a `uml:Model` under an `xmi:XMI`
;;     envelope this library does not model; see namespace docstring) ---

(defn emit-doc [pkg] (elem :uml:Model {:name (:uml/name pkg)} (emit-children pkg)))

(defn parse-doc [e]
  {:uml/kind :package :uml/name (attr e :name) :uml/packaged-element (parse-children e)})
