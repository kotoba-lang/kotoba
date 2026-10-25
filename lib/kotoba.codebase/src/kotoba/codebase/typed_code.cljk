(ns kotoba.codebase.typed-code
  "Definition identity computed from the compiler's checked KIR.

  `semantic-code` hashes a definition the codebase normalizes for itself. That
  gave content-addressed identity, but it also gave the workspace TWO answers
  to `what is this definition`: the one the codebase stores, and the one the
  compiler actually checks and lowers to a target. Nothing tied them together,
  so a definition could be stored under one identity and compiled from another,
  and neither could invalidate the other.

  Here the identity is the checked KIR itself -- the same intermediate
  representation the backends consume and qualify against. What a definition
  IS and what gets executed or compiled are then the same object, and the
  language coverage is the compiler's rather than a hand-maintained subset.

  Three things participate in identity and one deliberately does not:

  - the alpha-normalized body, so renaming a parameter is not a new definition;
  - the typed interface (parameter types, result, declared effects), so a
    signature change is a new definition even when the body is identical;
  - direct dependencies as CID links, so changing a callee necessarily changes
    every caller;
  - NOT the definition's own name, and not the names of the functions it calls.

  Alpha-normalization is not implemented here. KIR has five binding forms
  (`params`, `let`, `result-match-of`, `variant-match`, `option-match`) and
  kotoba-kir owns the walk over them, as `kotoba.kir.alpha-normalization`; this
  repository and the compiler each used to carry a copy of it, which is the
  defect kotoba-lang `lang/code-identity.edn` recorded and named the fix for.
  After renaming, any surviving original binder name that is not a known call
  target fails the compile closed -- with the limit of that check stated at the
  delegation below rather than assumed to be total."
  (:require [cbor.core :as cbor]
            [kotoba.codebase.semantic-code :as semantic]
            [kotoba.kir.alpha-normalization :as an]
            [kotoba.kir.definition-identity :as di]))

(def schema "kotoba.typed-definition.v1")
(def group-schema "kotoba.typed-group.v1")
(def member-schema "kotoba.typed-member.v1")
(def contract-version 1)

(def schema-v2
  "Identity layer 2. Not a key in the block -- see `definition-block-v2` for
  why a layer-2 block cannot carry one -- but sealed inside the interface, so
  it is recoverable from the bytes and participates in the identity."
  "kotoba.typed-definition.v2")

(def default-identity-version
  "Layer 1 stays the default. Layer-1 CIDs are published and live: kotoba-lang
  `lang/package-registry.edn` `:registry/definition-cids` names
  bafyreif7drknz5fumncb5gqdo2jqel7hulxbzwcoohq2gsds2zm26pe6oe, whose block is
  committed at `site/dist/ipfs/` and served 200 from kotoba-lang.org and
  kotoba.cloud (measured 2026-09-02). Moving them is a migration, never a
  default."
  1)

(def default-profile-version
  "`semantic/default-profile-cid` addresses the string
  \"kotoba.lang.profile.v3\"; layer 2 seals the version the ADR names rather
  than a CID of its spelling."
  3)

(def default-desugar-contract-version
  "The desugar contract version sealed when a caller does not supply one.

  It stays 1 with a reason, not by default. kotoba-lang
  `lang/elaboration-pipeline.edn` `[:contract-versions :desugar-contract]` is
  the authority for this number and it has read 2 since 2026-09-01, when `eval`
  moved out of `:forbidden-heads` and into the desugar table. Layer 1 cannot
  follow it: `bafyreif7drknz5fumncb5gqdo2jqel7hulxbzwcoohq2gsds2zm26pe6oe` is
  published, signed and served, and this constant is one of the six inputs its
  CID seals. Raising it would re-address a block other people hold.

  A LAYER-2 caller should pass the authority's current value explicitly --
  layer 2 is opt-in, nothing published points at one, and `compile-module`
  accepts `:desugar-contract-version` for exactly this. This repository does not
  read the authority itself because it does not depend on kotoba-lang; the
  compiler does, and does."
  1)

(def max-recursive-group 8)

(defn- fail! [problem data]
  (throw (ex-info (name problem) (assoc data :problem problem))))

;; ---------------------------------------------------------------------------
;; Canonical encoding of a KIR form
;;
;; Explicit rather than delegated: a KIR body carries f32 and f64 as host
;; Float/Double, which a value codec either rejects as an unwrapped number or
;; silently widens -- and widening loses exactly the distinction (f32 vs f64)
;; the type system makes.

