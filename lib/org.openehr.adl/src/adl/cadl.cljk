(ns adl.cadl
  "cADL (Constraint Archetype Definition Language) -- the grammar of an
  archetype's `definition` section: a tree of RM-object constraints, each
  optionally node-identified (`[at0001]`) and occurrence/cardinality
  bounded, down to leaf constraints on primitive values (intervals, coded
  terminology, enumerations, ordinals).

  The grammar has a structural alternation this parser leans on directly,
  instead of guessing from token shape at every brace: an OBJECT's `{...}`
  body is always a list of ATTRIBUTES (`data matches {...}`), and an
  ATTRIBUTE's `{...}` body is always either `*`, a list of OBJECTS
  (`HISTORY[at0001] matches {...} EVENT[at0002] matches {...}`), or a list
  of primitive alternatives (`True, False` / `0, 2, 3, 4` /
  `0|[local::at0038], 1|[local::at0039]`). Depth alone disambiguates
  `data matches {...}` (an attribute; body is objects) from
  `DV_TEXT matches {*}` (an object; body is `*`) even though both are
  `IDENT matches {...}` at the token level -- see `parse-attr-list` vs
  `parse-alternatives` below, which is why this parser does not need the
  \"is this identifier a known RM type name\" heuristic a token-stream
  parser would be stuck with.

  Primitive-constraint OBJECTS (`C_DV_QUANTITY <property = <...> ...>`) are
  the one place cADL and dADL are textually identical, so their body is
  parsed by literally calling back into `adl.dadl` rather than re-deriving
  the same grammar."
  (:require [kotoba.lang.text :as str]
            [adl.lexer :as lex]
            [adl.dadl :as dadl]
            [adl.path :as path]))

;; ---------------------------------------------------------------------
;; intervals: `{0..1}` occurrences, `{1..*; unordered}` cardinality,
;; `|0.0..100.0|` / `|>=0|` / `|2|` numeric-value constraints
;; ---------------------------------------------------------------------

(defn- read-bound [s i]
  (let [j (lex/skip-ws-and-comments s i)]
    (if (lex/peek-lit? s j "*")
      [:* (lex/expect s j "*")]
      (lex/read-number s j))))

(defn parse-braced-interval
  "`{lower}` (exact) or `{lower..upper}`, optionally `; ordered`/
  `; unordered` (cardinality only). `s[i]` must be the opening `{`."
  [s i]
  (let [j (lex/expect s i "{")
        [lo j2] (read-bound s j)
        [lo hi j3] (if (lex/peek-lit? s j2 "..")
                     (let [j4 (lex/expect s j2 "..")
                           [hi j5] (read-bound s j4)]
                       [lo hi j5])
                     [lo lo j2])
        [ordered? j6] (if (lex/peek-lit? s j3 ";")
                         (let [j4 (lex/expect s j3 ";")]
                           (cond
                             (lex/peek-lit? s j4 "unordered") [false (lex/expect s j4 "unordered")]
                             (lex/peek-lit? s j4 "ordered") [true (lex/expect s j4 "ordered")]
                             :else (throw (lex/adl-error :adl/expected-ordering {:at j4}))))
                         [nil j3])]
    [{:lower lo :upper hi :ordered? ordered?} (lex/expect s j6 "}")]))

(defn- bound-str
  "`:*` (unbounded, from read-bound) prints as the literal `*` -- NOT via
  plain `str`, which would print the keyword as `:*` (colon and all) and
  silently corrupt every unbounded interval on round-trip. Caught exactly
  this way: `{1..*}` serialized to `{1..:*}`, which then failed to
  re-parse -- a direct instance of the class of bug this library's
  round-trip test exists to catch, just with a keyword instead of a
  ClojureScript `(int c)` this time."
  [b]
  (if (= :* b) "*" (str b)))

(defn- interval-str [{:keys [lower upper ordered?]}]
  (str "{" (bound-str lower) (when (not= lower upper) (str ".." (bound-str upper)))
       (when (some? ordered?) (str "; " (if ordered? "ordered" "unordered")))
       "}"))

