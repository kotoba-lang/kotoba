(ns jsonlogic.core
  "JSONLogic — rules-as-data evaluator. A rule is plain data (string-keyed maps,
  as returned by JSON parsers). Zero third-party deps; portable .cljc (JVM, CLJS, SCI).

  `apply-logic` — pure evaluator; built-in operators only. Throws on unknown ops.
  `run`         — ports-enabled evaluator; dispatches unknown ops to the host IOp."
  (:require [kotoba.lang.text  :as str]
            [jsonlogic.ports :as p]))

;; ---------------------------------------------------------------------------
;; Truthiness (JSONLogic spec: false, 0, \"\", [], null/nil are falsy)
;; ---------------------------------------------------------------------------

(defn- truthy? [v]
  (cond
    (nil? v)     false
    (boolean? v) v
    (number? v)  (not (zero? v))
    (string? v)  (not= v "")
    (vector? v)  (not (empty? v))
    :else        (boolean v)))

;; ---------------------------------------------------------------------------
;; Numeric helpers
;; ---------------------------------------------------------------------------

(defn- parse-num
  "Parse a string to a double, or return nil."
  [s]
  #?(:clj  (when (string? s)
              (try (Double/parseDouble s) (catch Exception _ nil)))
     :cljs (when (string? s)
              (let [n (js/parseFloat s)]
                (when-not (js/isNaN n) n)))))

(defn- parse-int
  "Parse x to an integer index, or return nil."
  [x]
  #?(:clj  (try (cond
                  (integer? x) (int x)
                  :else        (Integer/parseInt (str x)))
                (catch Exception _ nil))
     :cljs (let [n (js/parseInt (str x))]
             (when-not (js/isNaN n) n))))

(defn- to-num
  "Coerce x to a number: identity for numbers; parse for strings; 0/1 for booleans."
  [x]
  (cond
    (number? x)  x
    (boolean? x) (if x 1 0)
    (string? x)  (parse-num x)
    :else        nil))

;; ---------------------------------------------------------------------------
;; Loose equality (JS ==)
;; ---------------------------------------------------------------------------

(defn- loose-eq
  "JavaScript-style == : same value → =; number+string → numeric coercion;
  boolean+anything → bool→number then coerce; nil only == nil."
  [a b]
  (cond
    (= a b)      true
    (nil? a)     false
    (nil? b)     false
    (or (boolean? a) (boolean? b))
    (let [na (to-num a) nb (to-num b)]
      (and (some? na) (some? nb) (== na nb)))
    (or (number? a) (number? b))
    (let [na (to-num a) nb (to-num b)]
      (and (some? na) (some? nb) (== na nb)))
    :else false))

;; ---------------------------------------------------------------------------
;; Variable lookup: dotted-path + integer index
;; ---------------------------------------------------------------------------

