(ns sigma.validate
  "Structural validation of a Sigma rule. Pure: returns a vector of problem maps
  {:sigma/severity :error|:warn :sigma/code … :sigma/id … :sigma/msg …} so a
  caller decides how to surface them. `valid?` is true iff there are no
  :error-level problems (warnings are advisory)."
  (:require [kotoba.lang.text :as str]
            [kotoba.dsl.problem :as problem]
            [sigma.model :as m]))

(defn- sigma-problem [severity code id msg]
  (problem/problem :sigma severity code id msg))

(defn- parse-field-modifiers
  "Return the modifier strings for a field key, e.g. \"User|contains|all\" → [\"contains\" \"all\"]."
  [field-key]
  (vec (rest (str/split field-key #"\|"))))

(defn- tokenize-condition [s]
  (re-seq #"[^\s()]+|[()]" s))

(defn- condition-refs
  "Return a seq of {:kind :plain|:glob :ref \"...\"} for identifiers in condition string.
  Keywords and/or/not/1/of/all/them/parens are consumed; 'all of them' emits nothing
  (valid as long as selections are non-empty — not checked here)."
  [s]
  (let [tokens (vec (tokenize-condition s))
        n      (count tokens)]
    (loop [i 0 acc []]
      (if (>= i n)
        acc
        (let [tok (get tokens i)]
          (cond
            (contains? #{"(" ")" "and" "or" "not"} tok)
            (recur (inc i) acc)

            (= tok "1")
            (if (and (< (+ i 2) n) (= "of" (get tokens (+ i 1))))
              (recur (+ i 3) (conj acc {:kind :glob :ref (get tokens (+ i 2))}))
              (recur (inc i) acc))

            (= tok "all")
            (if (and (< (+ i 1) n) (= "of" (get tokens (+ i 1))))
              (let [pat (nth tokens (+ i 2) nil)]
                (if (= pat "them")
                  (recur (+ i 3) acc)
                  (if pat
                    (recur (+ i 3) (conj acc {:kind :glob :ref pat}))
                    (recur (inc i) acc))))
              (recur (inc i) acc))

            :else
            (recur (inc i) (conj acc {:kind :plain :ref tok}))))))))

(defn- glob-matches-any?
  "True if the glob pattern (e.g. \"sel*\") matches at least one name in `sel-names`."
  [glob sel-names]
  (let [escaped (-> glob
                    (str/replace "\\" "\\\\")
                    (str/replace "." "\\.")
                    (str/replace "+" "\\+")
                    (str/replace "?" "\\?")
                    (str/replace "^" "\\^")
                    (str/replace "$" "\\$")
                    (str/replace "|" "\\|")
                    (str/replace "(" "\\(")
                    (str/replace ")" "\\)")
                    (str/replace "[" "\\[")
                    (str/replace "]" "\\]")
                    (str/replace "*" ".*"))
        rx      (re-pattern (str "^" escaped "$"))]
    (boolean (some #(re-matches rx %) sel-names))))

(defn problems
  "Return a vector of structural problems with Sigma rule `r`."
  [r]
  (let [id        (:sigma/id r "?")
        sel-names (m/selection-names r)
        cond-str  (m/condition r)
        ps        (transient [])]

    ;; severity level: warn if unknown (not a hard error — Sigma evolves)
    (when-let [lvl (:sigma/level r)]
      (when-not (contains? m/known-levels lvl)
        (conj! ps (sigma-problem :warn :rule/unknown-level id
                           (str "unknown level " (pr-str lvl)
                                "; expected one of " m/known-levels)))))

    ;; modifiers on every field key in every selection
    (doseq [[sel-name criteria] (m/selections r)]
      (doseq [field-key (keys criteria)]
        (doseq [mod (parse-field-modifiers field-key)]
          (when-not (contains? m/known-modifiers mod)
            (conj! ps (sigma-problem :error :field/unknown-modifier sel-name
                               (str "unknown modifier '" mod
                                    "' in field key '" field-key "'")))))))

    ;; condition: each plain identifier must exist; globs must match at least one
    (when (seq cond-str)
      (doseq [{:keys [kind ref]} (condition-refs cond-str)]
        (case kind
          :plain
          (when-not (contains? sel-names ref)
            (conj! ps (sigma-problem :error :condition/unknown-selection id
                               (str "condition references undefined selection '" ref "'"))))
          :glob
          (when-not (glob-matches-any? ref sel-names)
            (conj! ps (sigma-problem :warn :condition/unmatched-glob id
                               (str "glob '" ref "' in condition matches no defined selection"))))
          nil)))

    (persistent! ps)))

(defn errors
  "Return only :error-severity problems."
  [r]
  (problem/errors :sigma (problems r)))

(defn valid?
  "True iff rule `r` has no :error-level structural problems."
  [r]
  (problem/valid? :sigma (problems r)))
