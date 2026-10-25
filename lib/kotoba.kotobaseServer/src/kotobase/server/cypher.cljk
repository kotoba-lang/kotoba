(ns kotobase.server.cypher
  "CYPHER BASIC SUBSET -> the same map-form Datalog `do-q` executes
  (ADR-2607172500's `graph.query` surface; ADR-2607250100 axis 4).
  Sibling of `kotobase.server.sparql`, same doctrine: every unsupported
  form is rejected loudly with the supported grammar in the error, never
  silently misread.

  Supported, and ONLY this:

    MATCH p1, p2, ...
    [OPTIONAL MATCH p1, p2, ...] ...
    [WHERE boolean-expression]
    RETURN [DISTINCT] item, ...
    [ORDER BY item [ASC|DESC], ...] [SKIP n] [LIMIT n]

  One materializing WITH stage followed by MATCH is supported. WITH may use
  the same projection/order/skip/limit shape as RETURN. Boolean expressions
  support parentheses and NOT/AND/OR with precedence NOT > AND > OR.

    pattern := (v [:Label]* [{attr: lit, ...}]) chained by relationships
    rel     := -[[relvar] :attr [*range]]->   left to right
             | <-[[relvar] :attr [*range]]-   right to left
             | -[[relvar] :attr [*range]]-    undirected
    range   := * | *n | *n.. | *n..m | *..m   (bare * is 1.., UNBOUNDED)
    item    := v | v.attr [AS alias] | agg(v) [AS alias]
             | coalesce(item, ...) [AS alias]
             | toInteger(item) [AS alias]
             | CASE v WHEN lit THEN lit ELSE lit END [AS alias]
             | CASE WHEN v IS NULL THEN lit ELSE lit END [AS alias]
    lit     := null | true | false | \"string\" | 'string'
             | integer | decimal | $param

  The write subset is deliberately narrower than the read subset:

    CREATE (v[:Label] {id: lit, property: lit, ...}) [, ...]
    [RETURN v [, ...]]

  It creates standalone nodes only, requires a non-empty id, and is executed
  through the same authorization, policy, append-only commit and conditional
  head-CAS path as datom transactions.

  Attribute names are used as stored: a rel type `[:sp/knows]` matches the
  stored attribute string \":sp/knows\"; a property key `sp/name:` is
  prefixed to \":sp/name\" (the write path stores every attribute as its
  keyword-string form). A node label `(n:Person)` matches the stored
  attribute \":label\". A bare `(v)` with no properties, label or
  relationship binds nothing and is rejected (never an implicit scan).

  A `$param` with no value in the params map is a failure, not an empty
  match. `v.attr` projections compile to OPTIONAL blocks, so an absent
  property is null as Cypher requires, not a dropped row.

  Anything other than a plain single-hop left-to-right relationship
  compiles to a `:paths` entry rather than a triple, and needs an
  executor that implements it -- `query-exec/execute` refuses a compiled
  query carrying a construct it cannot evaluate rather than approximating
  it.

  OPTIONAL MATCH supports ordinary BGPs plus directed, undirected and
  variable-length relationships. Optional paths are kept separate from primary
  paths in the compiled form so the executor can expand them under the left
  join instead of accidentally making them mandatory. Anonymous nodes are
  accepted when the surrounding pattern binds the query.

  Not supported (rejected): multiple WITH stages, searched CASE forms other
  than `WHEN v IS NULL`, CASE result expressions beyond literals, functions
  other than coalesce/toInteger,
  relationship CREATE, CREATE from MATCH, MERGE, DELETE, SET, REMOVE and every
  other write form outside the bounded standalone-node CREATE above."
  (:require [kotoba.lang.text :as str]))

(def grammar-help
  "supported: MATCH/OPTIONAL MATCH, boolean WHERE (= <> < <= > >=, NOT/AND/OR), one WITH ... MATCH stage, RETURN projections/simple CASE, ORDER BY/SKIP/LIMIT; or authenticated standalone-node CREATE (... {id: lit}) [RETURN v]")

(defn- fail [msg near]
  (throw (ex-info (str "cypher-subset: " msg " (near: " (pr-str near) "). " grammar-help)
                  {:cypher-subset true})))

