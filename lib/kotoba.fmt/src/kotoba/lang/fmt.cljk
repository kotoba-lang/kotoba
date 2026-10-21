(ns kotoba.lang.fmt
  "Deterministic EDN formatter for the kotoba foundational stdlib. Layer 4
  (tooling). Reads EDN and re-emits it with canonical whitespace/indentation so
  the same data always yields the same text. Map keys keep insertion order (EDN
  read is order-preserving); key sorting is a separate content-addressing
  concern (see dag-cbor).

  Also exposes `pprint` / `pprint-str`, the `clojure.pprint`-shaped entry
  points for the SAME emit engine, aimed at human-facing value inspection
  rather than source-text canonicalization. See README.

  Zero third-party runtime deps; .cljc (JVM / SCI / CLJS / GraalVM / kotoba-WASM)."
  (:require [kotoba.lang.edn :as edn]
            [kotoba.lang.text :as str])
  (:refer-clojure :exclude [read format]))

(def ^:private default-opts {:indent 2 :margin 80})

(defn- ind [depth n] (str/join (repeat (* depth n) " ")))

(declare emit-inline)

(defn- emit-scalar [x]
  (cond
    (nil? x) "nil"
    (string? x) (pr-str x)
    (char? x) (pr-str x)
    (keyword? x) (str x)
    (symbol? x) (str x)
    :else (str x)))

(defn- inline-map [x]
  (str "{" (str/join ", " (map (fn [[k v]] (str (emit-inline k) " " (emit-inline v))) x)) "}"))

(defn- inline-coll [x open close]
  (str open (str/join " " (map emit-inline x)) close))

(defn emit-inline [x]
  (cond
    (map? x) (inline-map x)
    (vector? x) (inline-coll x "[" "]")
    (set? x) (inline-coll (seq x) "#{" "}")
    (seq? x) (inline-coll x "(" ")")
    :else (emit-scalar x)))

(declare emit)

(defn- multiline-map [x depth opts]
  (let [n (:indent opts)]
    (str "{\n"
         (str/join ",\n"
                   (map (fn [[k v]]
                          (str (ind (inc depth) n)
                               (emit k (inc depth) opts) " "
                               (emit v (inc depth) opts)))
                        x))
         "\n" (ind depth n) "}")))

(defn- multiline-coll [x depth opts open close]
  (let [n (:indent opts)]
    (str open "\n"
         (str/join "\n" (map #(str (ind (inc depth) n) (emit % (inc depth) opts)) x))
         "\n" (ind depth n) close)))

(defn- fits-margin? [x depth opts]
  (let [inline (emit-inline x)]
    (< (+ (* depth (:indent opts)) (count inline)) (:margin opts))))

(defn emit
  "Emit `x` as canonical EDN text at `depth` with `opts`."
  [x depth opts]
  (cond
    (map? x) (if (or (empty? x) (fits-margin? x depth opts))
               (emit-inline x)
               (multiline-map x depth opts))
    (vector? x) (if (or (empty? x) (fits-margin? x depth opts))
                  (emit-inline x)
                  (multiline-coll x depth opts "[" "]"))
    (set? x) (if (or (empty? x) (fits-margin? x depth opts))
               (emit-inline x)
               (multiline-coll (seq x) depth opts "#{" "}"))
    (seq? x) (if (or (empty? x) (fits-margin? x depth opts))
               (emit-inline x)
               (multiline-coll x depth opts "(" ")"))
    :else (emit-scalar x)))

(defn format-str
  "Format Clojure data `x` as canonical EDN. Options: `:indent` (default 2),
  `:margin` (default 80)."
  ([x] (format-str x default-opts))
  ([x opts] (emit x 0 (merge default-opts opts))))

(defn format
  "Format an EDN *string* `s`: parse it then re-emit canonically. Returns the
  canonical EDN string. Throws if `s` is not valid EDN."
  ([s] (format s default-opts))
  ([s opts]
   (let [data (edn/read-string {:default (fn [_t v] v)} s)]
     (format-str data opts))))

;; -- pprint / pprint-str ----------------------------------------------------
;;
;; `format-str` already *is* a value pretty-printer: it takes in-memory
;; Clojure/EDN data (not source text) and emits an indented, margin-wrapped
;; string via the same recursive `emit` used above -- there is no second
;; engine here, no parallel implementation to drift out of sync. `pprint-str`
;; and `pprint` expose that engine under the names a caller reaches for when
;; the job is "print this value so a human can read it" (clojure.pprint's
;; job) rather than "canonicalize this source text" (`format`'s job). See the
;; README's "pprint / pprint-str" section for exactly what subset of
;; `clojure.pprint` this covers and what it deliberately does not attempt.

(defn pprint-str
  "Pretty-print `x` (an EDN value: map/vector/set/seq/scalar) to a
  human-readable indented string. Same engine as `format-str` -- this exists
  so callers who want `(with-out-str (pprint x))` from `clojure.pprint` can
  call a string-returning function directly instead. Options: `:indent`
  (default 2), `:margin` (default 80)."
  ([x] (format-str x default-opts))
  ([x opts] (format-str x opts)))

(defn pprint
  "Pretty-print `x` to stdout, followed by a newline. See `pprint-str` for the
  string-returning form and options."
  ([x] (pprint x default-opts))
  ([x opts] (println (pprint-str x opts))))
