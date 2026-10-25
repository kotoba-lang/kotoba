(ns kotobase.pg.sql
  "A small, real SQL subset, hand-parsed and executed via
  `kotobase.query.bridge` (`kotoba-lang/kotobase-query`) -- the pure
  `.cljc` translator/executor half of `org-postgresql-wire`
  (ADR-2607172300 in `com-junkawasaki/root`). No socket / binary wire
  protocol concept lives here at all -- `kotobase.pg.wire` (`.cljs`-only)
  is the only namespace in this repo that knows about bytes on a socket;
  this namespace only ever sees/returns Clojure data. Same
  core/transport separation `kotobase.sftp.fs` (`kotoba-lang/org-ietf-sftp`)
  established for its own protocol family.

  ## v0.1 SQL subset -- READ THIS BEFORE EXTENDING (a deliberate scope
  boundary, owner-confirmed in ADR-2607172300, not laziness)

  Exactly one shape is supported:

      SELECT <col1>, <col2>, ... FROM <collection> WHERE <col> = <literal>

  - single table (`FROM` names exactly one `kotobase.store` collection)
  - the `WHERE` clause is OPTIONAL, but if present is exactly ONE
    `<col> = <literal>` equality predicate -- no `AND`/`OR`, no `<`/`>`/
    `<>`/`LIKE`/`IN`/`IS NULL`, no predicates on more than one column.
  - `<literal>` is a single-quoted string, an integer/decimal number,
    `TRUE`/`FALSE`, or `NULL`.
  - `SELECT` list is an explicit, non-empty column list -- `SELECT *` is
    explicitly rejected (see `parse`'s docstring), not silently
    interpreted as some default projection.

  Deliberately, explicitly UNSUPPORTED and REJECTED WITH A CLEAR ERROR
  (never silently mis-executed or silently ignored) -- this is the exact
  boundary the ADR draws:

  - joins (multiple tables in `FROM`, any `JOIN` keyword)
  - aggregates (`COUNT`/`SUM`/`AVG`/`MIN`/`MAX`/any function-call syntax
    in the `SELECT` list)
  - subqueries (a nested `SELECT` anywhere)
  - `ORDER BY` / `GROUP BY` / `LIMIT` / `OFFSET` / `DISTINCT`
  - `SELECT *`
  - anything past a single `<col> = <literal>` `WHERE` predicate

  ## Doc -> row mapping

  Delegates entirely to `kotobase.query.bridge`'s doc -> datoms mapping
  (see that namespace's docstring): a `SELECT` column name is looked up
  as a top-level attribute key (as a keyword, e.g. SQL column `role`
  reads doc attribute `:role`) on each entity materialized from the
  named `FROM` collection. A row is produced only for entities that have
  a value for EVERY selected column (and, if present, the `WHERE`
  column) -- an entity missing one of those attributes simply does not
  appear in the result set, matching how `arrangement.datalog`'s pattern
  matching already behaves (an unbound clause drops the row, it does not
  produce a `NULL` cell) and how `kotobase.query.bridge`'s own
  `join-across-two-materialized-collections` test documents this same
  behavior for its `[?u :dept-key ?dk]` clause. Callers that need `NULL`
  for a genuinely-missing column would need a richer query shape than
  this v0.1 subset provides -- out of scope here, named so it is not
  mistaken for an oversight.

  ## `visible?` is required, not defaulted

  `execute`/`query` both take `visible?` as a REQUIRED argument and pass
  it straight through to `kotobase.query.bridge/query` -- the same
  discipline the bridge itself enforces (ADR-2607050500, no permissive
  default). `kotobase.pg.wire` threads its own caller-supplied
  `visible?` through to this namespace; it does not invent one."
  (:require [kotoba.lang.text :as str]
            [kotobase.query.bridge :as bridge]))

;; ---------------------------------------------------------------------------
;; Tokenizer
;; ---------------------------------------------------------------------------

(def ^:private token-re
  #"(?i)'(?:[^']|'')*'|<>|!=|<=|>=|[A-Za-z_][A-Za-z0-9_]*|-?\d+\.\d+|-?\d+|[,=()*;<>]|\S")

(def ^:private keywords
  #{"select" "from" "where" "and" "or" "join" "inner" "left" "right" "outer"
    "order" "by" "group" "limit" "offset" "distinct" "as" "on" "true"
    "false" "null"})

(defn- unquote-string-literal [^String raw]
  ;; raw includes the surrounding single quotes; '' inside is the SQL
  ;; escape for a literal single quote.
  (-> (subs raw 1 (dec (count raw)))
      (str/replace "''" "'")))

(defn- classify-raw
  "One raw regex match `s` -> a token map `{:type ... :text s :val ...}`,
  or throws (unexpected-character) if `s` doesn't match any real token
  shape -- this only happens for the catch-all `\\S` alternative in
  `token-re`, i.e. a genuinely unrecognized character (`\"`, `.`, `<`
  alone, `+`, etc.)."
  [s]
  (cond
    (and (>= (count s) 2) (str/starts-with? s "'") (str/ends-with? s "'"))
    {:type :string :text s :val (unquote-string-literal s)}

    (re-matches #"-?\d+\.\d+" s)
    {:type :number :text s :val #?(:clj (Double/parseDouble s) :cljs (js/parseFloat s))}

    (re-matches #"-?\d+" s)
    {:type :number :text s :val #?(:clj (Long/parseLong s) :cljs (js/parseInt s 10))}

    (re-matches #"[A-Za-z_][A-Za-z0-9_]*" s)
    (let [lower (str/lower s)]
      (if (contains? keywords lower)
        {:type :keyword :text s :val lower}
        {:type :ident :text s :val s}))

    (contains? #{"," "=" "(" ")" "*" ";" "<>" "!=" "<=" ">=" "<" ">"} s)
    {:type :punct :text s :val s}

    :else
    (throw (ex-info (str "kotobase.pg.sql: unexpected character " (pr-str s) " in SQL text")
                     {:type :kotobase.pg.sql/syntax-error :reason :unexpected-character :char s}))))

(defn tokenize
  "SQL text -> vector of token maps (`{:type :string|:number|:ident|
  :keyword|:punct :text <original> :val <parsed value>}`). Whitespace
  between tokens is skipped; any other unrecognized character throws."
  [sql]
  (into [] (map classify-raw) (re-seq token-re sql)))

;; ---------------------------------------------------------------------------
;; Parser -- hand-written recursive-descent over the token vector, tiny
;; grammar on purpose (see ns docstring's scope boundary).
;; ---------------------------------------------------------------------------

(defn- syntax-error! [msg data]
  (throw (ex-info (str "kotobase.pg.sql: " msg) (merge {:type :kotobase.pg.sql/syntax-error} data))))

(defn- unsupported! [feature msg]
  (throw (ex-info (str "kotobase.pg.sql: " msg)
                   {:type :kotobase.pg.sql/unsupported-syntax :feature feature})))

(defn- kw? [tok word] (and (= :keyword (:type tok)) (= word (:val tok))))
(defn- punct? [tok text] (and (= :punct (:type tok)) (= text (:val tok))))

(defn- expect-keyword [tokens word]
  (let [tok (first tokens)]
    (when-not (and tok (kw? tok word))
      (syntax-error! (str "expected " (str/upper word)
                           (if tok (str ", found " (pr-str (:text tok))) ", found end of input"))
                      {:expected word :found tok}))
    (rest tokens)))

(defn- parse-select-list
  "-> [cols tokens'] where `cols` is a vector of column-name strings.
  Stops at (and does not consume) the `FROM` keyword. Rejects `*`,
  `DISTINCT`, and function-call syntax (`ident (`) with a clear error."
  [tokens]
  (when (kw? (first tokens) "distinct")
    (unsupported! :distinct "DISTINCT is not supported in this v0.1 SQL subset"))
  (loop [tokens tokens cols []]
    (let [tok (first tokens)]
      (cond
        (nil? tok)
        (syntax-error! "unexpected end of input in SELECT list, expected FROM" {})

        (kw? tok "from")
        (if (empty? cols)
          (syntax-error! "SELECT list is empty" {})
          [cols tokens])

        (punct? tok "*")
        (unsupported! :select-star
                      "SELECT * is not supported in this v0.1 SQL subset -- list explicit column names")

        (and (= :ident (:type tok)) (punct? (second tokens) "("))
        (unsupported! :aggregate-or-function
                      (str "aggregate/function calls (e.g. " (:text tok)
                           "(...)) are not supported in this v0.1 SQL subset"))

        (= :ident (:type tok))
        (let [after (rest tokens)]
          (if (punct? (first after) ",")
            (recur (rest after) (conj cols (:val tok)))
            (recur after (conj cols (:val tok)))))

        :else
        (syntax-error! (str "expected a column name in SELECT list, found " (pr-str (:text tok)))
                        {:found tok})))))

(defn- parse-literal [tok]
  (cond
    (nil? tok) (syntax-error! "expected a literal value, found end of input" {})
    (#{:string :number} (:type tok)) (:val tok)
    (kw? tok "true") true
    (kw? tok "false") false
    (kw? tok "null") nil
    :else (syntax-error! (str "expected a literal value (string/number/TRUE/FALSE/NULL), found "
                               (pr-str (:text tok)))
                          {:found tok})))

(defn- parse-where
  "-> [{:col ... :val ...} tokens'] (or [nil tokens] if there is no WHERE
  at all). Exactly one `<col> = <literal>` predicate; any comparison
  operator other than `=`, or a trailing `AND`/`OR`, is rejected."
  [tokens]
  (if-not (kw? (first tokens) "where")
    [nil tokens]
    (let [tokens (rest tokens)
          col-tok (first tokens)]
      (when-not (= :ident (:type col-tok))
        (syntax-error! (str "expected a column name after WHERE, found "
                             (if col-tok (pr-str (:text col-tok)) "end of input"))
                        {:found col-tok}))
      (let [op-tok (second tokens)]
        (when (nil? op-tok)
          (syntax-error! "unexpected end of input after WHERE <col>, expected =" {}))
        (when-not (punct? op-tok "=")
          (unsupported! :comparison-operator
                        (str "only `=` equality is supported in WHERE (found " (pr-str (:text op-tok)) ")")))
        (let [val-tok (nth tokens 2 nil)
              val (parse-literal val-tok)
              rest-tokens (drop 3 tokens)]
          (when (or (kw? (first rest-tokens) "and") (kw? (first rest-tokens) "or"))
            (unsupported! :compound-where
                          "only a single equality predicate is supported in WHERE (AND/OR not supported)"))
          [{:col (:val col-tok) :val val} rest-tokens])))))

(defn- check-no-trailing-clauses! [tokens]
  (let [tok (first tokens)]
    (cond
      (nil? tok) nil
      (punct? tok ";") (recur (rest tokens))
      (kw? tok "order") (unsupported! :order-by "ORDER BY is not supported in this v0.1 SQL subset")
      (kw? tok "group") (unsupported! :group-by "GROUP BY is not supported in this v0.1 SQL subset")
      (kw? tok "limit") (unsupported! :limit "LIMIT is not supported in this v0.1 SQL subset")
      (kw? tok "offset") (unsupported! :limit "OFFSET is not supported in this v0.1 SQL subset")
      (#{"join" "inner" "left" "right" "outer"} (:val tok))
      (unsupported! :join "JOIN is not supported in this v0.1 SQL subset -- single-table SELECT only")
      :else (syntax-error! (str "unexpected trailing SQL after WHERE clause: " (pr-str (:text tok))) {:found tok}))))

(defn parse
  "SQL text (a single `SELECT ... FROM ... [WHERE <col> = <literal>]`
  statement) -> `{:select [col ...] :from \"<collection>\" :where
  {:col ... :val ...} | nil}`. Throws `ex-info` with
  `:type :kotobase.pg.sql/syntax-error` or
  `:type :kotobase.pg.sql/unsupported-syntax` (+ a human-readable
  message and `:feature`/`:reason` data) for anything outside this
  namespace's v0.1 scope -- see the ns docstring's scope-boundary list.
  Never silently mis-parses/mis-executes out-of-scope SQL."
  [sql]
  (when (or (nil? sql) (str/blank? sql))
    (syntax-error! "empty SQL statement" {}))
  (let [tokens (tokenize sql)]
    (when (empty? tokens)
      (syntax-error! "empty SQL statement" {}))
    (when-not (kw? (first tokens) "select")
      (syntax-error! (str "SQL statement must start with SELECT (this v0.1 subset supports SELECT only, "
                           "no INSERT/UPDATE/DELETE/DDL), found " (pr-str (:text (first tokens))))
                      {:found (first tokens)}))
    (let [[cols tokens] (parse-select-list (rest tokens))
          tokens (expect-keyword tokens "from")
          from-tok (first tokens)]
      (when (punct? from-tok "(")
        (unsupported! :subquery "subqueries are not supported in this v0.1 SQL subset"))
      (when-not (= :ident (:type from-tok))
        (syntax-error! (str "expected a collection name after FROM, found "
                             (if from-tok (pr-str (:text from-tok)) "end of input"))
                        {:found from-tok}))
      (let [tokens (rest tokens)]
        (when (punct? (first tokens) ",")
          (unsupported! :join "multiple tables in FROM (implicit join) are not supported in this v0.1 SQL subset"))
        (when (#{"join" "inner" "left" "right" "outer"} (:val (first tokens)))
          (unsupported! :join "JOIN is not supported in this v0.1 SQL subset -- single-table SELECT only"))
        (let [[where tokens] (parse-where tokens)]
          (check-no-trailing-clauses! tokens)
          {:select cols :from (:val from-tok) :where where})))))

;; ---------------------------------------------------------------------------
;; Translate: parsed AST -> a kotobase-query Datalog `:find`/`:where` map
;; ---------------------------------------------------------------------------

(defn ->datalog
  "`(parse sql)`'s AST -> a Datomic-shaped `{:find [...] :where [...]}`
  query map, ready for `kotobase.query.bridge/q`/`query`. `?e` is scoped
  to the named `FROM` collection via a `:kotobase/coll` clause (so a
  materialized db that happens to contain other collections is not
  accidentally queried across); every `SELECT`ed column gets its own
  fresh logic variable; the optional `WHERE` predicate becomes one more
  `[?e <attr> <literal>]` clause -- even when its column is ALSO
  selected (redundant but consistent: `arrangement.datalog`'s join
  correctly unifies both clauses against the same entity/attribute, see
  ns docstring)."
  [{:keys [select from where]}]
  (let [col->var (into {} (map (fn [c] [c (symbol (str "?" c))])) select)
        base [(symbol "?e") :kotobase/coll from]
        where-clause (when where [(symbol "?e") (keyword (:col where)) (:val where)])
        select-clauses (map (fn [c] [(symbol "?e") (keyword c) (col->var c)]) select)]
    {:find (mapv col->var select)
     :where (into [base] (concat (when where-clause [where-clause]) select-clauses))}))

;; ---------------------------------------------------------------------------
;; Execute
;; ---------------------------------------------------------------------------

(defn execute
  "Run SQL text `sql` against `kotobase.store` `store`, scoped to the one
  collection its `FROM` clause names. `visible?` is REQUIRED (see ns
  docstring) and threaded straight through to
  `kotobase.query.bridge/query`.

  -> `{:columns [\"col1\" \"col2\" ...] :rows [[v1 v2 ...] ...]}` -- a
  Postgres-shaped row-set: `:columns` in `SELECT`-list order, each row a
  vector in the same column order. Row order itself is UNDEFINED (the
  underlying `bridge/query` returns a set, and this v0.1 subset has no
  `ORDER BY`) -- callers that need a stable order must sort client-side.

  Throws the same `ex-info`s `parse` throws for out-of-scope/malformed
  SQL -- callers (e.g. `kotobase.pg.wire`) are expected to catch those
  and turn them into a Postgres `ErrorResponse`, not let them propagate
  as an unhandled crash."
  [store sql visible?]
  (let [ast (parse sql)
        datalog (->datalog ast)
        result-set (bridge/query store [(:from ast)] datalog visible?)]
    {:columns (:select ast)
     :rows (mapv vec result-set)}))
