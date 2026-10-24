(ns icd10.compare
  "Code comparison and sorting. ICD-10 category digits are always
  zero-padded to 2 (\"J09\", never \"J9\"), so the category position itself
  sorts correctly as a plain string. The SUBCATEGORY position does not have
  that guarantee (`.2` vs `.10` are both legal 1-2 character subcategory
  shapes per icd10.code, and `.2` > `.10` as strings but should sort before
  it numerically) — this namespace compares the parsed STRUCTURE (letter,
  category digits, then subcategory) rather than raw code text, so that
  case sorts correctly instead of needing every caller to special-case it."
  (:require [icd10.code :as code]))

(defn- subcategory-key
  "A subcategory can itself be numeric (`.9`), so the same digit-vs-string
  ordering problem recurs one level down (`.9` vs `.10` is legal ADL...
  ICD-10 subcategory shape, up to 2 chars). Compared as [length numeric-or-
  string-value] so a purely-numeric subcategory compares numerically
  (`.2` < `.10`), while a subcategory containing a non-digit (real-world
  ICD-10-CM-style extension characters, not base WHO ICD-10 but tolerated
  by icd10.code's shape check) falls back to plain string comparison
  rather than throwing."
  [subcat]
  (cond
    (nil? subcat) [0 0]
    (re-matches #"[0-9]+" subcat)
    [1 #?(:clj (Long/parseLong subcat) :cljs (js/parseInt subcat 10))]
    :else [2 subcat]))

(defn code-key
  "A Comparable key for a successfully-parsed code map: usable directly
  with `compare`, `sort-by`, `sorted-set-by`, etc."
  [{:keys [letter category-digits subcategory dagger-asterisk]}]
  [letter #?(:clj (Long/parseLong category-digits) :cljs (js/parseInt category-digits 10))
   (subcategory-key subcategory)
   ;; a dagger/asterisk pair for the SAME underlying code sorts the
   ;; unmarked/dagger form before the asterisk form, matching how the
   ;; WHO tabular list itself presents a dagger entry immediately followed
   ;; by its asterisk cross-reference, not the reverse
   (case dagger-asterisk nil 0 :dagger 1 :asterisk 2)])

(defn compare-codes
  "Compares two ICD-10 code strings structurally. Returns a named
  `[:error :icd10/invalid-code-shape ...]` (not a thrown exception, and not
  a silently-wrong numeric result) if either fails to parse."
  [a b]
  (let [[ta pa] (code/parse a) [tb pb] (code/parse b)]
    (cond
      (not= ta :ok) [:error :icd10/invalid-code-shape {:input a}]
      (not= tb :ok) [:error :icd10/invalid-code-shape {:input b}]
      :else [:ok (compare (code-key pa) (code-key pb))])))

(defn sort-codes
  "Sorts a collection of ICD-10 code strings structurally. Codes that fail
  to parse are named in `:invalid` (preserving input order among
  themselves) rather than silently dropped or sorted lexicographically
  alongside the valid ones; `:sorted` holds only the successfully parsed
  codes, in structural order."
  [codes]
  (let [parsed (map (fn [c] [c (code/parse c)]) codes)
        {valid true invalid false} (group-by (fn [[_ [tag]]] (= tag :ok)) parsed)]
    {:sorted (map first (sort-by (fn [[_ [_ m]]] (code-key m)) valid))
     :invalid (map first invalid)}))
