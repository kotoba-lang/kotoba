(ns kotobase.protocols.sparql.parser
  "SPARQL 1.1 Query Language TEXT -> `kotoba-lang/sparql` EDN algebra.

  `kotoba-lang/sparql` deliberately has NO text-syntax parser (its README,
  verbatim: \"Callers build the algebra tree directly as EDN ... a separate
  parser repo is the natural place for `SELECT ?s WHERE {...}` string
  syntax, if/when a caller needs it\"). The SPARQL 1.1 PROTOCOL (this repo's
  actual scope, https://www.w3.org/TR/sparql11-protocol/) is a thin HTTP
  transport around a `query` parameter that is, per the protocol spec,
  SPARQL QUERY-LANGUAGE TEXT -- so accepting it at all requires SOME
  text->algebra translation. This namespace is that translation, scoped
  deliberately: it is protocol-level SYNTAX SUGAR over the algebra
  `kotoba-lang/sparql` already implements, not a new query capability --
  every algebra node this parser ever emits is one of the 8 `:sparql/op`
  shapes that repo's README documents (`:bgp`/`:filter`/`:join`/`:union`/
  `:optional`/`:project`/`:distinct`/`:order-by`/`:slice`); this namespace
  adds zero new semantics to `sparql.core/eval-node`.

  ## Supported query-text subset (v0.1 -- read before assuming more)

  - `PREFIX p: <iri>` declarations (any number, before the query body)
  - `SELECT (DISTINCT)? (?var+ | *)`, `ASK`, `CONSTRUCT { template } WHERE
    { ... }`, `DESCRIBE <iri>+` and `DESCRIBE ?var+ WHERE { ... }`
  - `WHERE { ... }` (the `WHERE` keyword itself is optional, as in the spec)
  - inside a group: triple patterns (`s p o .`), `OPTIONAL { ... }`,
    `{ ... } UNION { ... }` (chainable), `FILTER(...)`
  - `FILTER` expressions: `=` `!=` `<` `>` `<=` `>=` between a var/IRI/
    literal operand pair, `&&` conjunction, `||` disjunction (looser than
    `&&`, per the SPARQL 1.1 grammar), unary `!` negation, `BOUND(?v)`
  - `ORDER BY ?var+` (ascending only -- see limitation below)
  - `LIMIT n`, `OFFSET n` (either order, both optional)

  ## Explicit, documented NOT-in-scope (matches `koba-lang/sparql`'s own
  carve-outs -- this parser does not attempt to cover ground that repo's
  algebra itself does not have)

  - `UNION` remains the PATTERN-level disjunction and is not the same thing
    as `||`: `||` combines truth values over one solution, `UNION` combines
    solutions. Both are supported and neither substitutes for the other.
  - **No predicate-object lists** (`s p o1 , o2`) or **property lists**
    (`s p1 o1 ; p2 o2`) -- one `s p o .` triple per statement. Write out
    each triple pattern separately.
  - **No property paths, `GRAPH`, `SERVICE`, aggregates (`COUNT`/`GROUP
    BY`/...), blank-node syntax (`_:b0`/`[...]`), `VALUES`, subqueries** --
    identical boundary to `kotoba-lang/sparql`'s algebra, which has none of
    these operators to translate into.
  - `ORDER BY` sorts unbound-first and compares across types by type name,
    so a heterogeneous column orders rather than throwing (`sparql.core`'s
    `row-comparator`). Within a type it is `compare`. This is a total order,
    not SPARQL 1.1 §15.1's full ordering — no datatype-aware numeric/date
    collation.
  - **`FILTER`'s `=`/`!=` compare terms' `:value` only** (see
    `kotobase.protocols.sparql.quads`'s ns docstring on why literal terms
    are `{:rdf/type ... :value ...}` two-key maps) -- an IRI and a literal
    that happen to share the same string `:value` would compare equal.
    Given this repo's own quad transform never emits an object-position
    IRI (see `quads/->term`), this does not arise for BGP-produced
    bindings in practice, but is stated here rather than left implicit."
  (:require [kotoba.lang.text :as str]
            [kotobase.protocols.sparql.quads :as quads]))

