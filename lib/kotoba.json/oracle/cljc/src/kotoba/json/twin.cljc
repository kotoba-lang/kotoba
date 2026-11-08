(ns kotoba.json.twin
  "Portable JSON engine backing the `kotoba.lang.json` oracle twin.

  Oracle file (JUN-1024): a .cljc twin of json.core's .cljk host
  implementation for hosts that cannot read .cljk (stock nbb, Basilisp).
  Ported from the `:clj` branch (the `:cljs` branch is identical except for
  its parse interop). Every host-interop point below carries a `:lpy`
  branch with the same values.

  Placement and naming are load-order decisions, verified 2026-11-08:
  - nbb prefers a sibling `.cljk` over `.cljc`, so a twin next to the
    source never loads on nbb. Twins live under `oracle/cljc/src/` (no
    `.cljk` there) and the oracle runner puts that directory first on the
    classpath.
  - Basilisp cannot load any `json.*` namespace: top-level `json`
    resolves to Python's stdlib `json` package and `json.core` is then
    looked up inside it. The engine therefore lives in `kotoba.json.twin`
    (`kotoba.*` has no stdlib collision); the facade twin keeps the real
    `kotoba.lang.json` name and delegates here.

  Normalizations (same values, portable spelling):
  - single characters travel as one-character STRINGS (bb `nth` answers a
    Character while nbb/Basilisp answer a string; `(char N)` prints
    differently on each). `char-code` / `code-unit-str` convert at the rim.
  - astral results (`\\uD83D\\uDE00` pairs) are built from UTF-8 bytes, so all
    three runners answer the same string.
  - `clojure.string` is required: `join` / `includes?` were probed present
    on bb, nbb and Basilisp.

  Deliberate divergences from the .cljk host (reported, never aligned):
  - a LONE `\\uD800`-`\\uDFFF` escape is refused (\"invalid JSON unicode
    escape\"). The host keeps the lone surrogate; the Kotoba reading
    refuses it because a Kotoba string is valid UTF-8 and cannot hold one.
  - whole-valued floats past Long range print host-dependently (pre-existing
    host divergence: `(long n)` saturates on :clj, `Math.trunc` does not on
    :cljs). Shared cases stay inside Long range.

  Never a build, gate, runtime or fallback input -- one-off measurement
  oracle only (ADR 0026 D18)."
  (:require [clojure.string :as str]))

;; ---------------------------------------------------------------------------
;; Portability rim: every host difference is visible in this section.
;; ---------------------------------------------------------------------------

(defn- ch-at
  "One-character string at index `i`, or nil past the end."
  [s i]
  (when (and (<= 0 i) (< i (count s)))
    (subs s i (inc i))))

(defn- char-code
  "Code point of one single character (a Character or a 1-char string)."
  [ch]
  #?(:lpy (ord (str ch))
     :clj (int (.charAt (str ch) 0))
     :cljs (.charCodeAt (str ch) 0)))

(defn- code-unit-str
  "String for one BMP code unit `n`, lone surrogates included (the host
  keeps them; so does this twin). Python `chr` refuses surrogates, so
  those arrive via CESU-8 bytes decoded with surrogatepass."
  [n]
  #?(:lpy (if (<= 55296 n 57343)
            (.decode (python/bytes
                      [237
                       (+ 160 (bit-and (bit-shift-right n 6) 15))
                       (+ 128 (bit-and n 63))])
                     "utf-8" "surrogatepass")
            (chr n))
     :clj (str (char n))
     :cljs (.fromCharCode js/String n)))

(defn- astral-str
  "String for the astral code point `cp` (a surrogate pair combined),
  built from UTF-8 bytes so every runner answers the same string."
  [cp]
  #?(:lpy (.decode (python/bytes
                    [(bit-or 240 (bit-shift-right cp 18))
                     (bit-or 128 (bit-and (bit-shift-right cp 12) 63))
                     (bit-or 128 (bit-and (bit-shift-right cp 6) 63))
                     (bit-or 128 (bit-and cp 63))])
                   "utf-8")
     :clj (str (String. (byte-array (mapv unchecked-byte
                                          [(bit-or 240 (bit-shift-right cp 18))
                                           (bit-or 128 (bit-and (bit-shift-right cp 12) 63))
                                           (bit-or 128 (bit-and (bit-shift-right cp 6) 63))
                                           (bit-or 128 (bit-and cp 63))]))
                        "UTF-8"))
     :cljs (.decode (js/TextDecoder.)
                    (js/Uint8Array. #js [(bit-or 240 (bit-shift-right cp 18))
                                         (bit-or 128 (bit-and (bit-shift-right cp 12) 63))
                                         (bit-or 128 (bit-and (bit-shift-right cp 6) 63))
                                         (bit-or 128 (bit-and cp 63))]))))