(defn- get-in-data
  "Look up `path` in `data`. Supports dotted paths (\"a.b.c\"), integer indices for
  vectors, empty string/nil → whole data. Tries string key then keyword key."
  [data path]
  (let [p (if (nil? path) "" (str path))]
    (if (= p "")
      data
      (reduce
       (fn [cur part]
         (cond
           (nil? cur)    nil
           (map? cur)    (let [v (get cur part)]
                           (if (some? v) v (get cur (keyword part))))
           (vector? cur) (when-let [i (parse-int part)] (get cur i))
           :else         nil))
       data (str/split p #"\.")))))

;; ---------------------------------------------------------------------------
;; Core evaluator (internal — forward-declared for mutual recursion)
;; ---------------------------------------------------------------------------

(declare eval*)

(defn- eval-args [ports args data]
  (mapv #(eval* ports % data) args))

(defn- eval-var [ports raw-args data]
  (let [[path default-val has-default?]
        (if (vector? raw-args)
          [(first raw-args) (second raw-args) (> (count raw-args) 1)]
          [raw-args nil false])
        result (get-in-data data path)]
    (if (and (nil? result) has-default?)
      default-val
      result)))

(defn- eval-if [ports args data]
  (loop [remaining args]
    (cond
      (empty? remaining)    nil
      (= 1 (count remaining)) (eval* ports (first remaining) data)
      :else
      (let [[cond-expr then-expr & more] remaining
            cv (eval* ports cond-expr data)]
        (if (truthy? cv)
          (eval* ports then-expr data)
          (recur more))))))

(defn- eval-and [ports args data]
  (loop [remaining args last-val true]
    (if (empty? remaining)
      last-val
      (let [v (eval* ports (first remaining) data)]
        (if (truthy? v)
          (recur (rest remaining) v)
          v)))))

(defn- eval-or [ports args data]
  (loop [remaining args last-val nil]
    (if (empty? remaining)
      last-val
      (let [v (eval* ports (first remaining) data)]
        (if (truthy? v)
          v
          (recur (rest remaining) v))))))

(defn eval*
  "Internal recursive evaluator. Applies `rule` to `data` using `ports`."
  [ports rule data]
  (cond
    ;; non-map literals evaluate to themselves
    (not (map? rule)) rule

    ;; empty map → itself
    (empty? rule) rule

    ;; operation object: exactly one string key
    (= 1 (count rule))
    (let [[op raw-args] (first rule)]
      (case op
        ;; --- variable / missing ---
        "var"
        (eval-var ports raw-args data)

        "missing"
        (let [ks (if (vector? raw-args) raw-args [raw-args])]
          (filterv #(nil? (get-in-data data %)) ks))

        "missing_some"
        (let [[min-req ks] raw-args
              missing (filterv #(nil? (get-in-data data %)) ks)]
          (if (>= (- (count ks) (count missing)) min-req)
            []
            missing))

        ;; --- equality ---
        "=="  (let [[a b] (eval-args ports raw-args data)] (loose-eq a b))
        "===" (let [[a b] (eval-args ports raw-args data)] (= a b))
        "!="  (let [[a b] (eval-args ports raw-args data)] (not (loose-eq a b)))
        "!==" (let [[a b] (eval-args ports raw-args data)] (not= a b))

        ;; --- logical not / double-not ---
        "!"
        (let [v (if (vector? raw-args)
                  (eval* ports (first raw-args) data)
                  (eval* ports raw-args data))]
          (not (truthy? v)))

        "!!"
        (let [v (if (vector? raw-args)
                  (eval* ports (first raw-args) data)
                  (eval* ports raw-args data))]
          (boolean (truthy? v)))

        ;; --- short-circuit boolean ---
        "and"
        (eval-and ports
                  (if (vector? raw-args) raw-args [raw-args])
                  data)

        "or"
        (eval-or ports
                 (if (vector? raw-args) raw-args [raw-args])
                 data)

        ;; --- conditional ---
        ("if" "?:")
        (eval-if ports raw-args data)

        ;; --- comparisons (2-arg; < and <= also support 3-arg between) ---
        ">"
        (let [[a b] (map #(to-num (eval* ports % data)) raw-args)]
          (boolean (and (some? a) (some? b) (> a b))))

        ">="
        (let [[a b] (map #(to-num (eval* ports % data)) raw-args)]
          (boolean (and (some? a) (some? b) (>= a b))))

        "<"
        (if (= 3 (count raw-args))
          (let [[a b c] (map #(to-num (eval* ports % data)) raw-args)]
            (boolean (and (some? a) (some? b) (some? c) (< a b) (< b c))))
          (let [[a b] (map #(to-num (eval* ports % data)) raw-args)]
            (boolean (and (some? a) (some? b) (< a b)))))

        "<="
        (if (= 3 (count raw-args))
          (let [[a b c] (map #(to-num (eval* ports % data)) raw-args)]
            (boolean (and (some? a) (some? b) (some? c) (<= a b) (<= b c))))
          (let [[a b] (map #(to-num (eval* ports % data)) raw-args)]
            (boolean (and (some? a) (some? b) (<= a b)))))

        ;; --- arithmetic ---
        "+"
        (let [vals (mapv #(to-num (eval* ports % data)) raw-args)]
          (reduce + 0 (keep identity vals)))

        "-"
        (if (= 1 (count raw-args))
          (- (or (to-num (eval* ports (first raw-args) data)) 0))
          (let [[a b] (map #(to-num (eval* ports % data)) raw-args)]
            (- (or a 0) (or b 0))))

        "*"
        (let [vals (mapv #(to-num (eval* ports % data)) raw-args)]
          (reduce * 1 (keep identity vals)))

        "/"
        (let [[a b] (map #(to-num (eval* ports % data)) raw-args)]
          (/ (or a 0) (or b 1)))

        "%"
        (let [[a b] (map #(to-num (eval* ports % data)) raw-args)]
          (mod (or a 0) (or b 1)))

        "min"
        (let [vals (keep #(to-num (eval* ports % data)) raw-args)]
          (when (seq vals) (apply min vals)))

        "max"
        (let [vals (keep #(to-num (eval* ports % data)) raw-args)]
          (when (seq vals) (apply max vals)))

        ;; --- string / collection ---
        "in"
        (let [[needle haystack] (eval-args ports raw-args data)]
          (cond
            (string? haystack) (str/includes? haystack (str needle))
            (vector? haystack) (boolean (some #(= needle %) haystack))
            :else              false))

        "cat"
        (str/join "" (map #(let [v (eval* ports % data)]
                             (if (nil? v) "" (str v)))
                          raw-args))

        "substr"
        (let [[s-expr start-expr len-expr] raw-args
              sv   (str (eval* ports s-expr data))
              si   (int (or (to-num (eval* ports start-expr data)) 0))
              slen (count sv)
              asi  (if (neg? si) (max 0 (+ slen si)) (min si slen))]
          (if (nil? len-expr)
            (subs sv asi)
            (let [li  (int (or (to-num (eval* ports len-expr data)) 0))
                  end (min slen (+ asi (max 0 li)))]
              (subs sv asi end))))

        "merge"
        (reduce (fn [acc item]
                  (let [v (eval* ports item data)]
                    (if (vector? v) (into acc v) (conj acc v))))
                [] raw-args)

        ;; --- higher-order ---
        "map"
        (let [[arr-expr rule-expr] raw-args
              arr (eval* ports arr-expr data)]
          (if (vector? arr)
            (mapv #(eval* ports rule-expr %) arr)
            []))

        "filter"
        (let [[arr-expr rule-expr] raw-args
              arr (eval* ports arr-expr data)]
          (if (vector? arr)
            (filterv #(truthy? (eval* ports rule-expr %)) arr)
            []))

        "reduce"
        (let [[arr-expr rule-expr init-expr] raw-args
              arr  (eval* ports arr-expr data)
              init (eval* ports init-expr data)]
          (if (vector? arr)
            (reduce (fn [acc cur]
                      (eval* ports rule-expr {"current" cur "accumulator" acc}))
                    init arr)
            init))

        "all"
        (let [[arr-expr rule-expr] raw-args
              arr (eval* ports arr-expr data)]
          (boolean (and (vector? arr) (seq arr)
                        (every? #(truthy? (eval* ports rule-expr %)) arr))))

        "some"
        (let [[arr-expr rule-expr] raw-args
              arr (eval* ports arr-expr data)]
          (if (vector? arr)
            (boolean (some #(truthy? (eval* ports rule-expr %)) arr))
            false))

        "none"
        (let [[arr-expr rule-expr] raw-args
              arr (eval* ports arr-expr data)]
          (if (vector? arr)
            (not (some #(truthy? (eval* ports rule-expr %)) arr))
            true))

        ;; --- default: try custom op, else throw ---
        (if (p/custom-op? ports op)
          (p/apply-op ports op
                      (if (vector? raw-args)
                        (eval-args ports raw-args data)
                        [(eval* ports raw-args data)])
                      data)
          (throw (ex-info (str "Unknown JSONLogic operator: " op)
                          {:jsonlogic/op op})))))

    ;; multi-key map — non-standard, pass through as data
    :else rule))

;; ---------------------------------------------------------------------------
;; Public API
;; ---------------------------------------------------------------------------

(defn apply-logic
  "Evaluate `rule` against `data` using built-in operators only. A non-map rule
  (literal, vector) evaluates to itself. Throws on any unknown operator."
  [rule data]
  (eval* p/default-ports rule data))

(defn run
  "Evaluate `rule` against `data` dispatching unknown operators to `ports` (IOp).
  Falls through to built-in operators when `(custom-op? ports op)` is false."
  [ports rule data]
  (eval* ports rule data))