;; ------------------------------------------------------------- tokenizer

(def ^:private token-specs
  "[type regex], tried in order, each regex anchored to match at the START
  of the remaining input (`^...`). Order matters: more specific patterns
  (string/iriref/pname) must be tried before the generic `:ident` catch-all,
  numbers before pname (a bare `-5` shouldn't tokenize as an operator run),
  and operators like `!=`/`<=` before their single-char prefixes (`!`/`<`)."
  [[:ws       #"^[ \t\r\n]+"]
   [:comment  #"^#[^\r\n]*"]
   [:iriref   #"^<[^<>\"{}|^`\\\x00-\x20]*>"]
   [:string   #"^\"(?:[^\"\\]|\\.)*\"(?:@[A-Za-z]+(?:-[A-Za-z0-9]+)*)?(?:\^\^(?:<[^<>]*>|[A-Za-z_][A-Za-z0-9_-]*:[A-Za-z_0-9.-]*))?"]
   [:string   #"^'(?:[^'\\]|\\.)*'(?:@[A-Za-z]+(?:-[A-Za-z0-9]+)*)?(?:\^\^(?:<[^<>]*>|[A-Za-z_][A-Za-z0-9_-]*:[A-Za-z_0-9.-]*))?"]
   [:var      #"^[?$][A-Za-z_][A-Za-z0-9_]*"]
   [:number   #"^[+-]?(?:[0-9]+\.[0-9]+(?:[eE][+-]?[0-9]+)?|\.[0-9]+(?:[eE][+-]?[0-9]+)?|[0-9]+(?:[eE][+-]?[0-9]+)?)"]
   [:pname    #"^([A-Za-z_][A-Za-z0-9_-]*)?:[A-Za-z_0-9.-]*"]
   [:op       #"^(&&|\|\||!=|<=|>=|=|<|>|!)"]
   [:punct    #"^[{}().,;*]"]
   [:ident    #"^[A-Za-z][A-Za-z0-9_]*"]])

(defn- unescape-string [s]
  (-> s
      (str/replace "\\\"" "\"")
      (str/replace "\\'" "'")
      (str/replace "\\n" "\n")
      (str/replace "\\r" "\r")
      (str/replace "\\t" "\t")
      (str/replace "\\\\" "\\")))

(defn- string-token-value
  "Strip the quotes and any `@lang`/`^^datatype` suffix, unescape the body.
  We deliberately DROP lang/datatype (see ns docstring on the 2-key literal
  term shape) -- the suffix is consumed here just so it doesn't leak into
  the next token."
  [text]
  (let [quote (subs text 0 1)
        end (str/index-of text quote 1)]
    (unescape-string (subs text 1 end))))

(defn- parse-number-token
  "Same integer-vs-decimal split `kotobase.protocols.json`'s number parser
  uses (integer literal -> integral type, `.`/`e`/`E` present -> float) --
  this is what keeps a query-text literal `900000` `=`-equal to a
  materialized doc's `:budget 900000` on BOTH runtimes (cljs: only one
  number type, always equal; JVM :test compat suite: `Long` must meet
  `Long`, `Double` must meet `Double`, per `clojure.core/=`'s type-category
  rule)."
  [text]
  (if (re-find #"[.eE]" text)
    #?(:clj (Double/parseDouble text) :cljs (js/parseFloat text))
    #?(:clj (Long/parseLong text) :cljs (js/parseInt text 10))))

(defn tokenize
  "Query text -> vector of `{:type :text ...}` tokens, `:ws`/`:comment`
  dropped. Each token additionally carries a type-specific payload:
  `:var` -> `:name` (no `?`/`$`); `:string` -> `:value` (unescaped,
  unquoted); `:number` -> `:value` (parsed); `:iriref` -> `:value`
  (bracket contents); `:pname` -> `:prefix`/`:local`."
  [s]
  (loop [i 0 out (transient [])]
    (if (>= i (count s))
      (persistent! out)
      (let [remaining (subs s i)
            [type m] (some (fn [[type re]]
                             (when-let [m (re-find re remaining)]
                               [type (if (vector? m) (first m) m)]))
                           token-specs)]
        (when-not type
          (throw (ex-info (str "SPARQL parse error: unexpected character at " i)
                           {:type ::tokenize-error :index i :remaining (subs remaining 0 (min 20 (count remaining)))})))
        (let [len (count m)
              i' (+ i len)]
          (case type
            (:ws :comment) (recur i' out)
            :var     (recur i' (conj! out {:type :var :text m :name (subs m 1)}))
            :string  (recur i' (conj! out {:type :string :text m :value (string-token-value m)}))
            :number  (recur i' (conj! out {:type :number :text m :value (parse-number-token m)}))
            :iriref  (recur i' (conj! out {:type :iriref :text m :value (subs m 1 (dec (count m)))}))
            :pname   (let [ci (str/index-of m ":")]
                       (recur i' (conj! out {:type :pname :text m
                                              :prefix (subs m 0 ci) :local (subs m (inc ci))})))
            (recur i' (conj! out {:type type :text m}))))))))

;; ------------------------------------------------------------ token cursor

(defn- peek1 [state] (first (:toks @state)))
(defn- advance! [state]
  ;; `subvec` past the end throws an uncontrolled IndexOutOfBoundsException
  ;; on JVM (silently misbehaves differently on cljs) -- guard EOF here so
  ;; every malformed/truncated query text (e.g. an unclosed `{`) fails as a
  ;; clean `ex-info` `::parse-error`, the one exception shape callers
  ;; (the HTTP handler, and every `thrown?` test) actually catch for.
  (let [toks (:toks @state)]
    (when (empty? toks)
      (throw (ex-info "SPARQL parse error: unexpected end of input" {:type ::parse-error})))
    (swap! state update :toks subvec 1)
    (first toks)))
(defn- kw-tok? [tok kw]
  (and tok (= :ident (:type tok)) (= kw (str/upper (:text tok)))))
(defn- punct-tok? [tok ch] (and tok (= :punct (:type tok)) (= ch (:text tok))))
(defn- op-tok? [tok op] (and tok (= :op (:type tok)) (= op (:text tok))))
(defn- peek-kw? [state kw] (kw-tok? (peek1 state) kw))
(defn- peek-punct? [state ch] (punct-tok? (peek1 state) ch))
(defn- peek-op? [state op] (op-tok? (peek1 state) op))

(defn- fail! [msg tok]
  (throw (ex-info (str "SPARQL parse error: " msg
                        (when tok (str " (got " (pr-str (:text tok)) ")")))
                   {:type ::parse-error :token tok})))

(defn- expect-punct! [state ch]
  (let [t (advance! state)]
    (when-not (punct-tok? t ch) (fail! (str "expected '" ch "'") t))
    t))

(defn- expect-kw! [state kw]
  (let [t (advance! state)]
    (when-not (kw-tok? t kw) (fail! (str "expected " kw) t))
    t))

;; ---------------------------------------------------------------- prologue

(defn- resolve-pname [prefixes {:keys [prefix local]}]
  (if-let [base (get prefixes prefix)]
    (str base local)
    (fail! (str "unknown prefix '" prefix "'") nil)))

(defn- parse-prologue! [state]
  (loop [prefixes {}]
    (if (peek-kw? state "PREFIX")
      (do (advance! state)
          (let [pname-tok (advance! state)
                _ (when-not (= :pname (:type pname-tok)) (fail! "expected prefix:" pname-tok))
                iri-tok (advance! state)
                _ (when-not (= :iriref (:type iri-tok)) (fail! "expected <iri> after PREFIX" iri-tok))]
            (recur (assoc prefixes (:prefix pname-tok) (:value iri-tok)))))
      prefixes)))

;; -------------------------------------------------------------------- term

(defn- parse-term! [state prefixes]
  (let [t (advance! state)]
    (case (:type t)
      :var (symbol (str "?" (:name t)))
      :iriref (quads/iri (:value t))
      :pname (quads/iri (resolve-pname prefixes t))
      :string (quads/->literal (:value t))
      :number (quads/->literal (:value t))
      :ident (let [u (str/upper (:text t))]
               (cond
                 (= u "TRUE") (quads/->literal true)
                 (= u "FALSE") (quads/->literal false)
                 (= u "A") (quads/iri "urn:kotobase:rdf/type") ; SPARQL `a` shorthand
                 :else (fail! "expected an RDF term (IRI/prefixed-name/var/literal)" t)))
      (fail! "expected an RDF term (IRI/prefixed-name/var/literal)" t))))

;; ------------------------------------------------------------------ filter

(def ^:private comparison-ops #{"=" "!=" "<" ">" "<=" ">="})

(defn- operand-value [term bindings]
  (if (symbol? term) (:value (get bindings term)) (:value term)))

(defn- as-number
  "The number `v` denotes, or nil. A STRING that parses counts — a datom
  plane stringifies on write, so `30` arrives as `\"30\"` and a comparison
  that only accepted real numbers would answer nothing for every numeric
  FILTER over real data."
  [v]
  (cond
    (number? v) v
    (string? v) (when (re-matches #"\s*-?\d+(\.\d+)?\s*" v)
                  #?(:clj (Double/parseDouble (str/trim v))
                     :cljs (js/parseFloat v)))
    :else nil))

(defn- compare-operands
  "`<`/`>`/`<=`/`>=` NUMERICALLY when both sides denote numbers, and
  lexicographically otherwise — the same rule `kotobase.server.sparql`'s
  subset states (\"numeric FILTER comparison applies when both sides parse as
  numbers; lexicographic otherwise\"), so the two surfaces order the same way.

  Without it, `FILTER(?v > 25)` against a stringifying store compares a
  string to a number: on the JVM that throws, on cljs it silently answers
  false for every row. Neither is a filter."
  [f a b]
  (let [na (as-number a) nb (as-number b)]
    (if (and na nb)
      (f na nb)
      (f (compare (str a) (str b)) 0))))

(defn- compile-relational [op left right]
  (let [equality? (contains? #{"=" "!="} op)
        f (case op "=" = "!=" not= "<" < ">" > "<=" <= ">=" >=)
        num-f (case op "=" = "!=" not= "<" < ">" > "<=" <= ">=" >=)]
    (fn [b]
      (let [a (operand-value left b)
            c (operand-value right b)]
        (boolean
         (if equality?
           ;; Equality stays exact — `\"30\"` and `30` are different terms and
           ;; a query asking for one should not match the other. Only the
           ;; ORDERING comparisons need the numeric rule, which is also where
           ;; a type mismatch throws rather than merely answering false.
           (f a c)
           (compare-operands num-f a c)))))))

(declare parse-unary-expr!)

(defn- parse-primary-expr! [state prefixes]
  (cond
    (peek-punct? state "(")
    (do (advance! state)
        ;; `||` binds LOOSER than `&&` (SPARQL 1.1 grammar: ConditionalOrExpression
        ;; over ConditionalAndExpression), so the and-chain is the inner loop.
        ;; Parsing them at one level would make `a || b && c` mean `(a || b) && c`,
        ;; which is a wrong answer rather than a rejected query.
        (letfn [(and-chain []
                  (loop [left (parse-unary-expr! state prefixes)]
                    (if (peek-op? state "&&")
                      (do (advance! state)
                          (let [right (parse-unary-expr! state prefixes)]
                            (recur (fn [b] (and (left b) (right b))))))
                      left)))]
          (loop [left (and-chain)]
            (if (peek-op? state "||")
              (do (advance! state)
                  (let [right (and-chain)]
                    (recur (fn [b] (or (left b) (right b))))))
              (do (expect-punct! state ")") left)))))

    (kw-tok? (peek1 state) "BOUND")
    (do (advance! state)
        (expect-punct! state "(")
        (let [v (parse-term! state prefixes)]
          (expect-punct! state ")")
          (fn [b] (contains? b v))))

    :else
    (let [left (parse-term! state prefixes)
          t (peek1 state)]
      (if (and t (= :op (:type t)) (contains? comparison-ops (:text t)))
        (do (advance! state)
            (compile-relational (:text t) left (parse-term! state prefixes)))
        (fail! "expected a comparison operator" t)))))

(defn- parse-unary-expr! [state prefixes]
  (if (peek-op? state "!")
    (do (advance! state)
        (let [inner (parse-primary-expr! state prefixes)]
          (fn [b] (not (inner b)))))
    (parse-primary-expr! state prefixes)))

(defn- parse-filter! [state prefixes]
  ;; `FILTER` already consumed by caller. FILTER's argument is either a
  ;; parenthesized expression or (per the grammar) a bare BuiltInCall --
  ;; we only support the parenthesized form, which covers every test/real
  ;; query this repo's scope calls for.
  (parse-primary-expr! state prefixes))

;; ------------------------------------------------------------------ triple

(defn- parse-triple! [state prefixes]
  (let [s (parse-term! state prefixes)
        p (parse-term! state prefixes)
        o (parse-term! state prefixes)]
    (when (peek-punct? state ".") (advance! state))
    [s p o]))

;; --------------------------------------------------------- group pattern

(defn- add-triple [acc tp]
  (cond
    (nil? acc) {:sparql/op :bgp :patterns [tp]}
    (= :bgp (:sparql/op acc)) (update acc :patterns conj tp)
    :else {:sparql/op :join :left acc :right {:sparql/op :bgp :patterns [tp]}}))

(defn- combine [acc pattern]
  (if (nil? acc) pattern {:sparql/op :join :left acc :right pattern}))

(declare parse-group!)

(defn- parse-union-chain! [state prefixes first-pattern]
  (loop [combined first-pattern]
    (if (peek-kw? state "UNION")
      (do (advance! state)
          (recur {:sparql/op :union :left combined :right (parse-group! state prefixes)}))
      combined)))

(defn parse-group!
  "Parse one `{ ... }` GroupGraphPattern into a `:sparql/op` algebra node.
  Always returns a node (an empty `{}` becomes an always-true empty `:bgp`)."
  [state prefixes]
  (expect-punct! state "{")
  (loop [acc nil filters []]
    (cond
      (peek-punct? state "}")
      (do (advance! state)
          (reduce (fn [p pred] {:sparql/op :filter :pred pred :pattern p})
                  (or acc {:sparql/op :bgp :patterns []})
                  filters))

      (peek-kw? state "OPTIONAL")
      (do (advance! state)
          (let [inner (parse-group! state prefixes)]
            (recur (if acc {:sparql/op :optional :left acc :right inner} inner) filters)))

      (peek-kw? state "FILTER")
      (do (advance! state)
          (recur acc (conj filters (parse-filter! state prefixes))))

      (peek-punct? state "{")
      (let [pattern (parse-union-chain! state prefixes (parse-group! state prefixes))]
        (when (peek-punct? state ".") (advance! state))
        (recur (combine acc pattern) filters))

      :else
      (recur (add-triple acc (parse-triple! state prefixes)) filters))))

;; --------------------------------------------------------------- solution

(def ^:private aggregate-fns
  {"COUNT" :count "SUM" :sum "MIN" :min "MAX" :max "AVG" :avg})

(defn- parse-aggregate!
  "`(COUNT(?e) AS ?c)` / `(COUNT(DISTINCT ?e) AS ?c)` / `(COUNT(*) AS ?c)`
  -> `{:var ?c :fn :count :arg ?e :distinct? bool}`. The opening `(` is
  already consumed."
  [state]
  (let [t (advance! state)
        f (get aggregate-fns (str/upper (str (:text t))))]
    (when-not f
      (fail! (str "expected an aggregate ("
                  (str/join ", " (sort (keys aggregate-fns))) ")") t))
    (expect-punct! state "(")
    (let [distinct? (peek-kw? state "DISTINCT")
          _ (when distinct? (advance! state))
          arg (if (peek-punct? state "*")
                (do (advance! state) :*)
                (let [v (advance! state)]
                  (when-not (= :var (:type v))
                    (fail! "expected a variable or * inside the aggregate" v))
                  (symbol (str "?" (:name v)))))
          _ (expect-punct! state ")")
          _ (expect-kw! state "AS")
          out (advance! state)]
      (when-not (= :var (:type out))
        (fail! "expected a variable after AS" out))
      (expect-punct! state ")")
      (cond-> {:var (symbol (str "?" (:name out))) :fn f :arg arg}
        distinct? (assoc :distinct? true)))))

(defn- parse-var-list!
  "SELECT ?a ?b ... | SELECT * | SELECT ?a (COUNT(?b) AS ?c) ...

  -> `[output-vars aggregates]`. `output-vars` is nil only for `SELECT *`;
  an aggregate always names its own output var, so a select list containing
  one is never `*`."
  [state]
  (if (peek-punct? state "*")
    (do (advance! state) [nil []])
    (loop [vars [] aggs []]
      (cond
        (= :var (:type (peek1 state)))
        (recur (conj vars (symbol (str "?" (:name (advance! state))))) aggs)

        (peek-punct? state "(")
        (do (advance! state)
            (let [agg (parse-aggregate! state)]
              (recur (conj vars (:var agg)) (conj aggs agg))))

        :else [vars aggs]))))

(defn- parse-group-by! [state]
  (if (peek-kw? state "GROUP")
    (do (advance! state) (expect-kw! state "BY")
        (loop [vars []]
          (if (= :var (:type (peek1 state)))
            (recur (conj vars (symbol (str "?" (:name (advance! state))))))
            (if (seq vars)
              vars
              (fail! "expected a variable after GROUP BY" (peek1 state))))))
    []))

(defn- parse-order-by! [state]
  (if (peek-kw? state "ORDER")
    (do (advance! state) (expect-kw! state "BY")
        (loop [vars [] desc #{}]
          (cond
            (or (peek-kw? state "ASC") (peek-kw? state "DESC"))
            (let [desc? (peek-kw? state "DESC")]
              (advance! state)
              (expect-punct! state "(")
              (let [v (advance! state)
                    sym (symbol (str "?" (:name v)))]
                (expect-punct! state ")")
                (recur (conj vars sym) (cond-> desc desc? (conj sym)))))

            (= :var (:type (peek1 state)))
            (recur (conj vars (symbol (str "?" (:name (advance! state))))) desc)

            :else [vars desc])))
    [[] #{}]))

(defn- parse-limit-offset! [state]
  (loop [limit nil offset nil]
    (cond
      (peek-kw? state "LIMIT")
      (do (advance! state) (recur (:value (advance! state)) offset))

      (peek-kw? state "OFFSET")
      (do (advance! state) (recur limit (:value (advance! state))))

      :else [limit offset])))

;; ----------------------------------------------------------------- top level

(defn parse
  "SPARQL query text -> `{:form :select|:ask|:construct|:describe|:describe-solutions
                           :output-vars [sym...] or nil (SELECT * / ASK)
                           :algebra <full sparql.core algebra tree>
                           :warnings [string...]}`.
  `:algebra` already has ORDER BY / SELECT projection / DISTINCT / LIMIT-
  OFFSET applied (in that order -- order-by needs the projected-out vars
  still present, so it must wrap BEFORE :project). For `ASK`, `:algebra` is
  the bare WHERE pattern (ASK ignores DISTINCT/ORDER/LIMIT/OFFSET, matching
  the SPARQL spec -- `sparql.core/ask` only checks non-emptiness).
  Throws `ex-info` (`:type ::parse-error` or `::tokenize-error`) on
  malformed input -- callers (the HTTP handler) turn that into a 400."
  [query-text]
  (let [state (atom {:toks (tokenize query-text)})
        prefixes (parse-prologue! state)]
    (cond
      (peek-kw? state "SELECT")
      (let [_ (advance! state)
            distinct? (peek-kw? state "DISTINCT")
            _ (when distinct? (advance! state))
            [output-vars aggregates] (parse-var-list! state)
            _ (when (peek-kw? state "WHERE") (advance! state))
            pattern (parse-group! state prefixes)
            group-by (parse-group-by! state)
            _ (when (and (seq group-by) (empty? aggregates))
                (fail! "GROUP BY without an aggregate in the select list"
                       (peek1 state)))
            ;; Grouping happens BEFORE ordering and projection: ORDER BY may
            ;; name an aggregate's output var, which does not exist until the
            ;; group has been computed.
            pattern (if (seq aggregates)
                      (cond-> {:sparql/op :group :aggregates aggregates
                               :pattern pattern}
                        (seq group-by) (assoc :by group-by))
                      pattern)
            [order-vars order-desc] (parse-order-by! state)
            [limit offset] (parse-limit-offset! state)
            base (if (seq order-vars)
                   (cond-> {:sparql/op :order-by :vars order-vars :pattern pattern}
                     (seq order-desc) (assoc :desc order-desc))
                   pattern)
            base (if output-vars {:sparql/op :project :vars output-vars :pattern base} base)
            base (if distinct? {:sparql/op :distinct :pattern base} base)
            base (if (or limit offset)
                   {:sparql/op :slice :offset (or offset 0) :limit limit :pattern base}
                   base)]
        {:form :select :output-vars output-vars :algebra base :warnings []})

      (peek-kw? state "CONSTRUCT")
      (let [_ (advance! state)
            _ (expect-punct! state "{")
            template (loop [ts []]
                       (if (peek-punct? state "}")
                         (do (advance! state) ts)
                         (recur (conj ts (parse-triple! state prefixes)))))
            _ (when (peek-kw? state "WHERE") (advance! state))
            pattern (parse-group! state prefixes)
            [limit offset] (parse-limit-offset! state)
            base (if (or limit offset)
                   {:sparql/op :slice :offset (or offset 0) :limit limit :pattern pattern}
                   pattern)]
        (when (empty? template)
          (throw (ex-info "SPARQL parse error: CONSTRUCT template is empty -- there is nothing to build" {:type ::parse-error})))
        {:form :construct :template template :output-vars nil :algebra base :warnings []})

      (peek-kw? state "DESCRIBE")
      (let [_ (advance! state)
            ;; `DESCRIBE <iri>` names its subjects outright; `DESCRIBE ?v WHERE`
            ;; resolves them from solutions. Both are in the spec and they need
            ;; different evaluation, so the form records which one it is rather
            ;; than leaving the handler to guess from whether :algebra is nil.
            terms (loop [ts []]
                    (if (or (nil? (peek1 state)) (peek-kw? state "WHERE") (peek-punct? state "{"))
                      ts
                      (recur (conj ts (parse-term! state prefixes)))))
            _ (when (empty? terms)
                (throw (ex-info "SPARQL parse error: DESCRIBE needs at least one IRI or variable" {:type ::parse-error})))
            has-where? (or (peek-kw? state "WHERE") (peek-punct? state "{"))
            _ (when (peek-kw? state "WHERE") (advance! state))
            pattern (when has-where? (parse-group! state prefixes))]
        (if pattern
          {:form :describe-solutions :output-vars (filterv symbol? terms)
           :algebra pattern :warnings []}
          {:form :describe :terms terms :output-vars nil :algebra nil :warnings []}))

      (peek-kw? state "ASK")
      (let [_ (advance! state)
            _ (when (peek-kw? state "WHERE") (advance! state))
            pattern (parse-group! state prefixes)]
        {:form :ask :output-vars nil :algebra pattern :warnings []})

      :else
      (fail! "expected SELECT or ASK" (peek1 state)))))
