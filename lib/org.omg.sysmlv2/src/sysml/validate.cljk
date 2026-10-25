(ns sysml.validate
  "Structural validation for `sysml.model` models, returning
  `kotoba.dsl.problem`-shaped problems (`:sysml/severity :error|:warn`).

  `:error` means the model is not structurally valid SysML v2 (a locally
  resolved Usage definition of the wrong kind, a
  Specialization cycle, out-of-range Multiplicity bounds, a Connection/
  Interface Usage whose ends don't resolve to a Port/Part in scope).
  `:warn` means the model IS structurally valid, but exercises a feature
  this library deliberately does not implement in v1 (Action structural-
  only modeling with no execution semantics, satisfy/verify relationships
  with no requirements-traceability reasoning, or concrete syntax retained
  opaquely without semantic interpretation) -- see README Follow-ups.
  This mirrors `xmile.validate`'s error/warn split exactly (same
  `kotoba.dsl.problem` convention, same DFS white/gray/black cycle
  detection technique for illegal Specialization cycles as that
  namespace's `algebraic-loop-problems` uses for illegal equation cycles)."
  (:require [kotoba.lang.text :as str]
            [kotoba.dsl.problem :as problem]
            [sysml.kerml :as kerml]
            [sysml.model :as sm]))

(def domain :sysml)

(defn- err [code subject msg] (problem/problem domain :error code subject msg))
(defn- warn [code subject msg] (problem/problem domain :warn code subject msg))

(def ^:private usage-kind->definition-kind
  {:part-usage :part-definition
   :attribute-usage :attribute-definition
   :port-usage :port-definition
   :item-usage :item-definition
   :action-usage :action-definition
   :connection-usage :connection-definition
   :interface-usage :interface-definition
   :requirement-usage :requirement-definition})

(defn definition-ref-problems
  "When a Usage's optional `:sysml/definition` resolves locally, it must be
  the matching Definition kind. Untyped Usages and names resolved through
  imports/external libraries are valid SysML and are not rejected here."
  [m]
  (keep
   (fn [el]
     (when-let [expected-kind (usage-kind->definition-kind (:sysml/element-kind el))]
       (let [nm (:kerml/name el)
             dn (:sysml/definition el)
             def-el (and dn (sm/lookup m dn))]
         (when (and dn def-el
                    (not= expected-kind (:sysml/element-kind def-el)))
           (err :sysml/wrong-definition-kind [nm dn]
                (str nm "'s definition " dn " is a " (name (:sysml/element-kind def-el))
                     ", expected a " (name expected-kind)))))))
   (sm/elements m)))

(defn specialization-cycle-problems
  "Cycle-detect the Specialization graph (`:kerml/specific` ->
  `:kerml/general` edges) via DFS (white/gray/black) -- a Type can never
  transitively specialize itself."
  [m]
  (let [edges (reduce (fn [acc s] (update acc (:kerml/specific s) (fnil conj #{}) (:kerml/general s)))
                       {} (kerml/specializations m))
        color (atom {})
        cycle (atom nil)]
    (letfn [(visit [n path]
              (when-not @cycle
                (case (get @color n :white)
                  :black nil
                  :gray (reset! cycle (conj path n))
                  :white (do (swap! color assoc n :gray)
                             (doseq [d (get edges n)] (visit d (conj path n)))
                             (swap! color assoc n :black)))))]
      (doseq [n (keys edges)] (visit n []))
      (if @cycle
        [(err :sysml/specialization-cycle @cycle
              (str "illegal specialization cycle (a Type cannot transitively specialize itself): "
                   (str/join " -> " @cycle)))]
        []))))

(defn multiplicity-problems
  "Any `:kerml/multiplicity` bounds must be present, >= 0, and lower <= upper."
  [m]
  (keep
   (fn [el]
     (when-let [mult (:kerml/multiplicity el)]
       (let [nm (:kerml/name el)
             lower (:kerml/lower mult)
             upper (:kerml/upper mult)]
         (cond
           (or (nil? lower) (nil? upper))
           (err :sysml/bad-multiplicity nm (str nm "'s multiplicity is missing :kerml/lower or :kerml/upper"))

           (neg? lower)
           (err :sysml/bad-multiplicity nm (str nm "'s multiplicity lower bound must be >= 0, got " lower))

           (and (number? upper) (neg? upper))
           (err :sysml/bad-multiplicity nm (str nm "'s multiplicity upper bound must be >= 0, got " upper))

           (and (number? upper) (> lower upper))
           (err :sysml/bad-multiplicity nm
                (str nm "'s multiplicity lower bound (" lower ") must be <= upper bound (" upper ")"))))))
   (sm/elements m)))

(defn connection-end-problems
  "Every Connection/Interface Usage's `:sysml/ends` must resolve to an
  existing PortUsage or PartUsage in scope (i.e. a known element of the
  model)."
  [m]
  (mapcat
   (fn [el]
     (if (contains? #{:connection-usage :interface-usage} (:sysml/element-kind el))
       (let [nm (:kerml/name el)]
         (keep
          (fn [end-name]
            (let [end-el (sm/lookup m end-name)]
              (cond
                (and (nil? end-el)
                     (not (or (str/includes? end-name ".")
                              (str/includes? end-name "::"))))
                (err :sysml/dangling-connection-end [nm end-name]
                     (str nm "'s end " end-name " does not resolve to any element in scope"))

                (and end-el
                     (not (contains? #{:port-usage :part-usage}
                                     (:sysml/element-kind end-el))))
                (err :sysml/dangling-connection-end [nm end-name]
                     (str nm "'s end " end-name " must be a PortUsage or PartUsage, got "
                          (name (:sysml/element-kind end-el)))))))
          (:sysml/ends el)))
       []))
   (sm/elements m)))

(defn scope-out-problems
  "Elements that are structurally valid but exercise a v1 scope-out:
  Action Definitions/Usages (structural only, no execution semantics) and
  satisfy/verify relationship elements (structural traceability only, no
  requirements-reasoning engine), plus opaque concrete-syntax elements."
  [m]
  (keep
   (fn [el]
     (case (:sysml/element-kind el)
       (:action-definition :action-usage)
       (warn :sysml/structural-only-action (:kerml/name el)
             (str (:kerml/name el) " is an Action Definition/Usage modeled structurally only -- "
                  "no execution semantics (v1 scope-out, see README)"))

       (:satisfy-requirement-usage :verify-requirement-usage)
       (warn :sysml/no-requirements-reasoning (:kerml/name el)
             (str (:kerml/name el) " models a satisfy/verify relationship structurally only -- "
                  "no requirements-traceability reasoning is performed (v1 scope-out, see README)"))

       :opaque-syntax
       (warn :sysml/uninterpreted-syntax (:kerml/name el)
             (str (:kerml/name el) " preserves concrete syntax that is not yet "
                  "semantically interpreted by sysml.model"))

       nil))
   (sm/elements m)))

(defn validate
  "All problems for `m`, most structural first."
  [m]
  (vec (concat (definition-ref-problems m)
               (specialization-cycle-problems m)
               (multiplicity-problems m)
               (connection-end-problems m)
               (scope-out-problems m))))

(defn errors [problems] (problem/errors domain problems))
(defn warnings [problems] (problem/warnings domain problems))
(defn valid? [problems] (problem/valid? domain problems))
