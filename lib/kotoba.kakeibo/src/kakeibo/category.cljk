(ns kakeibo.category
  "Deterministic, rule-driven categorization.

  **No model runs in this path, by design.** Categories feed a double-entry
  ledger and a spending report; a language model that guesses \"groceries\"
  for a rent payment produces a number that looks authoritative and is wrong,
  and nothing downstream can tell. Rules are ordered data (first match wins),
  so every category is traceable to the rule id that produced it and an
  unmatched transaction stays visibly `:uncategorized` instead of being
  assigned a plausible bucket.

  A rule:

      {:rule/id       :cat/utilities
       :rule/category :utilities
       :rule/match    {:description/contains [\"東京電力\" \"東京ガス\"]
                       :amount/sign          :negative}}

  All predicates present in `:rule/match` must hold (AND). Supported:

  | key                    | meaning                                     |
  |------------------------|---------------------------------------------|
  | `:description/contains`| any listed substring occurs (OR within)     |
  | `:description/regex`   | pattern matches                             |
  | `:amount/sign`         | `:negative` (outflow) or `:positive` (inflow)|
  | `:amount/min-magnitude`| magnitude in minor units is at least n      |
  | `:tx/account`          | account keyword, or a set of them           |

  `:description/regex` is compiled with the host's own regex engine, so keep
  patterns to the common subset — a pattern relying on Java-only or
  JavaScript-only syntax will behave differently across runtimes."
  (:require [kotoba.lang.text :as str]))

(def uncategorized :uncategorized)

(defn- match-contains? [needles haystack]
  (let [h (str/lower (str haystack))]
    (boolean (some (fn [n] (str/includes? h (str/lower (str n))))
                   needles))))

(defn- match-regex? [pattern haystack]
  (boolean (re-find (re-pattern (str pattern)) (str haystack))))

(defn- match-sign? [sign amount]
  (case sign
    :negative (neg? amount)
    :positive (pos? amount)
    false))

(defn- match-account? [spec account]
  (if (set? spec) (contains? spec account) (= spec account)))

(defn matches?
  "True when every predicate in a rule's `:rule/match` holds for `tx`.

  An empty match map matches everything — useful as an explicit last-resort
  rule, and harmless because rules are ordered."
  [{:rule/keys [match]} {:tx/keys [amount account normalized description]}]
  (let [text (or normalized description "")]
    (every?
     (fn [[k v]]
       (case k
         :description/contains  (match-contains? v text)
         :description/regex     (match-regex? v text)
         :amount/sign           (match-sign? v amount)
         :amount/min-magnitude  (>= (if (neg? amount) (- amount) amount) v)
         :tx/account            (match-account? v account)
         ;; An unknown predicate must not silently pass: a typo in a rule
         ;; would otherwise widen it to everything below it.
         false))
     (or match {}))))

(defn categorize-tx
  "Attach `:tx/category` and `:tx/category-rule` to one transaction."
  [rules tx]
  (if-let [rule (first (filter #(matches? % tx) rules))]
    (assoc tx :tx/category (:rule/category rule)
           :tx/category-rule (:rule/id rule))
    (assoc tx :tx/category uncategorized
           :tx/category-rule nil)))

(defn categorize
  "Categorize a transaction sequence."
  [rules txs]
  (mapv #(categorize-tx rules %) txs))

(defn coverage
  "How much of a batch the rules actually explain.

  Returns `{:category/total n :category/matched n :category/uncategorized n
  :category/ratio r :category/unmatched-descriptions [...]}`.

  The unmatched descriptions are the working list for the next rule edit; the
  ratio exists so a category report can state its own completeness instead of
  implying the rules are exhaustive."
  [txs]
  (let [total     (count txs)
        unmatched (filter #(= uncategorized (:tx/category %)) txs)
        n-unmatched (count unmatched)]
    {:category/total total
     :category/matched (- total n-unmatched)
     :category/uncategorized n-unmatched
     :category/ratio (if (zero? total) nil (/ (- total n-unmatched) total))
     :category/unmatched-descriptions
     (->> unmatched (map #(or (:tx/normalized %) (:tx/description %))) distinct vec)}))
