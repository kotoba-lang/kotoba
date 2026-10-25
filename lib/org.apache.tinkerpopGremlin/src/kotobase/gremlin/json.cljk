(ns kotobase.gremlin.json
  "Minimal, dependency-free JSON encode/parse in portable cljc -- no host-JSON
  binding (JVM `org.json` / Node `JSON`), so the same code runs on nbb/cljs
  and the JVM compat suite. Modeled on the same house pattern
  `kotobase-protocols/src/kotobase/protocols/json.cljc` and
  `kotoba-lang/nostr`'s `nostr.json` use (this repo does not depend on
  either; this is a small, independent implementation of the same
  well-understood algorithm, same discipline `nostr.json`'s own docstring
  describes for itself).

  Used by `kotobase.gremlin.wire` to encode/decode GraphSON RequestMessage/
  ResponseMessage envelopes over WebSocket text frames. Map keys round-trip
  as STRINGS (never keywordized) -- GraphSON request/response fields are
  wire data, not code; `kotobase.gremlin.wire` does its own explicit
  string-key -> keyword-step translation where needed (bytecode step
  names)."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------- encode

(defn- char-code-at [s i]
  #?(:clj (int (.charAt ^String s ^int i)) :cljs (.charCodeAt s i)))

(defn- escape-str
  "Escape a string for JSON output, char-by-char (not a regex character
  class over a literal control-byte range -- see `nostr.json`'s own
  docstring for why that form is deliberately avoided here too). Every char
  code below 32 gets a `\\uXXXX` escape; `\"` and `\\` get their named
  two-char escapes; everything else (including all non-ASCII Unicode)
  passes through unchanged."
  [s]
  (let [n (count s)]
    (loop [i 0 acc (transient [])]
      (if (= i n)
        (apply str (persistent! acc))
        (let [code (char-code-at s i)
              c (subs s i (inc i))
              piece (cond
                      (= c "\"") "\\\""
                      (= c "\\") "\\\\"
                      (= code 10) "\\n"
                      (= code 13) "\\r"
                      (= code 9)  "\\t"
                      (= code 8)  "\\b"
                      (= code 12) "\\f"
                      (< code 32)
                      (str "\\u" #?(:clj (format "%04x" code)
                                    :cljs (.padStart (.toString code 16) 4 "0")))
                      :else c)]
          (recur (inc i) (conj! acc piece)))))))

(defn encode
  "EDN value -> JSON string. Map keys may be keywords or strings; keywords
  render as their name (no leading colon)."
  [x]
  (cond
    (nil? x)     "null"
    (true? x)    "true"
    (false? x)   "false"
    (number? x)  (str x)
    (string? x)  (str "\"" (escape-str x) "\"")
    (keyword? x) (str "\"" (escape-str (name x)) "\"")
    (map? x)     (str "{"
                      (str/join "," (map (fn [[k v]]
                                           (str (encode (if (keyword? k) (name k) (str k)))
                                                ":" (encode v)))
                                         x))
                      "}")
    (sequential? x) (str "[" (str/join "," (map encode x)) "]")
    :else (encode (str x))))

;; ----------------------------------------------------------------- parse

(defn- fail [msg i]
  (throw (ex-info (str "JSON parse error: " msg " at " i)
                  {:type ::parse-error :index i})))

(defn- ch [s i] (subs s i (inc i)))

(defn- skip-ws [s i]
  (loop [i i]
    (if (and (< i (count s)) (str/includes? " \t\n\r" (ch s i)))
      (recur (inc i))
      i)))

(declare parse-value)

(defn- parse-string* [s i]
  (loop [i (inc i) acc ""]
    (when (>= i (count s)) (fail "unterminated string" i))
    (let [c (ch s i)]
      (cond
        (= c "\"") [acc (inc i)]
        (= c "\\")
        (let [e (ch s (inc i))]
          (case e
            "\"" (recur (+ i 2) (str acc "\""))
            "\\" (recur (+ i 2) (str acc "\\"))
            "/"  (recur (+ i 2) (str acc "/"))
            "n"  (recur (+ i 2) (str acc "\n"))
            "r"  (recur (+ i 2) (str acc "\r"))
            "t"  (recur (+ i 2) (str acc "\t"))
            "b"  (recur (+ i 2) (str acc "\b"))
            "f"  (recur (+ i 2) (str acc "\f"))
            "u"  (let [hexs (subs s (+ i 2) (+ i 6))
                       code #?(:clj (Integer/parseInt hexs 16)
                               :cljs (js/parseInt hexs 16))]
                   (recur (+ i 6)
                          (str acc #?(:clj (char code)
                                      :cljs (js/String.fromCharCode code)))))
            (fail (str "bad escape \\" e) i)))
        :else (recur (inc i) (str acc c))))))

(defn- parse-number* [s i]
  (let [m (re-find #"^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?" (subs s i))]
    (when-not m (fail "bad number" i))
    [(if (re-find #"[.eE]" m)
       #?(:clj (Double/parseDouble m) :cljs (js/parseFloat m))
       #?(:clj (Long/parseLong m) :cljs (js/parseInt m 10)))
     (+ i (count m))]))

(defn- parse-array* [s i]
  (loop [i (skip-ws s (inc i)) acc []]
    (cond
      (>= i (count s)) (fail "unterminated array" i)
      (= (ch s i) "]") [acc (inc i)]
      :else
      (let [[v i] (parse-value s i)
            i (skip-ws s i)]
        (case (ch s i)
          "," (recur (skip-ws s (inc i)) (conj acc v))
          "]" [(conj acc v) (inc i)]
          (fail "expected , or ]" i))))))

(defn- parse-object* [s i]
  (loop [i (skip-ws s (inc i)) acc {}]
    (cond
      (>= i (count s)) (fail "unterminated object" i)
      (= (ch s i) "}") [acc (inc i)]
      :else
      (let [_ (when-not (= (ch s i) "\"") (fail "expected key string" i))
            [k i] (parse-string* s i)
            i (skip-ws s i)
            _ (when-not (= (ch s i) ":") (fail "expected :" i))
            [v i] (parse-value s (skip-ws s (inc i)))
            i (skip-ws s i)]
        (case (ch s i)
          "," (recur (skip-ws s (inc i)) (assoc acc k v))
          "}" [(assoc acc k v) (inc i)]
          (fail "expected , or }" i))))))

(defn- parse-value [s i]
  (let [i (skip-ws s i)]
    (when (>= i (count s)) (fail "unexpected end of input" i))
    (let [c (ch s i)]
      (cond
        (= c "\"") (parse-string* s i)
        (= c "{")  (parse-object* s i)
        (= c "[")  (parse-array* s i)
        (= c "t")  (if (= (subs s i (+ i 4)) "true") [true (+ i 4)] (fail "bad literal" i))
        (= c "f")  (if (= (subs s i (+ i 5)) "false") [false (+ i 5)] (fail "bad literal" i))
        (= c "n")  (if (= (subs s i (+ i 4)) "null") [nil (+ i 4)] (fail "bad literal" i))
        :else      (parse-number* s i)))))

(defn parse
  "JSON string -> EDN (map keys stay strings). Throws ex-info ::parse-error."
  [s]
  (let [[v i] (parse-value s 0)
        i (skip-ws s i)]
    (when (< i (count s)) (fail "trailing content" i))
    v))
