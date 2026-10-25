(ns kotobase.query.agent
  "Helping a caller — in practice a language model — write a query for this
  bridge, and refusing the bad ones before they reach the plane.

  ## Why this is here rather than in each caller

  ADR-2608189300 (`com-junkawasaki/root`) chose the kotobase dialect
  (Datomic-shaped EDN Datalog) as the agent-facing query surface. Part of that
  argument was measured on 2026-08-18 against two real datasets with
  `murakumo-main` (then qwen3.8-27b), twenty questions, graded by executing the
  generated query and comparing result sets:

      bare (dialect name and notation rules only)      5 / 11  = 45.5%
      schema + few-shot + validate + repair (<= 2)    16 / 18  = 88.9%

  Every one of the five bare failures was a fabricated attribute —
  `company/revenue` for `company/revenue-usd`, `company/isic-code` for
  `company/isic`, `market-intel/lei`, `repo-taxonomy/jurisdiction` — and
  `validate` caught all five **without executing anything**. That is the
  security property the dialect was chosen for, and it only holds if the same
  check runs everywhere. Two copies of it is one copy that gets fixed.

  ## Pure by construction

  No I/O, no dependencies — not even on `kotobase.query.bridge`. The caller
  owns the model call and the execution; this namespace only turns a schema
  into a prompt and a query into either `nil` or a structured refusal. That is
  what makes it cheap to test, and what lets the benchmark and production run
  the same code instead of two that drift.

  ## Schema shape

      {:datasets   [\"market-intel\" \"repo-taxonomy\"]
       :attributes [{:attr \"company/lei\" :doc \"LEI, the join key\"} ...]}

  There is deliberately no `:type` on an attribute. Types were considered on
  2026-08-18 and rejected for now: the two failures that survived the repair
  loop looked semantic but were not — `[>= ?r 100000000000]` and `[?ni < 0]`
  are both a **predicate written as a data pattern**, which is syntax. A type
  system would have caught neither. Add types when a failure needs them."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------- schema

(defn attribute-set
  "The attribute names a query may use. Anything else is a refusal."
  [schema]
  (into #{} (map :attr) (:attributes schema)))

;; ---------------------------------------------------------------- shapes

(def comparison-ops
  "Symbols a caller reaches for when it means a predicate. Seeing one in an
  entity or attribute position is how the two real failures presented."
  '#{< > <= >= = not= })

(defn- var-sym?
  "A logic variable (`?x`) or the blank (`_`)."
  [x]
  (and (symbol? x)
       (let [s (name x)]
         (or (= "_" s) (str/starts-with? s "?")))))

(defn- call-form?
  "`[(>= ?r 1e11)]` — a predicate or function clause. The inner form is a list
  under the reader in both Clojure and ClojureScript."
  [x]
  (or (list? x) (and (seq? x) (not (vector? x)))))

(defn where-clauses
  "The clauses after `:where`. Anything in `:find` or `:in` is not a clause.

  ⚠ Do not reach for `(.indexOf (to-array q) :where)` in ClojureScript: JS
  `indexOf` compares boxed keywords by identity and answers -1, so the walk
  silently visits **no clauses** and every query validates. Measured
  2026-08-18 — a check that could not run returning what a passing check
  returns."
  [q]
  (let [i (first (keep-indexed (fn [n x] (when (= x :where) n)) q))]
    (if (nil? i) [] (filterv vector? (subvec (vec q) (inc i))))))

(defn- find-bindings
  "What sits between `:find` and the first section keyword."
  [q]
  (take-while #(not (#{:where :in :with :keys} %)) (rest q)))

(defn- type-name [x]
  (cond (map? x) "map" (set? x) "set" (string? x) "string"
        (nil? x) "nil" (seq? x) "list" :else "other"))

;; ---------------------------------------------------------------- validate

(defn- entity-position-ok?
  "A logic var, the blank, an entity id, or a lookup ref. Not a literal string
  or keyword: the engine answers those with `Expected number or lookup ref for
  entity id`."
  [e]
  (or (var-sym? e) (integer? e) (vector? e)))

(defn- pattern-refusal
  "A data pattern is `[e a v]`. Refuse the ways a predicate arrives disguised as
  one, the ways an attribute arrives wrong, and a literal in the entity slot."
  [c allowed]
  (let [e (first c)
        a (when (>= (count c) 2) (nth c 1))]
    (cond
      ;; `[>= ?revenue 100000000000]` — the operator took the entity position.
      ;; DataScript reads this as a rule invocation and asks for `%` in `:in`.
      (and (symbol? e) (contains? comparison-ops e))
      {:error :predicate-not-wrapped :got (pr-str c)
       :hint (str "述語は括弧で包む: [(" e " " (str/join " " (rest c)) ")] "
                  "—— 裸のベクタはデータパターン（またはルール呼び出し）として読まれる。")}

      ;; `[?ni < 0]` — infix. The operator took the attribute position, so the
      ;; engine tries to compare a value against the symbol `<`.
      (and (symbol? a) (contains? comparison-ops a))
      {:error :predicate-not-wrapped :got (pr-str c)
       :hint (str "述語は中置ではなく前置で、括弧で包む: [(" a " " (pr-str e) " "
                  (pr-str (nth c 2 nil)) ")]")}

      (keyword? a)
      {:error :keyword-attributes :got (pr-str a)
       :hint (str "属性はキーワードではなく裸文字列で書く。" (pr-str a)
                  " ではなく " (pr-str (subs (str a) 1)) " とする。")}

      (and (string? a) (not (contains? allowed a)))
      {:error :unknown-attributes :got a
       :hint (str "この面に " (pr-str a) " という属性は無い。与えた一覧の中から選ぶ。")}

      ;; A symbol that is neither a var nor an operator sitting in the
      ;; attribute position is not something this dialect has a meaning for.
      (and (symbol? a) (not (var-sym? a)))
      {:error :unknown-attributes :got (str a)
       :hint (str (pr-str a) " は属性でも変数でもない。")}

      ;; `["company/ticker" ?e ?t]` (positions swapped) and `["lit" "a/b" ?v]`
      ;; both land here. Found by the mutation pass in
      ;; `scripts/query-dialect-bench/grammar-agreement.cljs`, not by hand.
      (not (entity-position-ok? e))
      {:error :bad-entity-position :got (pr-str e)
       :hint (str "1 番目は entity の変数（?e）か _ で、属性でも文字列でもない。"
                  "位置が入れ替わっていないか: [?e " (pr-str e) " …]")})))

(defn validate
  "`nil` when the query may run. Otherwise a map the caller can hand straight
  back to the model: `{:error <keyword> :got <what> :hint <how to fix>}`.

  This refuses shape, not meaning. It stops fabricated attribute names and
  predicates written as data patterns; it does not know whether the query
  answers the question."
  [q schema]
  (let [allowed (attribute-set schema)]
    (cond
      (not (vector? q))
      {:error :not-a-vector :got (type-name q)
       :hint "クエリは EDN のベクタで始まる: [:find ?x :where [?e \"attr\" ?x]]"}

      (not= :find (first q))
      {:error :missing-find :got (pr-str (first q))
       :hint "先頭は :find でなければならない"}

      (not (some #{:where} q))
      {:error :missing-where :hint ":where 節が無い"}

      (empty? (find-bindings q))
      {:error :empty-find
       :hint ":find と :where の間に返す変数か集約が 1 つも無い。例: [:find ?x :where …]"}

      :else
      (or
       ;; `[(>= ?r 1e11) extra]` / `["literal"]` — a clause that is neither a
       ;; well-formed predicate call nor a data pattern.
       (first (keep (fn [c]
                      (cond
                        (and (call-form? (first c)) (> (count c) 1))
                        {:error :malformed-predicate-clause :got (pr-str c)
                         :hint "述語節は [(op …)] の 1 要素。余分な要素を付けない。"}

                        (and (= 1 (count c)) (not (call-form? (first c))))
                        {:error :malformed-predicate-clause :got (pr-str c)
                         :hint "1 要素の節は述語呼び出しでなければならない: [(op …)]"}))
                    (where-clauses q)))

       (first (keep #(when-not (call-form? (first %)) (pattern-refusal % allowed))
                    (where-clauses q)))

       ;; A `:find` variable that nothing binds. The engine answers
       ;; `Query for unknown vars: [?t]` and the caller has already paid for
       ;; the inference by then.
       (let [vars-in (fn [form] (into #{} (filter var-sym?) (tree-seq coll? seq form)))
             wanted (disj (vars-in (find-bindings q)) '_)
             ;; ⚠ `(take-while #(not= :where %) q)` here would include the
             ;; `:find` section itself, making every find var trivially bound
             ;; and the check inert. Only `:in` binds from outside `:where`.
             in-section (let [i (first (keep-indexed (fn [n x] (when (= x :in) n)) q))]
                          (if (nil? i)
                            []
                            (take-while #(not (#{:where :with :keys} %))
                                        (drop (inc i) q))))
             bound (into (vars-in (where-clauses q)) (vars-in in-section))
             ;; A predicate can only test what a data pattern bound. The engine
             ;; refuses `[(>= ?r 1e11)]` when nothing binds `?r`, and by then
             ;; the inference is paid for.
             pattern-bound (into (vars-in (remove #(call-form? (first %)) (where-clauses q)))
                                 (vars-in in-section))
             pred-vars (disj (vars-in (filter #(call-form? (first %)) (where-clauses q))) '_)
             missing (sort (remove bound wanted))
             pred-missing (sort (remove pattern-bound pred-vars))]
         (cond
           (seq missing)
           {:error :unbound-find-var :got (mapv str missing)
            :hint (str ":find に在るが :where のどこにも束縛されていない変数: "
                       (str/join ", " missing))}

           (seq pred-missing)
           {:error :unbound-predicate-var :got (mapv str pred-missing)
            :hint (str "述語が使っているが、どのデータパターンも束縛していない変数: "
                       (str/join ", " pred-missing)
                       "。[?e \"attr\" " (first pred-missing) "] のような節が要る。")}))))))


;; ---------------------------------------------------------------- engine form
;; ⚠ **書かれる形と、エンジンが受ける形は同じではない。**
;;
;; この方言の表記は `[:find ?t :where [?e "a/b" ?t]]`（Datomic/DataScript の
;; ベクタ形）で、prompt も validator もそれを扱う。ところが kotobase が実際に通す
;; `datalog.core/q`（= `arrangement.datalog/q`、`bridge/q` の委譲先）が受けるのは
;; **map 形** `{:find [...] :where [...]}` だけである。
;;
;; そしてベクタ形を渡しても **throw しない**。実測 2026-08-18:
;;
;;     map    {:find [?t] :where [[?e "company/ticker" ?t]]}  -> #{["AAA"] ["BBB"]}
;;     vector [:find ?t :where [?e "company/ticker" ?t]]      -> #{[]}
;;
;; `(:find <vector>)` が nil になるので、空のクエリが 1 件の空タプルを返す。
;; **答えられなかったものが、答えと見分けのつかない値で返る** —— この入口が
;; 存在する理由そのものの形が、production 側の engine 呼び出しに在った。
;;
;; だから変換はここが持ち、`bridge/q` は map でないものを**拒否する**（黙って
;; `#{[]}` を返させない）。

(defn ->engine-query
  "検証済みのベクタ形を `datalog.core/q` の map 形にする。
   `[:find … :in … :where …]` の節を、そのまま同名のキーへ移すだけ。"
  [q]
  (when (vector? q)
    (let [section? #{:find :in :where :with :keys :rules}
          [_ & body] q]
      (loop [acc {} k nil xs body]
        (cond
          (empty? xs) acc
          (section? (first xs)) (recur acc (first xs) (rest xs))
          (nil? k) (recur (update acc :find (fnil conj []) (first xs)) nil (rest xs))
          :else (recur (update acc k (fnil conj []) (first xs)) k (rest xs)))))))

;; ---------------------------------------------------------------- prompt

(defn schema-block [schema]
  (str "この面で使える属性は次で全部。**この一覧に無い属性を書かない。**\n"
       (str/join "\n" (for [{:keys [attr doc]} (:attributes schema)]
                        (str "  " (pr-str attr) (when doc (str "  — " doc)))))
       (when-let [ds (seq (:datasets schema))]
         (str "\n\nsource/dataset の値: " (str/join ", " (map pr-str ds))))
       "\n"))

(def notation-rules
  (str "規則:\n"
       "- 出力は EDN のクエリ 1 本だけ。説明・前置き・後置きを書かない。\n"
       "- 属性は裸文字列（\"company/lei\"）。キーワード（:company/lei）にしない。\n"
       "- 変数は ?name の形。\n"
       "- 述語は括弧で包んで前置で書く: [(>= ?r 1e11)]。[?r >= 1e11] や [>= ?r 1e11] は誤り。\n"
       "- :find と :where は必須。\n"))

(def examples
  (str "例（kotobase 方言 = Datomic-shaped EDN Datalog）:\n\n"
       "  [:find ?t :where [?e \"source/dataset\" \"market-intel\"] [?e \"company/ticker\" ?t]]\n"
       "  [:find ?lei ?name :where [?a \"company/lei\" ?lei] [?b \"company/lei\" ?lei]"
       " [?b \"company/legal-name\" ?name]]\n"
       "  [:find (count ?e) :where [?e \"repo/kind\" \"actor\"]]\n"
       "  [:find ?t :where [?e \"company/revenue-usd\" ?r] [(>= ?r 1e11)] [?e \"company/ticker\" ?t]]\n"))

(defn system-prompt
  "The system turn. `:schema?` false gives the bare condition the measurement
  used as its baseline — useful for re-measuring, not for production."
  ([schema] (system-prompt schema {}))
  ([schema {:keys [schema? examples?] :or {schema? true examples? true}}]
   (str "あなたは kotobase 方言（Datomic-shaped EDN Datalog）でクエリを書く。\n"
        notation-rules
        (when schema? (str "\n" (schema-block schema)))
        (when examples? (str "\n" examples)))))

(defn user-turn [question]
  (str "問い: " question "\n\nこの問いに答えるクエリを 1 本書く。"))

(defn repair-turn
  "The turn that closed the gap in the measurement: hand the model its own
  answer back with the structured refusal, not a restatement of the question."
  [refusal]
  (str "そのクエリは実行前の構造検査で弾かれた。\n"
       (pr-str refusal)
       "\n直したクエリを 1 本だけ出す。"))

;; ---------------------------------------------------------------- extract

(defn extract-query
  "Pull the query out of a model turn: strips `<think>` blocks, code fences and
  surrounding prose, and stops at the balanced close so trailing commentary
  does not come along. `nil` when there is no query — which is a different
  answer from an empty one."
  [s]
  (let [s (str/replace (or s "") #"(?s)<think>.*?</think>" "")
        fenced (re-find #"(?s)```(?:clojure|edn|clj)?\s*(.+?)```" s)
        body (str/trim (or (second fenced) s))
        i (str/index-of body "[:find")]
    (when i
      (let [sub (subs body i)]
        (loop [n 0 depth 0 seen false]
          (if (>= n (count sub))
            (when seen (str/trim sub))
            (let [ch (nth sub n)
                  d (cond (#{\[ \( \{} ch) (inc depth)
                          (#{\] \) \}} ch) (dec depth)
                          :else depth)]
              (if (and (zero? d) (pos? depth))
                (subs sub 0 (inc n))
                (recur (inc n) d (or seen (pos? d)))))))))))
