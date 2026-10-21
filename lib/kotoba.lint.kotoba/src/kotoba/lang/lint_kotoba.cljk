(ns kotoba.lang.lint-kotoba
  "Static analysis of kotoba/EDN code. Consumes lint (parse), lsp (diagnostics),
  coll (result shaping). Walks a parsed form tree, reports unused def/defn,
  undeclared references, and over-granted capabilities (generalizes wit's
  unused_grants). All diagnostics are lsp records. No third-party deps; .cljc."
  (:require [kotoba.lang.lint :as lint]
            [kotoba.lang.lsp :as lsp]
            [kotoba.lang.coll :as c]
            [kotoba.lang.edn :as edn]))

(defn- def-name
  "If form is a (def name ...) or (defn name ...), return the name symbol."
  [form]
  (when (and (seq? form)
             (#{'def 'defn 'defn- 'defmacro} (first form))
             (next form))
    (second form)))

(declare collect-refs)

(defn- collect-refs
  "Walk `form`, collect all symbols referenced. Returns a set."
  [form]
  (cond
    (symbol? form) #{form}
    (map? form)    (set (mapcat collect-refs (concat (keys form) (vals form))))
    (coll? form)   (set (mapcat collect-refs form))
    :else #{}))

(defn- walk-defs-and-refs
  "Walk a top-level form. Return {:declared #{sym} :references #{sym}}."
  [form]
  (cond
    (and (seq? form) (= 'do (first form)))
    (reduce (fn [acc sub]
            (let [w (walk-defs-and-refs sub)]
              {:declared   (into (:declared acc) (:declared w))
               :references (into (:references acc) (:references w))}))
            {:declared #{} :references #{}}
            (rest form))

    (and (seq? form) (def-name form))
    (let [nm (def-name form)]
      {:declared #{nm}
       :references (set (mapcat collect-refs (drop 2 form)))})

    (map? form)
    {:declared #{} :references (set (mapcat collect-refs (vals form)))}

    :else
    {:declared #{} :references (collect-refs form)}))

(def ^:private default-known-globals
  "Symbols always treated as declared (kotoba/clojure.core baseline)."
  #{'+ '- '* '/ '= 'not= 'and 'or 'not 'if 'when 'let 'fn 'def 'defn
    'map 'reduce 'filter 'str 'keyword 'inc 'dec 'first 'rest 'count
    'true 'false 'nil 'doseq 'loop 'recur 'cond 'case})

(defn unused-decls
  "Declared symbols never referenced (and not in `known-globals`)."
  [{:keys [declared references]} known-globals]
  (let [known (set (or known-globals default-known-globals))
        refs  (set (concat references known))]
    (set (filter (complement refs) declared))))

(defn undeclared-refs
  "Referenced symbols never declared (and not in `known-globals`)."
  [{:keys [declared references]} known-globals]
  (let [known  (set (or known-globals default-known-globals))
        decls  (set (concat declared known))]
    (set (filter (complement decls) references))))

(defn- grants-from-form
  "If `form` is a map with :grants, return the granted capability strings."
  [form]
  (when (map? form)
    (let [g (:grants form)]
      (cond
        (sequential? g) (set (map str g))
        (set? g)        (set (map str g))
        :else #{}))))

(defn over-granted-capabilities
  "Granted-but-unused capabilities in `form` vs `used`."
  [form used]
  (let [granted (grants-from-form form)
        used    (set (map str used))]
    (set (filter (complement used) granted))))

(defn- diagnostic-pairs
  "Vec of lsp diagnostics for unused decls, undeclared refs, over-grant."
  [unused undecl over]
  (let [r (lsp/range (lsp/position 0 0) (lsp/position 0 0))
        d (fn [sev msg] (lsp/diagnostic r sev "lint-kotoba" msg))]
    (vec (concat
          (map #(d :warning (str "unused declaration: " %)) (sort-by str unused))
          (map #(d :warning (str "undeclared: " %))          (sort-by str undecl))
          (map #(d :warning (str "over-granted capability: " %)) (sort-by str over))))))

(defn analyze
  "Parse `source` (via lint) and run static analysis. `opts`:
  `:known-globals` (set of symbols never to flag as undeclared),
  `:used` (set of capability strings actually used — for over-grant).
  Returns `{:ok? :diagnostics :declared :references :unused :undeclared :over-grant}`."
  ([source] (analyze source nil))
  ([source opts]
   (let [parsed (lint/lint-source source)]
     (if-not (:ok? parsed)
       {:ok? false :diagnostics (:diagnostics parsed)
        :declared #{} :references #{} :unused #{} :undeclared #{} :over-grant #{}}
       (let [form   (try (edn/read-string (:canonical parsed)) (catch #?(:clj Throwable :cljs :default) _ nil))
             dr     (walk-defs-and-refs form)
             kg     (:known-globals opts)
             unused (unused-decls dr kg)
             undecl (undeclared-refs dr kg)
             over   (over-granted-capabilities form (:used opts))
             diags  (diagnostic-pairs unused undecl over)]
         {:ok? (empty? diags)
          :diagnostics diags
          :declared (:declared dr)
          :references (:references dr)
          :unused unused
          :undeclared undecl
          :over-grant over})))))
