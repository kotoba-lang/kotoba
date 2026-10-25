(ns computeruse.json
  "A minimal, dependency-free JSON reader/writer.

  Why hand-rolled: the resident bot CLI must load under nbb from a bare
  checkout — no tools.deps resolution, so no clojure.data.json — while
  the same .cljc must compile and test on the JVM. Using js/JSON on one
  host and a library on the other would give the two hosts different
  parsers; one parser is easier to trust.

  Scope is deliberately the OpenAI-compatible chat wire format:
  objects, arrays, strings (with \\uXXXX), numbers, true/false/null.
  Object keys become keywords. `read` throws on malformed input — a
  parse failure is a real failure and must not look like an empty
  response."
  (:refer-clojure :exclude [read])
  (:require [kotoba.lang.text :as str]))

;; ───────────────────────── writer ─────────────────────────

(defn- escape [s]
  (let [sb #?(:clj (StringBuilder.) :cljs (volatile! ""))]
    (doseq [ch (str s)]
      (let [c #?(:clj (int ch) :cljs (.charCodeAt ch 0))
            out (case c
                  34 "\\\"" 92 "\\\\" 8 "\\b" 12 "\\f"
                  10 "\\n" 13 "\\r" 9 "\\t"
                  (if (< c 32)
                    (str "\\u" (subs (str "000" #?(:clj (Integer/toHexString c)
                                                   :cljs (.toString c 16)))
                                     (- (count (str "000" #?(:clj (Integer/toHexString c)
                                                             :cljs (.toString c 16)))) 4)))
                    (str ch)))]
        #?(:clj (.append ^StringBuilder sb ^String out)
           :cljs (vswap! sb str out))))
    #?(:clj (.toString ^StringBuilder sb) :cljs @sb)))

(defn write
  "EDN value → JSON string. Keywords and symbols become strings."
  [x]
  (cond
    (nil? x) "null"
    (true? x) "true"
    (false? x) "false"
    (number? x) (str x)
    (string? x) (str "\"" (escape x) "\"")
    (keyword? x) (str "\"" (escape (name x)) "\"")
    (symbol? x) (str "\"" (escape (str x)) "\"")
    (map? x) (str "{" (str/join "," (map (fn [[k v]]
                                           (str (write (if (keyword? k) (name k) (str k)))
                                                ":" (write v)))
                                         x)) "}")
    (sequential? x) (str "[" (str/join "," (map write x)) "]")
    (set? x) (str "[" (str/join "," (map write x)) "]")
    :else (str "\"" (escape (str x)) "\"")))

;; ───────────────────────── reader ─────────────────────────

(defn- fail! [s i msg]
  (throw (ex-info (str "JSON parse error at " i ": " msg)
                  {:index i :near (subs (str s) (max 0 (- i 20))
                                        (min (count (str s)) (+ i 20)))})))

(defn- ws [s i]
  (let [n (count s)]
    (loop [i i]
      (if (and (< i n) (contains? #{\space \tab \newline \return} (nth s i)))
        (recur (inc i))
        i))))

(declare read-value)

(defn- read-string* [s i]
  ;; i points at the opening quote
  (let [n (count s)]
    (loop [i (inc i) acc []]
      (when (>= i n) (fail! s i "unterminated string"))
      (let [c (nth s i)]
        (cond
          (= c \") [(str/join acc) (inc i)]
          (= c \\)
          (let [e (nth s (inc i))]
            (case e
              \" (recur (+ i 2) (conj acc \"))
              \\ (recur (+ i 2) (conj acc \\))
              \/ (recur (+ i 2) (conj acc \/))
              \b (recur (+ i 2) (conj acc \backspace))
              \f (recur (+ i 2) (conj acc \formfeed))
              \n (recur (+ i 2) (conj acc \newline))
              \r (recur (+ i 2) (conj acc \return))
              \t (recur (+ i 2) (conj acc \tab))
              \u (let [hex (subs s (+ i 2) (+ i 6))
                       cp #?(:clj (Integer/parseInt hex 16)
                             :cljs (js/parseInt hex 16))]
                   (recur (+ i 6) (conj acc (char cp))))
              (fail! s i (str "bad escape \\" e))))
          :else (recur (inc i) (conj acc c)))))))

(def ^:private number-chars (set "-+.eE0123456789"))

(defn- read-number [s i]
  (let [n (count s)
        end (loop [j i] (if (and (< j n) (number-chars (nth s j))) (recur (inc j)) j))
        tok (subs s i end)]
    (when (= i end) (fail! s i "expected a number"))
    [(if (re-find #"[.eE]" tok)
       #?(:clj (Double/parseDouble tok) :cljs (js/parseFloat tok))
       #?(:clj (Long/parseLong tok) :cljs (js/parseInt tok 10)))
     end]))

(defn- read-array [s i]
  (let [i (ws s (inc i))]
    (if (= \] (nth s i))
      [[] (inc i)]
      (loop [i i acc []]
        (let [[v j] (read-value s i)
              j (ws s j)
              c (nth s j)]
          (cond
            (= c \,) (recur (ws s (inc j)) (conj acc v))
            (= c \]) [(conj acc v) (inc j)]
            :else (fail! s j "expected , or ]")))))))

(defn- read-object [s i]
  (let [i (ws s (inc i))]
    (if (= \} (nth s i))
      [{} (inc i)]
      (loop [i i acc {}]
        (when-not (= \" (nth s i)) (fail! s i "expected an object key"))
        (let [[k j] (read-string* s i)
              j (ws s j)
              _ (when-not (= \: (nth s j)) (fail! s j "expected :"))
              [v j] (read-value s (ws s (inc j)))
              j (ws s j)
              c (nth s j)
              acc (assoc acc (keyword k) v)]
          (cond
            (= c \,) (recur (ws s (inc j)) acc)
            (= c \}) [acc (inc j)]
            :else (fail! s j "expected , or }")))))))

(defn- read-value [s i]
  (let [i (ws s i)]
    (when (>= i (count s)) (fail! s i "unexpected end of input"))
    (let [c (nth s i)]
      (cond
        (= c \{) (read-object s i)
        (= c \[) (read-array s i)
        (= c \") (read-string* s i)
        (and (= c \t) (= "true" (subs s i (min (count s) (+ i 4))))) [true (+ i 4)]
        (and (= c \f) (= "false" (subs s i (min (count s) (+ i 5))))) [false (+ i 5)]
        (and (= c \n) (= "null" (subs s i (min (count s) (+ i 4))))) [nil (+ i 4)]
        :else (read-number s i)))))

(defn read
  "JSON string → EDN (object keys become keywords). Throws on malformed
  input; callers must not treat a throw as an empty answer."
  [s]
  (when (str/blank? (str s))
    (throw (ex-info "JSON parse error: empty input" {:input (str s)})))
  (first (read-value (str s) 0)))

(defn read-safe
  "`read`, but returns nil instead of throwing. Use only where the
  caller distinguishes nil from an empty response itself."
  [s]
  (try (read s) (catch #?(:clj Exception :cljs :default) _ nil)))