;; `token-re` の最後の `[^\s]` は「どの正規トークンにもならなかった 1 文字」を
;; 捕まえるためだけにある。これが無いと `re-seq` は未知文字を **黙って捨てて**
;; しまい、この ns が docstring で約束している「never silently misread」を破る。
;; 実測で 2 件の silent misread が出た(openCypher TCK 走査、2026-08-04):
;;   `-[:r*]->`   可変長パスの `*` が消えて 1 ホップの `-[:r]->` になっていた
;;   `WHERE a.n =~ "x"`  正規表現マッチの `~` が消えて **等値比較**になっていた
;; どちらもエラーではなく「違う質問の答え」を返す。
;; 2026-08-13 に追加したトークン: `$name`(パラメータ) `..`(範囲) `*`(可変長)。
;; `..` は `.` より **先** に並べる —— 交替は左優先なので順序を逆にすると
;; `0..3` が `.` 2 個に割れ、範囲が黙って property access に化ける。
(def ^:private token-re
  #"\"[^\"]*\"|'[^']*'|\$[A-Za-z_][A-Za-z0-9_]*|-?[0-9]+(?:\.[0-9]+)?|<-|->|<>|<=|>=|<|>|\(|\)|\[|\]|\{|\}|,|:|=|\.\.|\.|\*|-|[A-Za-z_][A-Za-z0-9_/\-]*|[^\s]")

;; 上と同じ選択肢から catch-all だけを除いたもの。full match で「正規トークンか」を判定する。
(def ^:private valid-token-re
  #"\"[^\"]*\"|'[^']*'|\$[A-Za-z_][A-Za-z0-9_]*|-?[0-9]+(?:\.[0-9]+)?|<-|->|<>|<=|>=|<|>|\(|\)|\[|\]|\{|\}|,|:|=|\.\.|\.|\*|-|[A-Za-z_][A-Za-z0-9_/\-]*")

(defn- tokenize
  "Cypher subset のトークン列。subset の語彙に無い文字は捨てずに loud reject する。
  末尾のセミコロン 1 個だけは Cypher の慣用なので取り除いて許す(意味を変えない)。"
  [s]
  (let [s (str/replace (str/trimr (str s)) #";$" "")
        ts (vec (re-seq token-re s))]
    (doseq [t ts]
      (when-not (re-matches valid-token-re t)
        (fail "character outside the supported subset (it would otherwise be dropped and change the query's meaning)" t)))
    ts))

(defn- param? [t] (and t (str/starts-with? t "$")))

(defn- substitute-params
  "Replace each `$name` token with the literal token its value would have been.
  Done here, immediately after tokenize, so every downstream rule keeps seeing
  only literals -- a parameter is a value, not a syntax.

  Missing parameter is a loud failure, never an empty binding: a query silently
  matching `id = \"\"` returns rows for the wrong entity instead of an error."
  [ts params]
  (mapv (fn [t]
          (if (param? t)
            (let [k (subs t 1)
                  v (or (get params k) (get params (keyword k)))]
              (when (nil? v)
                (fail "query parameter has no value (pass it in the params map)" t))
              (if (and (number? v) (not (string? v)))
                (str v)
                (str "\"" (str/replace (str v) "\"" "") "\"")))
            t))
        ts))

(defn- literal? [t]
  (or (str/starts-with? t "\"") (str/starts-with? t "'")
      (re-matches #"-?[0-9]+(?:\.[0-9]+)?" t)
      (contains? #{"NULL" "TRUE" "FALSE"} (str/upper (str t)))))

(defn- literal->value [t]
  (cond
    (str/starts-with? t "\"") (subs t 1 (dec (count t)))
    (str/starts-with? t "'") (subs t 1 (dec (count t)))
    (= "NULL" (str/upper (str t))) nil
    (= "TRUE" (str/upper (str t))) true
    (= "FALSE" (str/upper (str t))) false
    :else t))

(defn- attr-name [t] (if (str/starts-with? t ":") t (str ":" t)))

(def ^:private ^:dynamic *anon* nil)

(defn- anon-name []
  (str "__anon" (swap! *anon* inc)))

(defn- parse-int [t]
  #?(:clj (Long/parseLong (str t)) :cljs (js/parseInt (str t) 10)))

(defn- token-ident? [t] (boolean (and t (re-matches #"[A-Za-z_][A-Za-z0-9_/\-]*" t))))

(defn- kw? [t kw] (and (token-ident? t) (= (str/upper t) kw)))

(def ^:private where-ops {"=" := "<>" :not= "<" :< "<=" :<= ">" :> ">=" :>=})
(def ^:private return-aggs #{"count" "sum" "min" "max" "avg"})
;; Whitelist, not a general call syntax: each name has an implementation in
;; query-exec, and an unknown name is rejected rather than ignored.
(def ^:private return-fns #{"coalesce" "tointeger"})

(defn- parse-props
  "After '{': attr : lit [, attr : lit]* '}' -> [rest-tokens clauses]."
  [ts v clauses]
  (loop [ts ts clauses clauses]
    (let [[k colon lit & more] ts]
      (when-not (token-ident? k) (fail "property key expected" k))
      (when-not (= ":" colon) (fail "property key needs ':'" k))
      (when-not (and lit (literal? lit)) (fail "property value must be a literal" lit))
      (let [clauses (conj clauses [v (attr-name k) (literal->value lit)])]
        (cond
          (= "," (first more)) (recur (rest more) clauses)
          (= "}" (first more)) [(rest more) clauses]
          :else (fail "property map needs ',' or '}'" (first more)))))))

(defn- parse-labels
  "After the node variable: `:Label` (repeatable) -> one clause each.

  A label is matched, never skipped. Dropping it would turn
  `(n:Person {id: 1})` into `(n {id: 1})`, which silently answers a different
  question whenever two types share an id space -- exactly the failure mode the
  tokenizer's catch-all exists to prevent."
  [ts v clauses]
  (loop [ts ts clauses clauses]
    (if (and (= ":" (first ts)) (token-ident? (second ts)))
      (recur (drop 2 ts) (conj clauses [v ":label" (second ts)]))
      [(vec ts) clauses])))

(defn- parse-node
  "'(' var [:Label]* [{props}] ')' -> [rest-tokens var-sym clauses bound?]."
  [ts clauses]
  (let [[open v & more] ts]
    (when-not (= "(" open) (fail "node pattern must open with (" open))
    ;; `(:Label {..})` and `()` -- LDBC IS2 opens with one. The variable is
    ;; generated rather than the node being skipped: an unnamed node still
    ;; constrains the pattern, and dropping it would widen the match.
    (let [anon? (not (token-ident? v))
          more (if anon? (cons v more) more)
          v (if anon? (anon-name) v)]
      (when-not (or anon? (token-ident? v)) (fail "node needs a variable name" v))
    (let [sym (symbol (str "?" v))
          before (count clauses)
          [more clauses] (parse-labels more sym clauses)
          labelled? (> (count clauses) before)
          more (seq more)]
      (cond
        (= ")" (first more)) [(vec (rest more)) sym clauses labelled?]
        (= "{" (first more))
        (let [[ts clauses] (parse-props (rest more) sym clauses)]
          (if (= ")" (first ts))
            [(vec (rest ts)) sym clauses true]
            (fail "node must close with )" (first ts))))
        :else (fail "node must close with ) or contain {props}" (first more)))))))

(defn- parse-rel-detail
  "Inside `[ ... ]`: [relvar] ':' attr ['*' [min] ['..' [max]]]
  -> {:rel-var ?r|nil :attr \":a\" :min n :max n|nil}."
  [ts]
  (let [[rel-var ts] (if (and (token-ident? (first ts)) (= ":" (second ts)))
                       [(symbol (str "?" (first ts))) (vec (rest ts))]
                       [nil (vec ts)])]
    (when-not (= ":" (first ts)) (fail "relationship needs [:attr]" (first ts)))
    (let [attr (second ts)]
      (when-not (token-ident? attr) (fail "relationship type expected after [:" attr))
      (let [ts (vec (drop 2 ts))]
        (if (= "*" (first ts))
          ;; `*`, `*n`, `*n..`, `*n..m`, `*..m`
          ;; Cypher ranges. A bare `*` is `*1..` -- UNBOUNDED, not one hop.
          ;; Defaulting its max to its min would rebuild exactly the silent
          ;; single-hop bug that cypher-test has guarded against since
          ;; 2026-08-04, so `explicit-min?` is tracked rather than inferred.
          ;;   *      -> 1..nil     *n   -> n..n
          ;;   *n..   -> n..nil     *n..m-> n..m      *..m -> 1..m
          (let [ts (vec (rest ts))
                explicit-min? (boolean (re-matches #"[0-9]+" (str (first ts))))
                [minv ts] (if explicit-min?
                            [(parse-int (first ts)) (vec (rest ts))] [1 ts])
                [maxv ts] (if (= ".." (first ts))
                            (let [ts (vec (rest ts))]
                              (if (re-matches #"[0-9]+" (str (first ts)))
                                [(parse-int (first ts)) (vec (rest ts))]
                                [nil ts]))
                            [(when explicit-min? minv) ts])]
            (when-not (= "]" (first ts)) (fail "relationship must close with ]" (first ts)))
            [(vec (rest ts)) {:rel-var rel-var :attr (attr-name attr) :min minv :max maxv}])
          (do (when-not (= "]" (first ts)) (fail "relationship must close with ]" (first ts)))
              [(vec (rest ts)) {:rel-var rel-var :attr (attr-name attr) :min 1 :max 1}]))))))

(defn- parse-rel-chain
  "subj (<-|-)[relvar? :attr *range?](->|-) node)* -> [rest-tokens clauses paths].

  A plain single-hop left-to-right relationship with no relationship variable
  stays a BGP triple, so the engine can still push the whole query down. Every
  other shape -- undirected, right-to-left, variable-length, or one that binds
  the relationship itself -- becomes a `:paths` entry the executor expands,
  because none of them is a single triple."
  [ts subj clauses paths]
  (loop [ts (vec ts) subj subj clauses clauses paths paths]
    (let [rtl? (= "<-" (first ts))
          ltr-start? (and (= "-" (first ts)) (= "[" (second ts)))]
      (if-not (or rtl? (and ltr-start? true))
        [ts clauses paths]
        (let [ts (if rtl?
                   (do (when-not (= "[" (second ts)) (fail "relationship needs [:attr]" (second ts)))
                       (vec (drop 2 ts)))
                   (vec (drop 2 ts)))
              [ts detail] (parse-rel-detail ts)
              tail (first ts)
              direction (cond
                          (and rtl? (= "-" tail)) :rtl
                          (and rtl? (= "->" tail))
                          (fail "a relationship cannot point both ways" "<-...->")
                          (= "->" tail) :ltr
                          (= "-" tail) :both
                          :else (fail "relationship must end with -> or -" tail))
              [ts obj clauses _] (parse-node (vec (rest ts)) clauses)
              {:keys [rel-var attr min max]} detail
              simple? (and (nil? rel-var) (= 1 min) (= 1 max) (not= :both direction))]
          (if simple?
            (recur ts obj
                   (conj clauses (if (= :rtl direction) [obj attr subj] [subj attr obj]))
                   paths)
            (recur ts obj clauses
                   (conj paths {:from (if (= :rtl direction) obj subj)
                                :to (if (= :rtl direction) subj obj)
                                :attr attr :min min :max max
                                :both (= :both direction)
                                :rel-var rel-var}))))))))

(defn- parse-one-pattern [ts clauses paths]
  (let [[ts sym clauses bound?] (parse-node ts clauses)
        [ts clauses paths] (parse-rel-chain ts sym clauses paths)]
    (when (and (not bound?)
               (not (some (fn [[s _ o]] (or (= s sym) (= o sym))) clauses))
               (not (some (fn [{:keys [from to]}] (or (= from sym) (= to sym))) paths)))
      (fail "a bare (var) with no properties and no relationship binds nothing" (str sym)))
    [ts clauses paths]))

(defn- projection-var [v k]
  (symbol (str "?" v "__" (str/replace k "/" "_"))))

(defn- parse-fn-call
  "fn(arg, ...) [AS alias] -> [rest-tokens {:fn :coalesce :args [...] :as ?a} projections].
  A `v.attr` argument is bound through the same OPTIONAL projection machinery as
  a bare `RETURN v.attr`, so a missing property is null here too -- which is the
  whole point of `coalesce(m.content, m.imageFile)` in LDBC IS 4."
  [ts projs ordinal]
  (let [fname (keyword (str/lower (first ts)))]
    (loop [ts (vec (drop 2 ts)) args [] projs projs]
      (cond
        (and (token-ident? (first ts)) (= "." (second ts)) (token-ident? (nth ts 2 nil)))
        (let [v (first ts) k (nth ts 2)
              pv (projection-var v k)]
          (recur (vec (drop 3 ts)) (conj args pv)
                 (conj projs {:block [[(symbol (str "?" v)) (attr-name k) pv]] :bind pv})))
        (= "," (first ts)) (recur (vec (rest ts)) args projs)
        (literal? (first ts))
        (recur (vec (rest ts)) (conj args [:lit (literal->value (first ts))]) projs)
        (and (token-ident? (first ts)) (not= "(" (second ts)))
        (recur (vec (rest ts)) (conj args (symbol (str "?" (first ts)))) projs)
        (= ")" (first ts))
        (let [more (vec (rest ts))
              [alias more] (if (kw? (first more) "AS")
                             (do (when-not (token-ident? (second more)) (fail "AS needs an alias name" (second more)))
                                 [(symbol (str "?" (second more))) (vec (drop 2 more))])
                             [(symbol (str "?" (name fname) "_" ordinal)) more])]
          (when (empty? args) (fail "function call needs at least one argument" (name fname)))
          (when (and (= :tointeger fname) (not= 1 (count args)))
            (fail "toInteger takes exactly one argument" (name fname)))
          [more {:fn fname :args args :as alias} projs])
        :else (fail "unsupported function argument" (first ts))))))

(declare parse-where-or)

(defn- parse-where-primary [ts]
  (cond
    (= "(" (first ts))
    (let [[more expr blocks] (parse-where-or (vec (rest ts)))]
      (when-not (= ")" (first more)) (fail "WHERE expression must close with )" (first more)))
      [(vec (rest more)) expr blocks])

    (and (token-ident? (first ts)) (= "." (second ts)) (token-ident? (nth ts 2 nil)))
    (let [[v _ k cmp lit & more] ts]
      (when-not (contains? where-ops cmp)
        (fail "unsupported WHERE comparison (=, <>, <, <=, >, >=)" cmp))
      (when-not (literal? lit) (fail "WHERE value must be a literal" lit))
      (let [pv (projection-var v k)]
        [(vec more)
         {:op :cmp :var pv :cmp (get where-ops cmp) :value (literal->value lit)}
         [[[ (symbol (str "?" v)) (attr-name k) pv]]]]))

    :else (fail "WHERE needs a comparison, NOT, or parenthesized expression" (first ts))))

(defn- parse-where-not [ts]
  (if (kw? (first ts) "NOT")
    (let [[more expr blocks] (parse-where-not (vec (rest ts)))]
      [more {:op :not :arg expr} blocks])
    (parse-where-primary ts)))

(defn- parse-where-and [ts]
  (let [[ts first-expr first-blocks] (parse-where-not ts)]
    (loop [ts ts args [first-expr] blocks first-blocks]
      (if (kw? (first ts) "AND")
        (let [[more expr more-blocks] (parse-where-not (vec (rest ts)))]
          (recur more (conj args expr) (into blocks more-blocks)))
        [ts (if (= 1 (count args)) (first args) {:op :and :args args}) blocks]))))

(defn- parse-where-or [ts]
  (let [[ts first-expr first-blocks] (parse-where-and ts)]
    (loop [ts ts args [first-expr] blocks first-blocks]
      (if (kw? (first ts) "OR")
        (let [[more expr more-blocks] (parse-where-and (vec (rest ts)))]
          (recur more (conj args expr) (into blocks more-blocks)))
        [ts (if (= 1 (count args)) (first args) {:op :or :args args}) blocks]))))

(defn- parse-case-item [ts ordinal]
  (let [[case more]
        (if (kw? (second ts) "WHEN")
          (let [[_ _ subject is-kw null-kw then-kw then-value
                 else-kw else-value end-kw & more] ts]
            (when-not (token-ident? subject) (fail "CASE WHEN subject must be a bound variable" subject))
            (when-not (and (kw? is-kw "IS") (kw? null-kw "NULL"))
              (fail "searched CASE currently supports WHEN variable IS NULL" is-kw))
            (when-not (kw? then-kw "THEN") (fail "CASE needs THEN" then-kw))
            (when-not (literal? then-value) (fail "CASE THEN value must be a literal" then-value))
            (when-not (kw? else-kw "ELSE") (fail "CASE needs ELSE" else-kw))
            (when-not (literal? else-value) (fail "CASE ELSE value must be a literal" else-value))
            (when-not (kw? end-kw "END") (fail "CASE must close with END" end-kw))
            [{:is-null (symbol (str "?" subject))
              :then (literal->value then-value)
              :else (literal->value else-value)} more])
          (let [[_ subject when-kw when-value then-kw then-value
                 else-kw else-value end-kw & more] ts]
            (when-not (token-ident? subject) (fail "CASE subject must be a bound variable" subject))
            (when-not (kw? when-kw "WHEN") (fail "CASE needs WHEN" when-kw))
            (when-not (literal? when-value) (fail "CASE WHEN value must be a literal" when-value))
            (when-not (kw? then-kw "THEN") (fail "CASE needs THEN" then-kw))
            (when-not (literal? then-value) (fail "CASE THEN value must be a literal" then-value))
            (when-not (kw? else-kw "ELSE") (fail "CASE needs ELSE" else-kw))
            (when-not (literal? else-value) (fail "CASE ELSE value must be a literal" else-value))
            (when-not (kw? end-kw "END") (fail "CASE must close with END" end-kw))
            [{:subject (symbol (str "?" subject))
              :when (literal->value when-value)
              :then (literal->value then-value)
              :else (literal->value else-value)} more]))
        [alias more] (if (kw? (first more) "AS")
                       (do (when-not (token-ident? (second more))
                             (fail "AS needs an alias name" (second more)))
                           [(symbol (str "?" (second more))) (vec (drop 2 more))])
                       [(symbol (str "?case_" ordinal)) (vec more)])]
    [more {:case case :as alias}]))

(defn- parse-create [text params]
  (let [ts (substitute-params (tokenize (str text)) params)]
    (when-not (kw? (first ts) "CREATE") (fail "write must start with CREATE" (first ts)))
    (loop [ts (vec (rest ts)) nodes []]
      (let [[more clauses paths] (parse-one-pattern ts [] [])
            sym (ffirst clauses)]
        (when (or (seq paths)
                  (some (fn [[s _ o]] (or (not= s sym) (symbol? o))) clauses))
          (fail "CREATE currently supports standalone nodes, not relationships" (first more)))
        (let [properties (into {} (map (fn [[_ attr value]] [attr value]) clauses))
              entity-id (get properties ":id")]
          (when (or (nil? entity-id) (str/blank? (str entity-id)))
            (fail "CREATE node requires a non-empty id property" (str sym)))
          (let [nodes (conj nodes {:variable sym :id (str entity-id)
                                   :properties properties})]
            (cond
              (= "," (first more)) (recur (vec (rest more)) nodes)
              (empty? more) {:write :create :nodes nodes}
              (kw? (first more) "RETURN")
              (let [return-vars (->> (rest more) (remove #{","})
                                     (mapv #(symbol (str "?" %))))
                    created-vars (set (map :variable nodes))]
                (when (or (empty? return-vars)
                          (some #(not (contains? created-vars %)) return-vars))
                  (fail "CREATE RETURN may name only created node variables" (first more)))
                {:write :create :nodes nodes :return return-vars})
              :else (fail "CREATE allows another node or RETURN" (first more)))))))))

(defn- parse-basic
  "Cypher subset text -> {:find [...] :where [[s p o] ...] :optionals [...]
  :optional-paths [...] :paths [...] :order-by :filters :group-by :distinct
  :limit}.
  Throws ex-info {:cypher-subset true} on anything outside the subset.

  `params` supplies values for `$name` placeholders; a placeholder with no
  value is a failure, never an empty match."
  ([text params] (parse-basic text params #{}))
  ([text params initial-bound]
   (binding [*anon* (atom 0)]
    (let [ts (substitute-params (tokenize (str text)) params)]
    (when (empty? ts) (fail "empty query" ""))
    (when-not (kw? (first ts) "MATCH") (fail "must start with MATCH" (first ts)))
    (let [[ts clauses paths]
          (loop [ts (vec (rest ts)) clauses [] paths []]
            (let [[ts clauses paths] (parse-one-pattern ts clauses paths)]
              (if (= "," (first ts))
                (recur (vec (rest ts)) clauses paths)
                [ts clauses paths])))
          ;; OPTIONAL MATCH -> one :optionals block per clause. The executor has
          ;; had left-join since the SPARQL work; only the parser was missing.
          [ts match-optionals match-optional-paths]
          (loop [ts ts acc [] path-acc []]
            (if (and (kw? (first ts) "OPTIONAL") (kw? (second ts) "MATCH"))
              (let [[ts oc op]
                    (loop [ts (vec (drop 2 ts)) oc [] op []]
                      (let [[ts oc op] (parse-one-pattern ts oc op)]
                        (if (= "," (first ts))
                          (recur (vec (rest ts)) oc op)
                          [ts oc op])))]
                ;; Keep paths aligned with their OPTIONAL block. Folding them
                ;; into primary :paths would make the relationship mandatory;
                ;; dropping them would silently answer a one-hop query.
                (recur ts (conj acc (mapv vec oc)) (conj path-acc (vec op))))
              [ts acc path-acc]))
          [ts clauses filters predicate predicate-optionals]
          (if (kw? (first ts) "WHERE")
            (let [[more expr blocks] (parse-where-or (vec (rest ts)))]
              [more clauses [] expr (vec (distinct blocks))])
            [ts clauses [] nil []])
          _ (when-not (kw? (first ts) "RETURN") (fail "RETURN required" (first ts)))
          ts (vec (rest ts))
          [distinct? ts] (if (kw? (first ts) "DISTINCT") [true (vec (rest ts))] [false ts])
          ;; Projections become OPTIONAL single-triple blocks, not inner joins.
          ;; Cypher returns null for a missing property; an inner join would drop
          ;; the whole row instead, which is a different answer -- and IS 4 asks
          ;; for exactly such a property (`imageFile` is absent on text posts).
          [ts find-vars projections]
          (loop [ts ts acc [] projs []]
            (cond
              (kw? (first ts) "CASE")
              (let [[more item] (parse-case-item ts (count acc))
                    acc (conj acc item)]
                (if (= "," (first more))
                  (recur (vec (rest more)) acc projs)
                  [more acc projs]))

              (and (token-ident? (first ts)) (contains? return-aggs (str/lower (first ts)))
                   (= "(" (second ts)))
              (let [[agg _ v close & more] ts]
                (when-not (token-ident? v) (fail "aggregate needs a variable" v))
                (when-not (= ")" close) (fail "aggregate must close with )" close))
                (let [[alias more] (if (kw? (first more) "AS")
                                     (do (when-not (token-ident? (second more)) (fail "AS needs an alias name" (second more)))
                                         [(symbol (str "?" (second more))) (drop 2 more)])
                                     [(symbol (str "?" (str/lower agg) "_" v)) more])
                      acc (conj acc {:agg (keyword (str/lower agg)) :var (symbol (str "?" v)) :as alias})]
                  (if (= "," (first more))
                    (recur (vec (rest more)) acc projs)
                    [(vec more) acc projs])))
              ;; fn(arg, ...) [AS alias] -- coalesce / toInteger
              (and (token-ident? (first ts)) (contains? return-fns (str/lower (first ts)))
                   (= "(" (second ts)))
              (let [[more item projs] (parse-fn-call ts projs (count acc))
                    acc (conj acc item)]
                (if (= "," (first more))
                  (recur (vec (rest more)) acc projs)
                  [more acc projs]))
              ;; v.attr [AS alias]
              (and (token-ident? (first ts)) (= "." (second ts)) (token-ident? (nth ts 2 nil)))
              (let [v (first ts) k (nth ts 2)
                    pv (projection-var v k)
                    more (vec (drop 3 ts))
                    [alias more] (if (kw? (first more) "AS")
                                   (do (when-not (token-ident? (second more)) (fail "AS needs an alias name" (second more)))
                                       [(symbol (str "?" (second more))) (vec (drop 2 more))])
                                   [pv more])
                    ;; The OPTIONAL block binds `pv`; the row must appear under
                    ;; `alias`. Without this rename the column exists and is
                    ;; always nil -- which is what the first version did, and
                    ;; what the execution tests caught.
                    projs (conj projs (cond-> {:block [[(symbol (str "?" v)) (attr-name k) pv]]
                                               :as alias :bind pv}
                                        (not= alias pv) (assoc :rename pv)))
                    acc (conj acc alias)]
                (if (= "," (first more))
                  (recur (vec (rest more)) acc projs)
                  [more acc projs]))
              (token-ident? (first ts))
              (let [v (symbol (str "?" (first ts)))
                    more (vec (rest ts))
                    [alias more] (if (kw? (first more) "AS")
                                   (do (when-not (token-ident? (second more)) (fail "AS needs an alias name" (second more)))
                                       [(symbol (str "?" (second more))) (vec (drop 2 more))])
                                   [v more])
                    acc (conj acc alias)
                    projs (if (= alias v) projs (conj projs {:rename v :as alias}))]
                (if (= "," (first more))
                  (recur (vec (rest more)) acc projs)
                  [more acc projs]))
              :else (fail "RETURN needs variable names, var.attr, or agg(var)" (first ts))))
          [ts order-by']
          (if (and (seq ts) (kw? (first ts) "ORDER"))
            (do (when-not (kw? (second ts) "BY") (fail "ORDER must be followed by BY" (second ts)))
                (loop [ts (vec (drop 2 ts)) acc []]
                  (if (and (seq ts) (token-ident? (first ts))
                           (not (kw? (first ts) "SKIP"))
                           (not (kw? (first ts) "LIMIT")))
                    (let [;; ORDER BY v.attr, ORDER BY alias, or ORDER BY fn(alias).
                          ;; A cast is recorded rather than dropped: ordering
                          ;; "10" before "9" is a different answer from ordering
                          ;; 9 before 10, and LDBC IS 3 asks for the numeric one.
                          fn-cast? (and (contains? return-fns (str/lower (first ts)))
                                        (= "(" (second ts)))
                          [cast ts] (if fn-cast?
                                      [(keyword (str/lower (first ts))) (vec (drop 2 ts))]
                                      [nil ts])
                          [v ts] (if (and (= "." (second ts)) (token-ident? (nth ts 2 nil)))
                                   [(projection-var (first ts) (nth ts 2)) (vec (drop 3 ts))]
                                   [(symbol (str "?" (first ts))) (vec (rest ts))])
                          ts (if fn-cast?
                               (do (when-not (= ")" (first ts))
                                     (fail "ORDER BY function must close with )" (first ts)))
                                   (vec (rest ts)))
                               ts)
                          [dir ts] (cond
                                     (kw? (first ts) "DESC") [:desc (vec (rest ts))]
                                     (kw? (first ts) "ASC") [:asc (vec (rest ts))]
                                     :else [:asc ts])
                          acc (conj acc (cond-> {:var v :dir dir} cast (assoc :cast cast)))]
                      (if (= "," (first ts))
                        (recur (vec (rest ts)) acc)
                        [ts acc]))
                    (if (empty? acc) (fail "ORDER BY needs variable names" (first ts)) [ts acc]))))
            [ts []])
          [skip ts] (if (kw? (first ts) "SKIP")
                      (do (when-not (re-matches #"[0-9]+" (str (second ts)))
                            (fail "SKIP needs a non-negative integer" (second ts)))
                          [(parse-int (second ts)) (vec (drop 2 ts))])
                      [nil ts])
          [limit ts] (if (kw? (first ts) "LIMIT")
                       (do (when-not (re-matches #"[0-9]+" (str (second ts)))
                             (fail "LIMIT needs a non-negative integer" (second ts)))
                           [(parse-int (second ts)) (vec (drop 2 ts))])
                       [nil ts])
          _ (when (seq ts) (fail "only ORDER BY / SKIP / LIMIT allowed after RETURN" (first ts)))
          bound (-> (set initial-bound)
                    (into (mapcat (fn [[s _ o]] (filter symbol? [s o])) clauses))
                    (into (mapcat (fn [{:keys [from to rel-var]}] (filter symbol? [from to rel-var])) paths))
                    ;; OPTIONAL MATCH binds too -- nullably, but bound.
                    (into (mapcat (fn [blk] (mapcat (fn [[s _ o]] (filter symbol? [s o])) blk))
                                  match-optionals))
                    (into (mapcat (fn [ps]
                                    (mapcat (fn [{:keys [from to rel-var]}]
                                              (filter symbol? [from to rel-var]))
                                            ps))
                                  match-optional-paths)))
          renames (filterv :rename projections)
          projection-optionals (mapv :block (filterv :block projections))
          optionals (into (into (vec match-optionals) predicate-optionals) projection-optionals)
          optional-paths (into (vec match-optional-paths)
                               (repeat (+ (count predicate-optionals)
                                          (count projection-optionals)) []))
          projected (set (filter symbol? find-vars))
          agg-items (filterv :agg find-vars)
          fn-items (filterv :fn find-vars)
          case-items (filterv :case find-vars)
          bare-vars (filterv symbol? find-vars)
          group-by' (when (seq agg-items)
                      (vec (remove (set (map :as (filterv :block projections))) bare-vars)))]
      (when (and (empty? clauses) (empty? paths)) (fail "MATCH produced no bindable clauses" "MATCH"))
      ;; Every RETURN item must trace back to something MATCH bound.
      (doseq [{:keys [block]} (filterv :block projections)]
        (let [[[v _ _]] block]
          (when-not (bound v) (fail "RETURN variable not bound in MATCH/WHERE" (str v)))))
      ;; A rename's source is either a MATCH variable (RETURN a AS b) or a
      ;; projection's own bind var (RETURN a.attr AS b), which the OPTIONAL
      ;; block binds rather than the base BGP.
      (let [projection-binds (set (keep :bind projections))]
        (doseq [{:keys [rename]} renames]
          (when-not (or (bound rename) (projection-binds rename))
            (fail "RETURN variable not bound in MATCH/WHERE" (str rename)))))
      (doseq [v bare-vars]
        (when-not (or (bound v) (projected v)) (fail "RETURN variable not bound in MATCH/WHERE" (str v))))
      (doseq [{:keys [var]} agg-items]
        (when-not (bound var) (fail "aggregate variable not bound in MATCH/WHERE" (str var))))
      ;; Every function argument must be a literal, a MATCH variable, or a
      ;; projection this query binds. An unbound one would compute over nil.
      (let [projection-binds (set (keep :bind projections))]
        (doseq [{:keys [fn args]} fn-items]
          (doseq [a args]
            (when (and (symbol? a) (not (bound a)) (not (projection-binds a)))
              (fail (str (name fn) " argument not bound in MATCH/WHERE") (str a))))))
      (doseq [{:keys [case]} case-items]
        (let [subject (or (:subject case) (:is-null case))]
          (when-not (bound subject)
            (fail "CASE subject not bound in MATCH/WHERE" (str subject)))))
      (doseq [{:keys [var]} order-by']
        (when-not (or (projected var)
                      (some (fn [it] (= var (:as it))) agg-items)
                      (some (fn [it] (= var (:as it))) fn-items)
                      (some (fn [it] (= var (:as it))) case-items))
          (fail "ORDER BY var must be in RETURN" (str var))))
      (cond-> {:find (vec find-vars) :where (mapv vec clauses)}
        (seq optionals) (assoc :optionals optionals)
        (some seq optional-paths) (assoc :optional-paths optional-paths)
        (seq renames) (assoc :renames (mapv (juxt :rename :as) renames))
        (seq paths) (assoc :paths paths)
        (seq order-by') (assoc :order-by order-by')
        (seq filters) (assoc :filters filters)
        predicate (assoc :predicate predicate)
        (seq group-by') (assoc :group-by group-by')
        distinct? (assoc :distinct true)
        skip (assoc :skip skip)
        limit (assoc :limit limit)))))))

(defn parse
  "Parse one read query or one bounded two-stage WITH pipeline. WITH materializes
  its projected rows after ORDER BY/SKIP/LIMIT, then seeds the following MATCH."
  ([text] (parse text nil))
  ([text params]
   (let [ts (tokenize (str text))
         with-idx (first (keep-indexed #(when (kw? %2 "WITH") %1) ts))]
     (cond
       (kw? (first ts) "CREATE") (parse-create text params)
       (nil? with-idx)
       (parse-basic text params)
       :else
       (let [match-idx (first (keep-indexed
                               (fn [i t] (when (and (> i with-idx) (kw? t "MATCH")) i)) ts))]
         (when-not match-idx (fail "WITH must be followed by MATCH" "WITH"))
         (when (some #(kw? % "WITH") (subvec ts (inc with-idx)))
           (fail "only one WITH pipeline stage is supported" "WITH"))
         (let [first-text (str/join " " (concat (subvec ts 0 with-idx)
                                                  ["RETURN"]
                                                  (subvec ts (inc with-idx) match-idx)))
               second-text (str/join " " (subvec ts match-idx))
               first-stage (parse-basic first-text params)
               initial-bound (set (map (fn [item] (if (map? item) (:as item) item))
                                       (:find first-stage)))
               second-stage (parse-basic second-text params initial-bound)]
           {:pipeline [first-stage second-stage]}))))))