(defn- stable-name [x]
  (cond
    (keyword? x) (if-let [n (namespace x)] (str n "/" (name x)) (name x))
    (symbol? x) (str x)
    :else (str x)))

(defn- float-bits [x]
  #?(:clj (cond
            (instance? Float x) ["f32" (long (Float/floatToIntBits ^float x))]
            (instance? Double x) ["f64" (Double/doubleToLongBits ^double x)])
     :cljs ["f64" x]))

(declare canonical-form)

(defn- canonical-pairs [m]
  (->> m
       (map (fn [[k v]] [(canonical-form k) (canonical-form v)]))
       (sort-by #(mapv (fn [b] (bit-and b 0xff)) (seq (cbor/encode (first %)))))
       vec))

(defn canonical-form
  "One KIR form as canonical, portable data.

  Fails closed on anything not enumerated: an unrecognised value in a body is a
  reason to refuse an identity, not to invent an encoding for it."
  [form]
  (cond
    (nil? form) ["nil"]
    (boolean? form) ["bool" form]
    (map? form) ["map" (canonical-pairs form)]
    (some? (float-bits form)) (float-bits form)
    #?(:clj (integer? form) :cljs (integer? form)) ["int" (str form)]
    (string? form) ["str" form]
    (keyword? form) ["kw" (stable-name form)]
    (symbol? form) ["sym" (str form)]
    (vector? form) ["vec" (mapv canonical-form form)]
    (set? form) ["set" (vec (sort-by #(mapv (fn [b] (bit-and b 0xff)) (seq (cbor/encode %)))
                                     (map canonical-form form)))]
    (sequential? form) ["list" (mapv canonical-form form)]
    :else (fail! :typed-code/unsupported-form {:form (str form) :type (str (type form))})))

(defn- reference-node
  "A dependency inside a canonical body. Shaped like `semantic-code`'s
  reference so `ir`'s traversal and CID substitution work on both."
  [cid]
  {"op" "reference" "cid" (semantic/cid-link cid)})

(defn- group-node [index]
  {"op" "recursive-reference" "index" index})

;; ---------------------------------------------------------------------------
;; Alpha normalization -- delegated to kotoba-kir
;;
;; This repository carried its own copy of the five-binder walk, and so did
;; kotoba.compiler.definition-identity: the same algorithm, over the same KIR,
;; in two places, with neither one the authority. kotoba-lang
;; lang/code-identity.edn recorded that as a residual risk of :ci8 and named the
;; fix -- into kotoba-kir, not into a third place. It landed there on
;; 2026-09-02 as kotoba.kir.alpha-normalization.
;;
;; Two things this copy did are preserved as arguments rather than as code.
;; The refusal keyword stays :typed-code/binder-not-normalized, because that is
;; this repository's diagnostic vocabulary and a consumer matching on it would
;; not know about kir's. And the leaf stays untouched (`:scalar` defaults to
;; `identity`), because `canonical-form` below admits host Float and Double
;; directly and distinguishes f32 from f64 -- a distinction the compiler's leaf,
;; which maps every host number into the identity's single f64 form, would lose.
;;
;; One behaviour changed: kir walks into a set, and this copy did not, so a
;; bound symbol inside a set survived and `verify-normalized!` refused it. That
;; widens a refusal into a CID; it moves no CID that exists, because the case it
;; changes is exactly the case that produced none.

(defn- ref-type-vector?
  "`[:ref schema-name]` names a schema, not a local. Both the renaming walk and
  dependency linking have to leave it alone; kir keeps its own copy for the
  first, and this one is for the second, which is this repository's."
  [form]
  (and (vector? form) (= :ref (first form)) (= 2 (count form))))

(def alpha-normalize
  "kotoba.kir.alpha-normalization/alpha-normalize. Kept as a name here because
  the tests and `prepare` call it, and because a reader following
  `compile-module` should not have to know which repository owns the walk to
  find out what it does."
  an/alpha-normalize)

(defn- verify-normalized!
  "Refuse an identity that still contains a source-chosen binder name, under
  this repository's problem keyword.

  MEASURED LIMIT (2026-09-02), corrected here rather than carried: the docstring
  this replaces said the check catches a binding form KIR gains later. It
  catches one that takes a name this walk already bound and lets a reference
  escape. A self-contained one -- `(loop [i 0] (+ i 1))` with no outer `i` --
  leaks nothing by this test, so the source name is sealed. See
  `kotoba.kir.alpha-normalization` for why closing that needs an operator table
  kotoba-kir does not own."
  [normalized call-targets]
  (an/verify-normalized! normalized call-targets
                         {:problem :typed-code/binder-not-normalized}))