;; parse-piped-interval / piped-interval-str live in adl.dadl -- a piped
;; interval is also a legal dADL primitive VALUE (`magnitude = <|>=0.0|>`
;; inside a C_DV_QUANTITY's dADL-shaped attribute list), not only a cADL
;; construct, so both namespaces need it and dadl is the one cadl already
;; depends on.
(def parse-piped-interval dadl/parse-piped-interval)
(def piped-interval-str dadl/piped-interval-str)

;; ---------------------------------------------------------------------
;; leaf terms inside an attribute's primitive-alternatives body
;; ---------------------------------------------------------------------

(defn- parse-ordinal-or-number [s i]
  (let [[n j] (lex/read-number s i)]
    (if (lex/peek-lit? s j "|")
      (let [j2 (lex/expect s j "|")
            [code j3] (dadl/parse-code-phrase s j2)]
        [{:adl/kind :ordinal :value n :code code} j3])
      [{:adl/kind :literal :value n} j])))

(defn- parse-alt-term [s i]
  (let [j (lex/skip-ws-and-comments s i)]
    (cond
      (lex/peek-lit? s j "\"") (let [[v k] (lex/read-string-literal s j)] [{:adl/kind :literal :value v} k])
      (lex/peek-lit? s j "True") [{:adl/kind :literal :value true} (lex/expect s j "True")]
      (lex/peek-lit? s j "False") [{:adl/kind :literal :value false} (lex/expect s j "False")]
      (lex/peek-lit? s j "|") (let [[iv k] (parse-piped-interval s j)] [{:adl/kind :interval :interval iv} k])
      (lex/peek-lit? s j "[") (let [[cp k] (dadl/parse-code-phrase s j)] [(assoc cp :adl/kind :code-phrase) k])
      (or (lex/digit-ch? (lex/char-at s j)) (lex/peek-lit? s j "-")) (parse-ordinal-or-number s j)
      :else (throw (lex/adl-error :adl/expected-alt-term
                                   {:at j :context (subs s j (min (count s) (+ j 40)))})))))

;; ---------------------------------------------------------------------
;; c_object: TYPE[node-id]? occurrences? matches BODY, or the primitive
;; `TYPE <key=<val>...>` form, or `TYPE<PARAM> matches BODY`.
;; ---------------------------------------------------------------------

(declare parse-attr-list parse-alternatives)

(defn- type-name-shape? [tok] (boolean (re-matches #"[A-Z][A-Z0-9_]*" tok)))

(defn- parse-type-tail
  "After TYPE (and, if present, `<PARAM>`) has been read: optional
  `[node-id]`, optional `occurrences matches {..}`, then `matches` and the
  body. Returns [c-object next-index] -- like every other parse function
  here, NOT a map with the end position folded in as a field. (An earlier
  version did exactly that, tagging the map with `:end`; nested c-objects
  then carried source-position noise into their own structure, and two
  otherwise-identical archetypes parsed from different-length source text
  compared as unequal purely because their `:end`s differed -- caught by
  the round-trip test, which is exactly the case for keeping position out
  of the value in the first place.)"
  [s i type-name type-param]
  (let [j (lex/skip-ws-and-comments s i)
        [node-id j2] (if (= "[" (lex/char-at s j))
                       (let [k (lex/expect s j "[")
                             [nid k2] (lex/read-dotted-code s k)]
                         [nid (lex/expect s k2 "]")])
                       [nil j])
        [occ j3] (if (lex/peek-lit? s j2 "occurrences")
                   (let [k (lex/expect s j2 "occurrences")
                         k2 (lex/expect s k "matches")]
                     (parse-braced-interval s k2))
                   [nil j2])
        j4 (lex/expect s j3 "matches")
        j5 (lex/expect s j4 "{")
        [comment j6] (lex/trailing-comment s j5)]
    (if (lex/peek-lit? s j6 "*")
      [{:adl/kind :c-object :type type-name :type-param type-param :node-id node-id
        :occurrences occ :comment comment :form :any}
       (lex/expect s (lex/expect s j6 "*") "}")]
      (let [[attrs j7] (parse-attr-list s j6)]
        [{:adl/kind :c-object :type type-name :type-param type-param :node-id node-id
          :occurrences occ :comment comment :form :attrs :attrs attrs}
         (lex/expect s j7 "}")]))))

(defn parse-c-object
  "Returns [c-object next-index]."
  [s i]
  (let [[type-name j] (lex/read-ident s i)]
    (when-not (type-name-shape? type-name)
      (throw (lex/adl-error :adl/expected-type-name {:at i :got type-name})))
    (let [j2 (lex/skip-ws-and-comments s j)]
      (if (= "<" (lex/char-at s j2))
        (let [k (lex/expect s j2 "<")
              save-k k
              probe (try (let [[maybe-ident k1] (lex/read-ident s k)]
                           {:ident maybe-ident :after k1}) (catch #?(:clj Exception :cljs :default) _ nil))]
          (if (and probe (lex/peek-lit? s (:after probe) "="))
            ;; primitive-constraint-object form: TYPE <key = <val> ...>
            (let [[v k2] (dadl/parse-value-body s k)]
              [{:adl/kind :c-object :type type-name :type-param nil :node-id nil
                :occurrences nil :comment nil :form :primitive-object :value v}
               (lex/expect s k2 ">")])
            (if (and probe (lex/peek-lit? s (:after probe) ">"))
              ;; generic type-param: TYPE<PARAM> matches {...}
              (let [k2 (lex/expect s (:after probe) ">")]
                (parse-type-tail s k2 type-name {:type (:ident probe) :type-param nil}))
              (throw (lex/adl-error :adl/malformed-generic-or-primitive {:at save-k})))))
        (parse-type-tail s j2 type-name nil)))))

;; ---------------------------------------------------------------------
;; archetype slot: `allow_archetype TYPE[id] occurrences matches {N}
;; matches { include (path matches {/re/})+ (exclude (path matches
;; {/re/})+)? }`
;; ---------------------------------------------------------------------

(defn- read-regex-literal [s i]
  (let [j (lex/expect s i "/")
        n (count s)
        end (loop [k j] (if (and (< k n) (not= "/" (lex/char-at s k))) (recur (inc k)) k))]
    [(subs s j end) (lex/expect s end "/")]))

(defn- parse-slot-rules
  "Zero or more `attr/path matches {/regex/}` lines."
  [s i]
  (loop [rules [] k i]
    (if (or (lex/peek-lit? s k "exclude") (lex/peek-lit? s k "}"))
      [rules k]
      (let [[seg-str k1] (lex/read-dotted-ident s k)
            ;; attribute path may itself contain `/`, e.g. archetype_id/value
            [seg-str k1] (loop [acc seg-str k k1]
                           (if (= "/" (lex/char-at s k))
                             (let [[seg k2] (lex/read-dotted-ident s (inc k))]
                               (recur (str acc "/" seg) k2))
                             [acc k]))
            k2 (lex/expect s k1 "matches")
            k3 (lex/expect s k2 "{")
            [re k4] (read-regex-literal s k3)
            k5 (lex/expect s k4 "}")]
        (recur (conj rules {:path seg-str :regex re}) k5)))))

(defn- parse-archetype-slot [s i]
  (let [j (lex/expect s i "allow_archetype")
        [type-name j2] (lex/read-ident s j)
        j3 (lex/skip-ws-and-comments s j2)
        [node-id j4] (if (= "[" (lex/char-at s j3))
                       (let [k (lex/expect s j3 "[")
                             [nid k2] (lex/read-dotted-code s k)]
                         [nid (lex/expect s k2 "]")])
                       [nil j3])
        [occ j5] (if (lex/peek-lit? s j4 "occurrences")
                   (let [k (lex/expect s j4 "occurrences")
                         k2 (lex/expect s k "matches")]
                     (parse-braced-interval s k2))
                   [nil j4])
        j6 (lex/expect s j5 "matches")
        j7 (lex/expect s j6 "{")
        [comment j8] (lex/trailing-comment s j7)
        j9 (lex/expect s j8 "include")
        [include-rules j10] (parse-slot-rules s j9)
        [exclude-rules j11] (if (lex/peek-lit? s j10 "exclude")
                               (parse-slot-rules s (lex/expect s j10 "exclude"))
                               [[] j10])
        j12 (lex/expect s j11 "}")]
    [{:adl/kind :archetype-slot :type type-name :node-id node-id :occurrences occ
      :comment comment :include include-rules :exclude exclude-rules}
     j12]))

;; ---------------------------------------------------------------------
;; use_node TYPE /path
;; ---------------------------------------------------------------------

(defn- parse-use-node [s i]
  (let [j (lex/expect s i "use_node")
        [type-name j2] (lex/read-ident s j)
        j3 (lex/skip-ws-and-comments s j2)
        n (count s)
        end (loop [k j3]
              (if (and (< k n)
                       (not (lex/ws-ch? (lex/char-at s k)))
                       (not (and (= "-" (lex/char-at s k)) (= "-" (lex/char-at s (inc k))))))
                (recur (inc k))
                k))
        raw (subs s j3 end)
        [tag parsed] (path/parse raw)]
    (when (= tag :error) (throw (lex/adl-error :adl/invalid-use-node-path {:path raw :detail parsed})))
    [{:adl/kind :use-node :type type-name :path parsed} end]))

;; ---------------------------------------------------------------------
;; alternatives: an attribute's `{...}` body (objects, or primitives, or *)
;; ---------------------------------------------------------------------

(defn- object-alt? [item] (contains? #{:c-object :archetype-slot :use-node} (:adl/kind item)))

(defn parse-alternatives
  "Parses the content of an ATTRIBUTE's `{...}` body starting right after
  the `{` (any inline comment on the `{` itself already consumed by the
  caller). Returns [{:form :any | :objects | :primitives :items [...]}
  next-index], stopping at (not consuming) the closing `}`."
  [s i]
  (let [j (lex/skip-ws-and-comments s i)]
    (if (lex/peek-lit? s j "*")
      [{:form :any} (lex/expect s j "*")]
      (loop [items [] k j]
        (let [k' (lex/skip-ws-and-comments s k)]
          (if (lex/peek-lit? s k' "}")
            [{:form (if (object-alt? (first items)) :objects :primitives) :items items} k']
            (cond
              (lex/peek-lit? s k' "allow_archetype")
              (let [[slot k2] (parse-archetype-slot s k')] (recur (conj items slot) k2))

              (lex/peek-lit? s k' "use_node")
              (let [[un k2] (parse-use-node s k')] (recur (conj items un) k2))

              (and (lex/ident-start-ch? (lex/char-at s k'))
                   (not (lex/peek-lit? s k' "True"))
                   (not (lex/peek-lit? s k' "False")))
              ;; identifier-shaped and not a reserved keyword above/below
              ;; => an RM/AM type name (parse-c-object itself throws a
              ;; named error if it turns out not to satisfy the ALL-CAPS
              ;; type-name shape).
              (let [[obj k2] (parse-c-object s k')]
                (recur (conj items obj) k2))

              :else
              (let [[term k2] (parse-alt-term s k')
                    k3 (if (lex/peek-lit? s k2 ",") (lex/expect s k2 ",") k2)
                    [comment k4] (lex/trailing-comment s k3)
                    term (assoc term :comment comment)]
                (recur (conj items term) k4)))))))))

;; ---------------------------------------------------------------------
;; c_attribute: name (cardinality matches {..})? matches { ALTERNATIVES }
;; ---------------------------------------------------------------------

(defn- parse-attr
  "`name (existence matches {..})? (cardinality matches {..})? matches
  {ALTERNATIVES}`. `existence` (usually `{0..1}` / `{1..1}`) is distinct
  from `cardinality` (usually `{0..*}` / `{1..*}`): existence bounds
  whether the attribute is present at all, cardinality bounds how many
  child objects a MULTIPLE attribute holds once it is -- an archetype can
  and does specify both on the same attribute (`null_flavour existence
  matches {0..1} matches {...}` in a real published archetype)."
  [s i]
  (let [[name j] (lex/read-ident s i)
        [existence j1] (if (lex/peek-lit? s j "existence")
                          (let [k (lex/expect s j "existence")
                                k2 (lex/expect s k "matches")]
                            (parse-braced-interval s k2))
                          [nil j])
        [cardinality j2] (if (lex/peek-lit? s j1 "cardinality")
                            (let [k (lex/expect s j1 "cardinality")
                                  k2 (lex/expect s k "matches")]
                              (parse-braced-interval s k2))
                            [nil j1])
        j3 (lex/expect s j2 "matches")
        j4 (lex/expect s j3 "{")
        [comment j5] (lex/trailing-comment s j4)
        [body j6] (parse-alternatives s j5)
        j7 (lex/expect s j6 "}")]
    [{:adl/kind :c-attr :name name :existence existence :cardinality cardinality
      :comment comment :body body}
     j7]))

(defn parse-attr-list
  "Parses the content of an OBJECT's `{...}` body starting right after the
  `{` -- a non-empty sequence of attributes, since the `*` (any) case is
  handled by the caller before this is ever invoked. Returns
  [[c-attr ...] next-index], stopping at (not consuming) the closing `}`."
  [s i]
  (loop [attrs [] k i]
    (let [k' (lex/skip-ws-and-comments s k)]
      (if (lex/peek-lit? s k' "}")
        [attrs k']
        (let [[attr k2] (parse-attr s k')]
          (recur (conj attrs attr) k2))))))

;; ---------------------------------------------------------------------
;; public entry point
;; ---------------------------------------------------------------------

(defn parse
  "Parses one top-level cADL c_object (the whole `definition` section
  body) from the start of `s`. Returns `[:ok c-object]` or
  `[:error kw detail]` -- never throws."
  [s]
  (try
    (let [[obj end] (parse-c-object s 0)
          i (lex/skip-ws-and-comments s end)]
      (if (= i (count s))
        [:ok obj]
        [:error :adl/trailing-content {:at i}]))
    (catch #?(:clj Exception :cljs :default) e
      (if (lex/adl-error? (ex-data e))
        [:error (:adl/error (ex-data e)) (dissoc (ex-data e) :adl/error)]
        (throw e)))))

;; ---------------------------------------------------------------------
;; serializing
;; ---------------------------------------------------------------------

(defn- comment-suffix [c] (when (seq c) (str "\t-- " c)))

(defn- alt-term-str [{:keys [adl/kind] :as term}]
  (case kind
    :literal (dadl/value-body-str (:value term) 0)
    :code-phrase (dadl/code-phrase-str term)
    :ordinal (str (:value term) "|" (dadl/code-phrase-str (:code term)))
    :interval (piped-interval-str (:interval term))))

(declare c-object-str)

(defn- slot-rule-str [{:keys [path regex]}] (str path " matches {/" regex "/}"))

(defn- item-str [item indent]
  (case (:adl/kind item)
    :c-object (c-object-str item indent)
    :use-node (str "use_node " (:type item) " " (path/path-str (:path item))
                   (comment-suffix (:comment item)))
    :archetype-slot
    (let [pad (str/join (repeat (inc indent) "\t"))
          pad2 (str/join (repeat (+ indent 2) "\t"))]
      (str "allow_archetype " (:type item)
           (when (:node-id item) (str "[" (:node-id item) "]"))
           (when (:occurrences item) (str " occurrences matches " (interval-str (:occurrences item))))
           " matches {" (comment-suffix (:comment item)) "\n"
           pad "include\n"
           (str/join "" (for [r (:include item)] (str pad2 (slot-rule-str r) "\n")))
           (when (seq (:exclude item))
             (str pad "exclude\n" (str/join "" (for [r (:exclude item)] (str pad2 (slot-rule-str r) "\n")))))
           (str/join (repeat indent "\t")) "}"))
    (str (alt-term-str item) (comment-suffix (:comment item)))))

(defn- alternatives-str [{:keys [form items]} indent]
  (if (= form :any)
    "*"
    (let [pad (str/join (repeat (inc indent) "\t"))
          close-pad (str/join (repeat indent "\t"))]
      (cond
        (empty? items) ""

        ;; A separator-then-comment join (`str/join ",\n" (item-with-its-
        ;; own-trailing-comment ...)`) puts the `,` AFTER the comment text
        ;; of every non-last item instead of between the value and the
        ;; comment -- caught by round-tripping a real archetype's ordinal
        ;; enumeration (`0|[local::at0016], \t-- Markedly reduced`): the
        ;; comma landed on the comment, re-parsing it back as
        ;; `\"Markedly reduced,\"`. So the comma has to be placed
        ;; explicitly between the term and its comment, per item, not via
        ;; the join separator.
        (= form :primitives)
        (let [n (count items)]
          (str "\n"
               (str/join "\n"
                         (map-indexed
                          (fn [idx item]
                            (str pad (alt-term-str item)
                                 (when (< idx (dec n)) ",")
                                 (comment-suffix (:comment item))))
                          items))
               "\n" close-pad))

        :else
        (str "\n" (str/join "\n" (map #(str pad (item-str % (inc indent))) items)) "\n" close-pad)))))

(defn- attr-str [{:keys [name existence cardinality comment body]} indent]
  (let [pad (str/join (repeat indent "\t"))]
    (str pad name
         (when existence (str " existence matches " (interval-str existence)))
         (when cardinality (str " cardinality matches " (interval-str cardinality)))
         " matches {" (comment-suffix comment) (alternatives-str body indent) "}")))

(defn c-object-str
  "Serializes a parsed c-object back to cADL text at the given indent
  depth. `indent` affects only cosmetic whitespace, never
  `parse(serialize(x)) = x` (the parser ignores whitespace amount)."
  [{:keys [type type-param node-id occurrences comment form attrs value]} indent]
  (let [head (str type
                  (when type-param (str "<" (:type type-param) ">"))
                  (when node-id (str "[" node-id "]"))
                  (when occurrences (str " occurrences matches " (interval-str occurrences))))]
    (if (= form :primitive-object)
      (str type " " (dadl/value-str value indent))
      (let [pad (str/join (repeat indent "\t"))]
        (str head " matches {" (comment-suffix comment)
             (case form
               :any "*"
               :attrs (if (empty? attrs)
                        ""
                        (str "\n" (str/join "" (map #(str (attr-str % (inc indent)) "\n") attrs)) pad)))
             "}")))))

(defn definition-str
  "Serializes a full `definition` section body (the top-level c_object plus
  a trailing newline, matching how it sits under the `definition` keyword
  in an archetype)."
  [c-object]
  (c-object-str c-object 1))