(defn- parse-long-twin
  [s]
  #?(:lpy (parse-long s)
     :clj (Long/parseLong (str s))
     :cljs (js/parseInt s 10)))

(defn- parse-double-twin
  [s]
  #?(:lpy (parse-double s)
     :clj (Double/parseDouble (str s))
     :cljs (js/parseFloat s)))

;; ---------------------------------------------------------------------------
;; Emit. Ported from the host branches (identical on :clj/:cljs); the only
;; host differences were the number parser and char codes, handled above.
;; ---------------------------------------------------------------------------

(def ^:private hex-digits "0123456789abcdef")

(defn- hex4
  "4-digit hex for a JSON `\\uXXXX` escape (portable: bit ops + a lookup
  table, no Long/Integer interop)."
  [n]
  (apply str (for [shift [12 8 4 0]] (nth hex-digits (bit-and (bit-shift-right n shift) 0xf)))))

(def ^:private quote-str "\"")
(def ^:private backslash-str "\\")

(defn- esc [s]
  (apply str
         (map (fn [ch]
                (let [code (char-code ch)]
                  (cond
                    (= code 34) (str backslash-str quote-str)
                    (= code 92) (str backslash-str backslash-str)
                    (= code 8) "\\b"
                    (= code 12) "\\f"
                    (= code 10) "\\n"
                    (= code 13) "\\r"
                    (= code 9) "\\t"
                    (< code 32) (str "\\u" (hex4 code))
                    :else (str ch))))
              (map #(subs s % (inc %)) (range (count s))))))

(defn- kstr [k] (if (keyword? k) (name k) (str k)))

(defn- whole-float?
  [n]
  #?(:lpy (.is_integer n)
     :clj (== (double n) (Math/rint (double n)))
     :cljs (js/Number.isInteger n)))

(defn- int-str
  [n]
  #?(:lpy (str (python/int n))
     :clj (str (long n))
     :cljs (str (js/Math.trunc n))))

(defn- numstr [n]
  (if (and (number? n) (not (integer? n)) (whole-float? n))
    (int-str n)
    (str n)))

(declare emit)

(defn- emit [x ind pretty?]
  (let [pad  (apply str (repeat ind "  "))
        pad+ (str pad "  ")
        sep  (if pretty? ",\n" ",")
        kv   (if pretty? ": " ":")]
    (cond
      (nil? x)                      "null"
      (boolean? x)                  (str x)
      (number? x)                   (numstr x)
      (or (string? x) (keyword? x)) (str quote-str (esc (kstr x)) quote-str)
      (map? x) (if (empty? x) "{}"
                 (let [entries (if pretty? x (sort-by (comp kstr key) x))]
                   (str "{"
                        (when pretty? "\n")
                        (str/join sep
                                  (for [[k v] entries]
                                    (str (when pretty? pad+)
                                         quote-str (esc (kstr k)) quote-str kv
                                         (emit v (inc ind) pretty?))))
                        (when pretty? (str "\n" pad))
                        "}")))
      (sequential? x) (if (empty? x) "[]"
                        (str "["
                             (when pretty? "\n")
                             (str/join sep
                                       (for [v x]
                                         (str (when pretty? pad+)
                                              (emit v (inc ind) pretty?))))
                             (when pretty? (str "\n" pad))
                             "]"))
      :else (str quote-str (esc (str x)) quote-str))))

(defn json
  "Serialize EDN to a 2-space pretty JSON string. Keyword keys/values become strings."
  [x]
  (emit x 0 true))

(defn encode
  "Serialize EDN to compact JSON with deterministic map key order."
  [x]
  (emit x 0 false))

;; ---------------------------------------------------------------------------
;; Decode. Ported from the host branches; the parser is identical, only the
;; character/number interop differs (handled in the rim above).
;; ---------------------------------------------------------------------------

(defn- hex-val
  "One hex digit's value (bounds are numeric literals, never `(int \\0)`)."
  [ch]
  (let [i (char-code ch)]
    (cond
      (<= 48 i 57) (- i 48)                ; 0-9
      (<= 97 i 102) (+ 10 (- i 97))        ; a-f
      (<= 65 i 70) (+ 10 (- i 65))         ; A-F
      :else (throw (ex-info "invalid JSON unicode escape" {:char ch})))))

(defn- codepoint [s i]
  (reduce (fn [n ch] (+ (* n 16) (hex-val ch))) 0
          (map #(subs s % (inc %)) (range i (+ i 4)))))

(def ^:private ws-set #{" " "\t" "\n" "\r"})

(defn- ws? [ch] (contains? ws-set ch))

(defn- skip-ws [s i]
  (let [n (count s)]
    (loop [i i]
      (if (and (< i n) (ws? (subs s i (inc i))))
        (recur (inc i))
        i))))

(declare read-value)

(defn- read-string* [s i]
  (loop [i (inc i) out []]
    (let [ch (ch-at s i)]
      (cond
        (nil? ch) (throw (ex-info "unterminated JSON string" {:pos i}))
        (< (char-code ch) 32) (throw (ex-info "unescaped JSON control character" {:pos i}))
        (= ch quote-str) [(apply str out) (inc i)]
        (= ch backslash-str)
        (let [e (ch-at s (inc i))]
          (cond
            (nil? e) (throw (ex-info "unterminated JSON string" {:pos i}))
            (= e quote-str) (recur (+ i 2) (conj out quote-str))
            (= e backslash-str) (recur (+ i 2) (conj out backslash-str))
            (= e "/") (recur (+ i 2) (conj out "/"))
            (= e "b") (recur (+ i 2) (conj out (code-unit-str 8)))
            (= e "f") (recur (+ i 2) (conj out (code-unit-str 12)))
            (= e "n") (recur (+ i 2) (conj out (code-unit-str 10)))
            (= e "r") (recur (+ i 2) (conj out (code-unit-str 13)))
            (= e "t") (recur (+ i 2) (conj out (code-unit-str 9)))
            (= e "u")
            (let [u (when (<= (+ i 6) (count s))
                      (try (codepoint s (+ i 2))
                           (catch #?(:lpy python/Exception :clj Exception :cljs :default) _
                             ::bad)))]
              (cond
                (or (nil? u) (= u ::bad))
                (throw (ex-info "invalid JSON unicode escape" {:pos (+ i 2)}))
                (<= 55296 u 56319)
                (let [lo (when (and (= (ch-at s (+ i 6)) backslash-str)
                                    (= (ch-at s (+ i 7)) "u")
                                    (<= (+ i 12) (count s)))
                           (try (codepoint s (+ i 8))
                                (catch #?(:lpy python/Exception :clj Exception :cljs :default) _
                                  ::bad)))]
                  (if (and (some? lo) (not (= lo ::bad)) (<= 56320 lo 57343))
                    (recur (+ i 12) (conj out (astral-str (+ 65536 (+ (* (- u 55296) 1024)
                                                                     (- lo 56320))))))
                    (throw (ex-info "invalid JSON unicode escape" {:pos (+ i 2)}))))
                (<= 56320 u 57343)
                (throw (ex-info "invalid JSON unicode escape" {:pos (+ i 2)}))
                :else
                (recur (+ i 6) (conj out (code-unit-str u)))))
            :else (throw (ex-info "invalid JSON escape" {:pos i :escape e}))))
        :else (recur (inc i) (conj out ch))))))

(defn- char-at= [s i c]
  (and (<= 0 i) (< i (count s)) (= c (subs s i (inc i)))))

(defn- digit-at? [s i]
  (and (<= 0 i) (< i (count s))
       (let [c (char-code (subs s i (inc i)))]
         (<= 48 c 57))))

(defn- skip-digits [s i]
  (loop [j i] (if (digit-at? s j) (recur (inc j)) j)))

(defn- json-number? [s]
  (let [i (if (char-at= s 0 "-") 1 0)
        i (cond (char-at= s i "0") (inc i)
                (digit-at? s i) (skip-digits s i)
                :else -1)
        i (if (char-at= s i ".")
            (if (digit-at? s (inc i)) (skip-digits s (inc i)) -1)
            i)
        i (if (or (char-at= s i "e") (char-at= s i "E"))
            (let [j (if (or (char-at= s (inc i) "+") (char-at= s (inc i) "-")) (+ i 2) (inc i))]
              (if (digit-at? s j) (skip-digits s j) -1))
            i)]
    (= i (count s))))

(def ^:private number-chars #{"0" "1" "2" "3" "4" "5" "6" "7" "8" "9"
                              "e" "E" "+" "-" "."})

(defn- read-number [s i]
  (let [n (count s)
        end (loop [j i]
              (if (and (< j n) (contains? number-chars (subs s j (inc j))))
                (recur (inc j))
                j))
        token (subs s i end)]
    (when-not (json-number? token)
      (throw (ex-info "invalid JSON number" {:pos i :token token})))
    [(if (or (str/includes? token ".") (str/includes? token "e") (str/includes? token "E"))
       (parse-double-twin token)
       (parse-long-twin token))
     end]))

(defn- read-array [s i]
  (loop [i (skip-ws s (inc i)) out []]
    (let [ch (ch-at s i)]
      (if (= ch "]")
        [out (inc i)]
        (let [[v j] (read-value s i)
              j (skip-ws s j)
              ch (ch-at s j)]
          (cond
            (= ch ",") (let [next-index (skip-ws s (inc j))]
                         (when (= (ch-at s next-index) "]")
                           (throw (ex-info "trailing JSON array comma" {:pos next-index})))
                         (recur next-index (conj out v)))
            (= ch "]") [(conj out v) (inc j)]
            :else (throw (ex-info "expected comma or array end" {:pos j :char ch}))))))))

(defn- read-object [s i]
  (loop [i (skip-ws s (inc i)) out {}]
    (let [ch (ch-at s i)]
      (if (= ch "}")
        [out (inc i)]
        (let [[k j] (do (when-not (= (ch-at s i) quote-str)
                          (throw (ex-info "JSON object key must be a string" {:pos i})))
                        (read-string* s i))
              j (skip-ws s j)]
          (when-not (= (ch-at s j) ":")
            (throw (ex-info "expected object colon" {:pos j})))
          (let [[v j] (read-value s (skip-ws s (inc j)))
                j (skip-ws s j)
                ch (ch-at s j)]
            (cond
              (= ch ",") (let [next-index (skip-ws s (inc j))]
                           (when (= (ch-at s next-index) "}")
                             (throw (ex-info "trailing JSON object comma" {:pos next-index})))
                           (recur next-index (assoc out k v)))
              (= ch "}") [(assoc out k v) (inc j)]
              :else (throw (ex-info "expected comma or object end" {:pos j :char ch})))))))))

(defn- starts? [s i lit] (= lit (subs s i (min (count s) (+ i (count lit))))))

(defn- read-value [s i]
  (let [i (skip-ws s i)
        ch (ch-at s i)]
    (cond
      (= ch quote-str) (read-string* s i)
      (= ch "{") (read-object s i)
      (= ch "[") (read-array s i)
      (= ch "t") (if (starts? s i "true") [true (+ i 4)] (throw (ex-info "invalid JSON token" {:pos i})))
      (= ch "f") (if (starts? s i "false") [false (+ i 5)] (throw (ex-info "invalid JSON token" {:pos i})))
      (= ch "n") (if (starts? s i "null") [nil (+ i 4)] (throw (ex-info "invalid JSON token" {:pos i})))
      (or (= ch "-") (and ch (<= 48 (char-code ch) 57))) (read-number s i)
      :else (throw (ex-info "invalid JSON value" {:pos i :char ch})))))

(defn decode
  "Parse JSON into Clojure data. Object keys are strings."
  [s]
  (let [[v i] (read-value s 0)
        i (skip-ws s i)]
    (when-not (= i (count s))
      (throw (ex-info "trailing JSON input" {:pos i})))
    v))