;; ---------------------------------------------------------------------------
;; Dependency linking

(defn- link-dependencies
  "Replace call-target symbols with reference nodes, returning
  `{:body :dependencies}`. RESOLVED maps a function name to its CID; GROUP maps
  a name to its index inside the recursive group being built.

  `->REF` builds the node a dependency becomes. Layer 1 uses `reference-node`,
  a DAG-CBOR link; layer 2 uses `definition-ref`, ordinary data, because the
  canonical identity domain admits no CBOR tag. The walk itself -- what counts
  as a dependency, and the eagerness the comment below is about -- is the same
  question either way and stays written once."
  ([body resolved group] (link-dependencies body resolved group reference-node))
  ([body resolved group ->ref]
  (let [dependencies (atom #{})]
    (letfn [(walk [form]
              (cond
                (symbol? form)
                (cond
                  (contains? group form) (group-node (get group form))
                  (contains? resolved form) (do (swap! dependencies conj (get resolved form))
                                                (->ref (get resolved form)))
                  :else form)

                (ref-type-vector? form) form
                (map? form) (into {} (map (fn [[k v]] [(walk k) (walk v)])) form)
                (vector? form) (mapv walk form)
                ;; EAGER. `map` here is lazy, and the dependency set is
                ;; collected as a side effect of walking -- reading the atom
                ;; before the seq is forced returns an empty set, and a
                ;; definition whose body links a callee would be stored
                ;; declaring no dependencies at all.
                (seq? form) (apply list (mapv walk form))
                :else form))]
      (let [linked (walk body)]
        {:body linked :dependencies (vec (sort @dependencies))})))))

(defn- canonical-body
  "Canonical data for a body whose dependencies are already reference nodes."
  [form]
  (cond
    (and (map? form) (contains? form "op")) form
    (map? form) ["map" (canonical-pairs form)]
    (vector? form) ["vec" (mapv canonical-body form)]
    (set? form) ["set" (vec (sort-by #(mapv (fn [b] (bit-and b 0xff)) (seq (cbor/encode %)))
                                     (map canonical-body form)))]
    (sequential? form) ["list" (mapv canonical-body form)]
    :else (canonical-form form)))

;; ---------------------------------------------------------------------------
;; Schemas
;;
;; A definition commits to the schemas it actually reaches, not to its module's
;; whole table: otherwise an unrelated schema added elsewhere in the file would
;; change this definition's identity.

(defn- schema-refs [form]
  (into #{}
        (keep (fn [node] (when (ref-type-vector? node) (second node))))
        (tree-seq coll? seq form)))

(defn reachable-schemas [schemas roots]
  (loop [pending (vec (schema-refs roots)) seen {}]
    (if-let [name (first pending)]
      (if (contains? seen name)
        (recur (subvec pending 1) seen)
        (let [definition (get schemas name)]
          (recur (into (subvec pending 1) (schema-refs definition))
                 (assoc seen name definition))))
      (into (sorted-map-by (fn [a b] (compare (str a) (str b)))) seen))))

;; ---------------------------------------------------------------------------
;; Blocks

(defn interface-block
  "The typed interface a definition commits to, separate from its body.

  Its own block, like `semantic-code`'s type block: two definitions with the
  same interface share it, and a caller can check the contract it is linking
  against without hydrating the callee's body."
  [{:keys [params param-types result effects]} schemas]
  {"schema" "kotoba.typed-interface.v1"
   "version" 1
   "arity" (count params)
   "paramTypes" (mapv canonical-form (or param-types (vec (repeat (count params) :i64))))
   "result" (canonical-form result)
   "effects" (vec (sort (map stable-name effects)))
   "schemas" (mapv (fn [[name definition]]
                     [(canonical-form name) (canonical-form definition)])
                   schemas)})

(defn definition-block
  [{:keys [body dependencies ir-format interface-cid profile-cid hash-contract-cid]}]
  {"schema" schema
   "version" contract-version
   "irFormat" (stable-name ir-format)
   "body" body
   "interface" (semantic/cid-link interface-cid)
   "dependencies" (mapv semantic/cid-link (sort dependencies))
   "profile" (semantic/cid-link profile-cid)
   "hashContract" (semantic/cid-link hash-contract-cid)})

(defn default-contract-cid []
  (semantic/source-cid
   "kotoba.typed-definition.v1|kir-alpha-normalized|dag-cbor|sha2-256|typed-scc-v1"))

;; ---------------------------------------------------------------------------
;; Identity layer 2 -- delegate to kotoba.kir.definition-identity
;;
;; Everything above computes a canonical form THIS namespace owns. The
;; workspace contract (kotoba-lang `lang/code-identity.edn`) names
;; `kotoba.kir.definition-identity` as the implementation of definition
;; identity, and measured 2026-09-02 the two give different CIDs for the same
;; definition. Layer 2 stops being a second answer: the CID a definition gets
;; IS the payload-v2 DefCID, over the same six sealed inputs.
;;
;; One structural consequence decides the block shape, so it is worth stating
;; rather than discovering: `store/put-block!` verifies that a block re-encodes
;; to the CID it is filed under. A CID minted by `definition-cid` can therefore
;; name exactly one byte string -- the canonical identity payload. A layer-2
;; block is consequently NOT a map with a "schema" key; it IS
;; `(normalize (identity-payload ...))`, and the schema tag lives inside the
;; sealed interface, where it is part of the identity instead of decoration on
;; top of it. Layer 1 and layer 2 blocks are distinguishable without a tag
;; lookup anyway: one is a CBOR map, the other a CBOR array.
;;
;; Layer 1 remains the default and stays readable. This is a versioned
;; migration, never an in-place re-encoding -- see `default-identity-version`.

(defn- definition-ref
  "A dependency inside a layer-2 body. Ordinary data, because the canonical
  identity domain admits no CBOR tag: `normalize` refuses a tagged value
  rather than inventing an encoding for it. The CID is sealed a second time in
  `:definition/dependencies`, so nothing is lost by spelling it as a string."
  [cid]
  {:op :kir/definition-ref :cid cid})

(defn sealed-effect-row
  "The keyword effect row `kotoba.kir.definition-identity` seals, from whatever
  the compiler handed us.

  Three inputs, three outcomes, and none of them is a fallthrough:

  - a row of keywords is already the sealed vocabulary and passes through;
  - a row carrying `[:cap/call <id>]` wire vectors goes through
    `di/effect-row-from-hir`, which needs the catalog's `:id->name` and
    refuses an id the catalog cannot name;
  - anything else is refused here.

  Layer 1 does none of this: `stable-name` falls through to `str`, so a wire
  row is sealed as the STRING \"[:cap/call 9]\", which `typed-eval` reads back
  with `(map keyword)` and which can therefore never match an allowed effect.
  That is the defect this function exists not to repeat, which is why there is
  no branch here that stringifies."
  [effects {:keys [capability-id->name]}]
  (let [row (cond (nil? effects) #{}
                  (set? effects) effects
                  (coll? effects) (set effects)
                  :else (fail! :typed-code/effect-row-unbridged
                               {:effects effects
                                :hint "an effect row must be a collection"}))]
    (cond
      (every? keyword? row) row

      (some vector? row)
      (if (map? capability-id->name)
        (di/effect-row-from-hir {:effects row} {:id->name capability-id->name})
        (fail! :typed-code/effect-row-unbridged
               {:effects row
                :hint (str "a compiler wire row needs {:capability-id->name <catalog>}; "
                           "typed-code never guesses a name for a wire id, and never "
                           "seals one as a string")}))

      :else
      (fail! :typed-code/effect-row-unbridged
             {:effects row
              :hint "effect row members must be keywords, or wire [:cap/call <id>] vectors"}))))

(def ^:private max-exact-integer
  "2^53 - 1, the same bound `di/normalize` enforces."
  9007199254740991)

(defn- admit-scalar
  "One KIR scalar in the canonical identity domain `di/normalize` admits.

  Layer 1 encodes a float as its bit pattern under an `f32`/`f64` tag it owns.
  Layer 2's domain has an exact f64 form and NO f32 form, so:

  - a double becomes `di/f64`, which is the same bit pattern, losslessly;
  - a float is REFUSED. Widening it to a double would silently answer a
    different question than the type system asked, and there is no narrower
    place to put the answer;
  - an integer past +/-(2^53-1) becomes `di/i64`, because a ClojureScript
    reader has already rounded a plain literal that large.

  Idempotent: the wrappers it produces are maps of strings, which it leaves
  alone."
  [x]
  #?(:clj
     (cond
       (instance? Float x)
       (fail! :typed-code/f32-unsupported-under-v2
              {:value (str x)
               :hint (str "the canonical identity domain has an exact f64 form and no f32 "
                          "form; widening would seal a value the type system distinguishes "
                          "from the one that was written")})
       (instance? Double x) (di/f64 x)
       (integer? x) (if (<= (- max-exact-integer) x max-exact-integer) (long x) (di/i64 x))
       :else x)
     :cljs
     (cond
       (and (some? x) (not (number? x)) (not (string? x)) (not (boolean? x))
            (identical? js/BigInt (.-constructor x)))
       (let [n (js/Number x)]
         (if (js/Number.isSafeInteger n) n (di/i64 (.toString x))))
       (and (number? x) (not (integer? x))) (di/f64 x)
       (and (integer? x) (not (<= (- max-exact-integer) x max-exact-integer))) (di/i64 x)
       :else x)))

(defn admit-value
  "Rewrite a KIR form's scalars into the layer-2 identity domain.

  Applied on BOTH routes into a layer-2 payload -- compiling a module and
  migrating a stored layer-1 block -- so the two cannot disagree about how a
  literal is sealed. A shared answer is the whole point of the layer."
  [form]
  (cond
    (map? form) (into {} (map (fn [[k v]] [(admit-value k) (admit-value v)])) form)
    (vector? form) (mapv admit-value form)
    (set? form) (into #{} (map admit-value) form)
    (seq? form) (apply list (map admit-value form))
    :else (admit-scalar form)))

(defn interface-payload
  "The typed interface layer 2 seals. `schema-v2` is a member so the layer is
  recoverable from the bytes AND cannot be changed without moving the CID."
  [{:keys [params param-types result]} schemas]
  {:schema schema-v2
   :arity (count params)
   :param-types (vec (or param-types (vec (repeat (count params) :i64))))
   :result result
   :schemas (into {} schemas)})

(defn- kir-node [{:keys [params param-types result]} body]
  {:op :kir/function
   :params (vec params)
   :param-types (vec (or param-types (vec (repeat (count params) :i64))))
   :result result
   :body body})

(defn definition-payload
  "The six sealed inputs `kotoba.kir.definition-identity` addresses, built from
  an alpha-normalized, dependency-linked KIR function."
  [{:keys [function params body dependencies effect-row schemas
           profile-version desugar-contract-version]}]
  (let [function (assoc function :params params)]
    {:definition/profile-version (or profile-version default-profile-version)
     :definition/desugar-contract-version (or desugar-contract-version
                                              default-desugar-contract-version)
     :definition/kir (admit-value (kir-node function body))
     :definition/effect-row effect-row
     :definition/interface (admit-value (interface-payload function schemas))
     :definition/dependencies (vec (sort (distinct dependencies)))}))

(defn definition-block-v2
  "The bytes a layer-2 CID names. `(semantic/block-cid (definition-block-v2 p))`
  equals `(di/definition-cid p)` by construction -- both are
  `cidv1-dag-cbor` over `(cbor/encode (normalize (identity-payload p)))` -- and
  a test asserts it rather than leaving it to the reader."
  [payload]
  (di/normalize (di/identity-payload payload)))

(defn payload-block?
  "Whether BLOCK is a layer-2 block: the canonical identity payload, which is a
  tagged array rather than the tagged map layer 1 writes."
  [block]
  (boolean
   (and (vector? block)
        (= 2 (count block))
        (= "map" (nth block 0))
        (coll? (nth block 1))
        (some (fn [entry]
                (and (coll? entry)
                     (= ["kw" "kotoba.definition-identity/version"]
                        (first entry))))
              (nth block 1)))))

(defn block-identity-version
  "Which identity layer BLOCK belongs to, or nil when it is neither.

  Returning nil rather than defaulting is the point: a reader that guesses
  layer 1 for an unrecognised block is a reader that accepts a layer-2 block
  silently and decodes it as something it is not."
  [block]
  (cond
    (and (map? block)
         (contains? #{schema group-schema member-schema} (get block "schema"))) 1
    (payload-block? block) 2
    :else nil))

;; ---------------------------------------------------------------------------
;; Module compilation

(defn- prepare
  "Alpha-normalize one KIR function and canonicalize its schemas."
  [function schemas call-targets]
  (let [normalized (alpha-normalize function)]
    (verify-normalized! normalized call-targets)
    (assoc normalized
           :schemas (reachable-schemas schemas
                                       [(:param-types function) (:result function)
                                        (:body function)]))))

(defn- function-references [body names]
  (into #{} (filter names) (an/symbols-in body)))

(defn- strongly-connected
  "Small deterministic SCC partition, mirroring `semantic-code`'s."
  [graph]
  (letfn [(reachable [start]
            (loop [todo [start] seen #{}]
              (if-let [node (peek todo)]
                (if (contains? seen node)
                  (recur (pop todo) seen)
                  (recur (into (pop todo) (get graph node #{})) (conj seen node)))
                seen)))]
    (loop [remaining (set (keys graph)) out []]
      (if-let [node (first (sort-by str remaining))]
        (let [forward (reachable node)
              component (set (filter #(contains? (reachable %) node) forward))]
          (recur (set (remove component remaining)) (conj out component)))
        out))))

(defn- permutations [xs]
  (if (empty? xs)
    [[]]
    (mapcat (fn [x] (map #(cons x %) (permutations (remove #{x} xs)))) xs)))

(defn- group-candidate
  [ordered prepared resolved ir-format profile-cid hash-contract-cid]
  (let [indices (zipmap ordered (range))
        members (mapv (fn [name]
                        (let [{:keys [body params schemas]} (get prepared name)
                              function (get prepared name)
                              {:keys [body dependencies]} (link-dependencies body resolved indices)
                              interface (interface-block (assoc (:function function)
                                                                :params params)
                                                         schemas)]
                          {"interface" (semantic/cid-link (semantic/block-cid interface))
                           "body" (canonical-body body)
                           :interface-block interface
                           :dependencies dependencies}))
                      ordered)
        dependencies (vec (sort (distinct (mapcat :dependencies members))))
        block {"schema" group-schema "version" contract-version
               "irFormat" (stable-name ir-format)
               "members" (mapv #(select-keys % ["interface" "body"]) members)
               "dependencies" (mapv semantic/cid-link dependencies)
               "profile" (semantic/cid-link profile-cid)
               "hashContract" (semantic/cid-link hash-contract-cid)}]
    {:ordered ordered :block block
     :bytes (mapv #(bit-and % 0xff) (seq (cbor/encode block)))
     :interfaces (mapv :interface-block members)
     :dependencies dependencies}))

(defn- compile-group
  [component prepared resolved ir-format profile-cid hash-contract-cid]
  (when (> (count component) max-recursive-group)
    (fail! :typed-code/recursive-group-too-large {:size (count component)}))
  (let [candidates (map #(group-candidate (vec %) prepared resolved
                                          ir-format profile-cid hash-contract-cid)
                        (permutations (sort-by str component)))
        chosen (first (sort-by :bytes candidates))
        group-cid (semantic/block-cid (:block chosen))]
    {:group-cid group-cid
     :group-block (:block chosen)
     :definitions
     (into {}
           (map-indexed
            (fn [index name]
              (let [interface (nth (:interfaces chosen) index)
                    interface-cid (semantic/block-cid interface)
                    member {"schema" member-schema "version" contract-version
                            "group" (semantic/cid-link group-cid)
                            "index" index
                            "interface" (semantic/cid-link interface-cid)}]
                [name {:name name :cid (semantic/block-cid member) :block member
                       :identity-version 1
                       :interface-cid interface-cid :interface-block interface
                       :group-cid group-cid :group-block (:block chosen)
                       :dependency-cids (:dependencies chosen)}]))
            (:ordered chosen)))}))

(defn compile-module
  "Split checked KIR into per-function content-addressed definitions.

  `:definitions` seeds externally resolved names, so a module compiled against
  a namespace links to the definitions that namespace selects rather than to
  a name it hopes to find later."
  ([kir] (compile-module kir {}))
  ([kir {:keys [definitions profile-cid hash-contract-cid identity-version
                profile-version desugar-contract-version capability-id->name]
         :or {definitions {}}}]
   (let [identity-version (or identity-version default-identity-version)
         _ (when-not (contains? #{1 2} identity-version)
             (fail! :typed-code/unknown-identity-version
                    {:identity-version identity-version :known #{1 2}}))
         profile-cid (or profile-cid (semantic/default-profile-cid))
         hash-contract-cid (or hash-contract-cid (default-contract-cid))
         ir-format (:format kir)
         schemas (:schemas kir)
         functions (:functions kir)
         names (set (map :name functions))
         call-targets (into names (keys definitions))
         prepared (into {}
                        (map (fn [function]
                               [(:name function)
                                (assoc (prepare function schemas call-targets)
                                       :function function)]))
                        functions)
         graph (into {} (map (fn [[name {:keys [body]}]]
                               [name (function-references body names)]))
                     prepared)]
     (loop [pending (vec (sort-by str names))
            resolved (into {} (map (fn [[k v]] [(symbol (str k)) v])) definitions)
            output {}]
       (if (empty? pending)
         {:schema "kotoba.typed-codebase.v1"
          :ir-format ir-format
          :identity-version identity-version
          :profile-cid profile-cid
          :hash-contract-cid hash-contract-cid
          :definitions output}
         (let [ready (filter (fn [name]
                               (every? #(contains? resolved %) (get graph name)))
                             pending)]
           (if (seq ready)
             (let [compiled
                   (into {}
                         (map (fn [name]
                                (let [{:keys [body params schemas function]} (get prepared name)]
                                  (if (= 2 identity-version)
                                    (let [{:keys [body dependencies]}
                                          (link-dependencies body resolved {} definition-ref)
                                          payload
                                          (definition-payload
                                           {:function function :params params :body body
                                            :dependencies dependencies :schemas schemas
                                            :effect-row (sealed-effect-row
                                                         (:effects function)
                                                         {:capability-id->name capability-id->name})
                                            :profile-version profile-version
                                            :desugar-contract-version desugar-contract-version})]
                                      [name {:name name
                                             :cid (di/definition-cid payload)
                                             :block (definition-block-v2 payload)
                                             :identity-version 2
                                             :payload payload
                                             :dependency-cids dependencies}])
                                    (let [{:keys [body dependencies]} (link-dependencies body resolved {})
                                          interface (interface-block (assoc function :params params) schemas)
                                          interface-cid (semantic/block-cid interface)
                                          block (definition-block
                                                 {:body (canonical-body body)
                                                  :dependencies dependencies
                                                  :ir-format ir-format
                                                  :interface-cid interface-cid
                                                  :profile-cid profile-cid
                                                  :hash-contract-cid hash-contract-cid})]
                                      [name {:name name :cid (semantic/block-cid block) :block block
                                             :identity-version 1
                                             :interface-cid interface-cid :interface-block interface
                                             :dependency-cids dependencies}])))))
                         ready)]
               (recur (vec (remove (set ready) pending))
                      (into resolved (map (fn [[name {:keys [cid]}]] [name cid])) compiled)
                      (into output compiled)))
             ;; Everything left is in a cycle. Take one whose entire outward
             ;; edge set is already resolved or inside itself.
             (let [pending-set (set pending)
                   pending-graph (into {} (map (fn [name]
                                                 [name (into #{} (filter pending-set)
                                                             (get graph name))]))
                                       pending)
                   component (first (filter (fn [members]
                                              (every? #(or (contains? members %)
                                                           (contains? resolved %))
                                                      (mapcat graph members)))
                                            (strongly-connected pending-graph)))]
               (when-not component
                 (fail! :typed-code/unresolvable-recursion {:symbols (mapv str pending)}))
               ;; A recursive group is a cycle, and a cycle has no CID to link
               ;; to. Layer 1 answers that with a group block plus member
               ;; blocks; the sealed payload layer 2 addresses has exactly one
               ;; slot for dependencies and it holds CIDs. Refusing is the only
               ;; honest answer available today -- an invented encoding here
               ;; would be a third answer to `what is this definition`, which
               ;; is the defect layer 2 exists to close.
               (when (= 2 identity-version)
                 (fail! :typed-code/recursive-group-unsupported-under-v2
                        {:symbols (vec (sort (map str component)))
                         :identity-version 2
                         :hint (str "kotoba.typed-definition.v2 seals dependencies as CIDs and "
                                    "has no representation for a cycle; compile this group under "
                                    "identity-version 1")}))
               (let [compiled (compile-group component prepared resolved
                                             ir-format profile-cid hash-contract-cid)]
                 (recur (vec (remove component pending))
                        (into resolved (map (fn [[name {:keys [cid]}]] [name cid]))
                              (:definitions compiled))
                        (into output (:definitions compiled))))))))))))
