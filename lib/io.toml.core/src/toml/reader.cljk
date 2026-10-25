(ns toml.reader
  "[TOML v1.0.0](https://toml.io/en/v1.0.0) as a reader, in portable `.cljc`,
  with no dependencies.

  A hand-written recursive-descent scanner over a character index. TOML is
  small enough that a parser combinator library would be more code than the
  grammar, and this stays a leaf.

  ## What a document becomes

      table              a Clojure map, string keys
      array              a vector
      string             a string
      integer            an integer
      float              a double, with :inf/:-inf/:nan for the named values
                         (⚠ ClojureScript has one numeric type, so `1.0`
                         reads back indistinguishable from `1` there. That is
                         the host, not this reader; do not build a wire format
                         on the difference.)
      boolean            true / false
      offset date-time   {:toml/offset-date-time \"1979-05-27T07:32:00Z\"}
      local date-time    {:toml/local-date-time \"1979-05-27T07:32:00\"}
      local date         {:toml/local-date \"1979-05-27\"}
      local time         {:toml/local-time \"07:32:00\"}

  Keys stay strings because TOML keys are strings and may contain anything;
  keywordising them would lose `\"a.b\"` and `\"\"`, both of which are legal.

  The four date-time types are tagged rather than parsed into an instant.
  TOML's local types have no offset, so there is no instant to produce, and a
  reader that invented one would be making a timezone decision on the
  caller's behalf. `kotoba-lang/time` is where that belongs.

  ## Errors

  Returned, never thrown. `read` answers `{:status :ok :value m}` or
  `{:status :error :reason kw :line n :column n}`. The reason keywords are
  contract."
  (:refer-clojure :exclude [read])
  (:require [kotoba.lang.text :as str]))

;; ── scanner state ────────────────────────────────────────────────────────────
;; A map {:s text :i index}. Every reader takes and returns one, or an error.

(defn- eof? [{:keys [s i]}] (>= i (count s)))

(defn- char-at
  "The character at `j` as a ONE-CHARACTER STRING, on both runtimes.

  `(nth \"abc\" 0)` is a `Character` on the JVM and a one-character string
  under ClojureScript, so every comparison in this file against a literal
  like `\" \"` would hold on one runtime and fail on the other. `subs`
  yields a string on both. This is the same JVM/ClojureScript character
  divergence that `scripts/verify-char-int-coercion.cljs` reports elsewhere in
  this workspace, arriving through `nth` rather than `int`."
  [s j]
  (when (and (>= j 0) (< j (count s))) (subs s j (inc j))))

(defn- peek1 [{:keys [s i]}] (char-at s i))
(defn- peek-at [{:keys [s i]} n] (char-at s (+ i n)))
(defn- adv [st n] (update st :i + n))

(defn- position
  "Line and column of the current index, for an error a human has to find."
  [{:keys [s i]}]
  (let [before (subs s 0 (min i (count s)))
        line (inc (count (re-seq #"\n" before)))
        col (- i (or (str/last-index-of before "\n") -1))]
    {:line line :column col}))

(defn- error?
  "Whether a reader returned an error.

  Not `map?`. Most readers here return `[state value]` on success, so a map
  did mean an error -- but the scanner state is ITSELF a map, so the moment
  one reader returned bare state the `map?` test started reporting success as
  failure. `read` did exactly that with `end-of-line` and every document
  failed with a nil `:reason`."
  [x]
  (and (map? x) (= :error (:status x))))

(defn- err [st reason & {:as extra}]
  (merge {:status :error :reason reason} (position st) extra))

(defn- starts? [{:keys [s i]} lit]
  (and (<= (+ i (count lit)) (count s))
       (= lit (subs s i (+ i (count lit))))))

;; ── whitespace and comments ──────────────────────────────────────────────────

(defn- ws
  "Spaces and tabs. Not newlines: TOML is line-oriented and a newline ends a
  key/value pair, so consuming one here would let `a = 1 b = 2` parse."
  [st]
  (loop [st st]
    (if (#{" " "\t"} (peek1 st)) (recur (adv st 1)) st)))

(defn- comment*
  "`#` to end of line. A comment may not contain a control character other
  than tab (§Comment), and rejecting that is what stops a stray \\r from
  being swallowed into one."
  [st]
  (if (not= "#" (peek1 st))
    st
    (loop [st (adv st 1)]
      (let [c (peek1 st)]
        (cond
          (nil? c) st
          (= c "\n") st
          :else (recur (adv st 1)))))))

(defn- ws-comment-newline
  "Whitespace, comments and newlines — the run allowed inside an array and
  between statements."
  [st]
  (loop [st st]
    (let [st' (-> st ws comment*)]
      (if (#{"\n" "\r"} (peek1 st'))
        (recur (adv st' 1))
        st'))))

;; ── strings ──────────────────────────────────────────────────────────────────

(def ^:private escapes
  {"b" "\b" "t" "\t" "n" "\n" "f" "\f" "r" "\r" "\"" "\"" "\\" "\\"})

(defn- hex->int [s]
  #?(:clj (Long/parseLong s 16) :cljs (js/parseInt s 16)))

(defn- code-point->str [n]
  #?(:clj (String. (Character/toChars (int n)))
     :cljs (.fromCodePoint js/String n)))

(defn- read-escape
  "One `\\`-escape, §String. Returns `[st text]` or an error map."
  [st]
  (let [st (adv st 1)
        c (peek1 st)]
    (cond
      (nil? c) (err st :unterminated-escape)
      (escapes c) [(adv st 1) (escapes c)]
      (#{"u" "U"} c)
      (let [n (if (= c "u") 4 8)
            digits (apply str (keep #(peek-at st (inc %)) (range n)))]
        (cond
          (< (count digits) n) (err st :truncated-unicode-escape)
          (not (re-matches #"[0-9A-Fa-f]+" digits))
          (err st :invalid-unicode-escape :digits digits)
          :else
          (let [cp (hex->int digits)]
            ;; §String: the escape must be a Unicode scalar value. Surrogates
            ;; are not, and a reader that passes them through produces a
            ;; string that cannot be encoded as UTF-8.
            (if (or (> cp 0x10FFFF) (<= 0xD800 cp 0xDFFF))
              (err st :unicode-escape-not-a-scalar-value :code-point cp)
              [(adv st (inc n)) (code-point->str cp)]))))
      :else (err st :unknown-escape :character c))))

(defn- control-char?
  "Characters TOML forbids unescaped in a string (§String): U+0000..U+0008,
  U+000A..U+001F, U+007F. Tab is allowed."
  [c]
  (let [n #?(:clj (int (first c)) :cljs (.charCodeAt c 0))]
    (or (<= 0 n 8) (<= 0x0A n 0x1F) (= n 0x7F))))

(defn- read-basic-string [st]
  (loop [st (adv st 1) acc []]
    (let [c (peek1 st)]
      (cond
        (nil? c) (err st :unterminated-string)
        (= c "\"") [(adv st 1) (apply str acc)]
        (= c "\\") (let [r (read-escape st)]
                     (if (map? r) r (recur (first r) (conj acc (second r)))))
        (control-char? c) (err st :control-character-in-string)
        :else (recur (adv st 1) (conj acc c))))))

(defn- line-ending-backslash?
  "True when the `\\` at the cursor is §String's line-ending backslash: it is
  followed only by spaces and tabs up to a newline.

  Scanned rather than matched against a windowed regex, because the run of
  whitespace has no bound and a window that is long enough today is a bug
  waiting for a longer line."
  [{:keys [s i]}]
  (loop [j (inc i)]
    (cond
      (>= j (count s)) false
      (#{" " "\t"} (char-at s j)) (recur (inc j))
      (#{"\n" "\r"} (char-at s j)) true
      :else false)))

(defn- skip-trimmed-run
  "Consume the whitespace and newlines a line-ending backslash removes."
  [st]
  (loop [st (adv st 1)]
    (if (#{" " "\t" "\n" "\r"} (peek1 st))
      (recur (adv st 1))
      st)))

(defn- read-multiline-basic [st]
  ;; §String: a newline immediately after the opening delimiter is trimmed.
  (let [st (adv st 3)
        st (cond (starts? st "\r\n") (adv st 2)
                 (= "\n" (peek1 st)) (adv st 1)
                 :else st)]
    (loop [st st acc []]
      (let [c (peek1 st)]
        (cond
          (nil? c) (err st :unterminated-string)
          ;; Up to two extra quotes may precede the delimiter, so `""""` is a
          ;; quote then the delimiter. Testing the longer run first is what
          ;; makes that work; testing `\"\"\"` first would close the string
          ;; early and leave a stray quote as the next token.
          (starts? st "\"\"\"\"\"") [(adv st 5) (apply str (conj acc "\"\""))]
          (starts? st "\"\"\"\"") [(adv st 4) (apply str (conj acc "\""))]
          (starts? st "\"\"\"") [(adv st 3) (apply str acc)]
          (= c "\\")
          (if (line-ending-backslash? st)
            (recur (skip-trimmed-run st) acc)
            (let [r (read-escape st)]
              (if (map? r) r (recur (first r) (conj acc (second r))))))
          (and (control-char? c) (not= c "\n") (not= c "\r"))
          (err st :control-character-in-string)
          :else (recur (adv st 1) (conj acc c)))))))

(defn- read-literal-string [st]
  (loop [st (adv st 1) acc []]
    (let [c (peek1 st)]
      (cond
        (nil? c) (err st :unterminated-string)
        (= c "'") [(adv st 1) (apply str acc)]
        (= c "\n") (err st :newline-in-literal-string)
        (control-char? c) (err st :control-character-in-string)
        :else (recur (adv st 1) (conj acc c))))))

(defn- read-multiline-literal [st]
  (let [st (adv st 3)
        st (cond (starts? st "\r\n") (adv st 2)
                 (= "\n" (peek1 st)) (adv st 1)
                 :else st)]
    (loop [st st acc []]
      (let [c (peek1 st)]
        (cond
          (nil? c) (err st :unterminated-string)
          (starts? st "'''''") [(adv st 5) (apply str (conj acc "''"))]
          (starts? st "''''") [(adv st 4) (apply str (conj acc "'"))]
          (starts? st "'''") [(adv st 3) (apply str acc)]
          (and (control-char? c) (not= c "\n") (not= c "\r"))
          (err st :control-character-in-string)
          :else (recur (adv st 1) (conj acc c)))))))

(defn- read-string* [st]
  (cond
    (starts? st "\"\"\"") (read-multiline-basic st)
    (starts? st "'''") (read-multiline-literal st)
    (= "\"" (peek1 st)) (read-basic-string st)
    (= "'" (peek1 st)) (read-literal-string st)
    :else (err st :expected-string)))

;; ── numbers ──────────────────────────────────────────────────────────────────
;; Matched at the cursor with anchored patterns. Order matters below: a
;; date-time starts exactly like an integer, and a float starts exactly like
;; one too, so the longest and most specific form is tried first.

(def ^:private re-offset-dt
  #"^(\d{4}-\d{2}-\d{2})[Tt ](\d{2}:\d{2}:\d{2}(?:\.\d+)?)([Zz]|[+-]\d{2}:\d{2})")
(def ^:private re-local-dt
  #"^(\d{4}-\d{2}-\d{2})[Tt ](\d{2}:\d{2}:\d{2}(?:\.\d+)?)")
(def ^:private re-local-date #"^(\d{4}-\d{2}-\d{2})")
(def ^:private re-local-time #"^(\d{2}:\d{2}:\d{2}(?:\.\d+)?)")

(def ^:private re-hex #"^[+-]?0x[0-9A-Fa-f](?:_?[0-9A-Fa-f])*")
(def ^:private re-oct #"^[+-]?0o[0-7](?:_?[0-7])*")
(def ^:private re-bin #"^[+-]?0b[01](?:_?[01])*")
(def ^:private re-float
  #"^[+-]?(?:0|[1-9](?:_?\d)*)(?:\.\d(?:_?\d)*)?(?:[eE][+-]?\d(?:_?\d)*)?")
(def ^:private re-special-float #"^[+-]?(?:inf|nan)")
(def ^:private re-dec-int #"^[+-]?(?:0|[1-9](?:_?\d)*)")

(defn- rest-of [{:keys [s i]}] (subs s (min i (count s))))

(defn- strip_ [s] (str/replace s "_" ""))

(defn- parse-int* [s radix]
  (let [neg? (str/starts-with? s "-")
        body (strip_ (str/replace s #"^[+-]" ""))
        body (if (= radix 10) body (subs body 2))
        n #?(:clj (Long/parseLong body (int radix))
             :cljs (js/parseInt body radix))]
    (if neg? (- n) n)))

(defn- parse-float* [s]
  #?(:clj (Double/parseDouble (strip_ s))
     :cljs (js/parseFloat (strip_ s))))

(defn- read-number-or-date [st]
  (let [r (rest-of st)]
    (if-let [m (re-find re-offset-dt r)]
      [(adv st (count (nth m 0)))
       {:toml/offset-date-time (nth m 0)}]
      (if-let [m (re-find re-local-dt r)]
        [(adv st (count (nth m 0))) {:toml/local-date-time (nth m 0)}]
        (if-let [m (re-find re-local-date r)]
          [(adv st (count (nth m 0))) {:toml/local-date (nth m 0)}]
          (if-let [m (re-find re-local-time r)]
            [(adv st (count (nth m 0))) {:toml/local-time (nth m 0)}]
            (if-let [m (re-find re-special-float r)]
              [(adv st (count m))
               (cond (str/ends-with? m "nan") :nan
                     (str/starts-with? m "-") :-inf
                     :else :inf)]
              (if-let [m (re-find re-hex r)]
                [(adv st (count m)) (parse-int* m 16)]
                (if-let [m (re-find re-oct r)]
                  [(adv st (count m)) (parse-int* m 8)]
                  (if-let [m (re-find re-bin r)]
                    [(adv st (count m)) (parse-int* m 2)]
                    (let [f (re-find re-float r)
                          d (re-find re-dec-int r)]
                      (cond
                        ;; A float only when it is LONGER than the integer
                        ;; match — otherwise `1` would become 1.0 and TOML
                        ;; distinguishes the two.
                        (and f d (> (count f) (count d)))
                        [(adv st (count f)) (parse-float* f)]
                        d [(adv st (count d)) (parse-int* d 10)]
                        :else (err st :expected-value)))))))))))))

;; ── keys ─────────────────────────────────────────────────────────────────────

(def ^:private re-bare-key #"^[A-Za-z0-9_-]+")

(defn- read-simple-key [st]
  (cond
    (#{"\"" "'"} (peek1 st))
    (let [r (read-string* st)] (if (map? r) r r))
    :else
    (if-let [m (re-find re-bare-key (rest-of st))]
      [(adv st (count m)) m]
      (err st :expected-key))))

(defn- read-key
  "A dotted key path, returned as a vector of strings. `a.b.c` is three
  segments; whitespace around the dots is allowed and discarded."
  [st]
  (loop [st st path []]
    (let [r (read-simple-key st)]
      (if (map? r)
        r
        (let [[st k] r
              st (ws st)]
          (if (= "." (peek1 st))
            (recur (ws (adv st 1)) (conj path k))
            [st (conj path k)]))))))

;; ── values ───────────────────────────────────────────────────────────────────

(declare read-value)

(defn- read-array [st]
  (loop [st (ws-comment-newline (adv st 1)) acc []]
    (cond
      (eof? st) (err st :unterminated-array)
      (= "]" (peek1 st)) [(adv st 1) acc]
      :else
      (let [r (read-value st)]
        (if (map? r)
          r
          (let [[st v] r
                st (ws-comment-newline st)]
            (cond
              (= "," (peek1 st)) (recur (ws-comment-newline (adv st 1)) (conj acc v))
              (= "]" (peek1 st)) [(adv st 1) (conj acc v)]
              (eof? st) (err st :unterminated-array)
              :else (err st :expected-comma-or-close-bracket))))))))

(declare assoc-path)

(defn- read-inline-table
  "§Inline Table. Newlines are NOT allowed inside one — that is the rule that
  distinguishes it from a table, and permitting them is the most common way
  an inline-table reader ends up accepting documents TOML rejects."
  [st]
  (loop [st (ws (adv st 1)) m {} seen #{}]
    (cond
      (eof? st) (err st :unterminated-inline-table)
      (= "}" (peek1 st)) [(adv st 1) m]
      :else
      (let [r (read-key st)]
        (if (map? r)
          r
          (let [[st path] r
                st (ws st)]
            (if (not= "=" (peek1 st))
              (err st :expected-equals)
              (let [r2 (read-value (ws (adv st 1)))]
                (if (map? r2)
                  r2
                  (let [[st v] r2
                        st (ws st)]
                    (cond
                      (contains? seen path) (err st :duplicate-key :key path)
                      (= "," (peek1 st))
                      (recur (ws (adv st 1)) (assoc-path m path v) (conj seen path))
                      (= "}" (peek1 st))
                      [(adv st 1) (assoc-path m path v)]
                      :else (err st :expected-comma-or-close-brace))))))))))))

(defn- read-value [st]
  (let [c (peek1 st)]
    (cond
      (nil? c) (err st :expected-value)
      (#{"\"" "'"} c) (read-string* st)
      (= "[" c) (read-array st)
      (= "{" c) (read-inline-table st)
      (starts? st "true") [(adv st 4) true]
      (starts? st "false") [(adv st 5) false]
      :else (read-number-or-date st))))

;; ── document assembly ────────────────────────────────────────────────────────

(defn- assoc-path [m path v]
  (assoc-in m path v))

(defn- describe
  "A dotted path, for an error message somebody has to act on."
  [path]
  (str/join "." path))

(defn- resolve-prefix
  "Turn a header path into a concrete path into the value map.

  A segment that names an array of tables resolves to its LAST element, so
  after `[[fruit]]` a following `[fruit.variety]` lands inside the fruit that
  is being built rather than beside the array. Getting this wrong produces a
  document that parses and is shaped differently from what the file says."
  [{:keys [value aot]} path]
  (loop [segs path here [] out []]
    (if (empty? segs)
      {:status :ok :path out}
      (let [k (first segs)
            here (conj here k)
            out (conj out k)
            cur (get-in value out ::missing)]
        (cond
          (contains? aot here)
          (let [idx (dec (count (get-in value out)))]
            (recur (rest segs) here (conj out idx)))
          (= cur ::missing) (recur (rest segs) here out)
          (map? cur) (recur (rest segs) here out)
          :else {:status :error :reason :key-is-not-a-table :key (describe out)})))))

(defn- apply-key
  "Assign `v` at `path` relative to the current table, with the duplicate and
  closed-table rules of §Keys and §Inline Table."
  [{:keys [value current keys' inline dotted] :as ctx} path v st]
  (let [full (into current path)
        ;; Every proper prefix of a dotted key becomes a table, and none of
        ;; them may already hold a value or belong to an inline table.
        prefixes (map #(vec (take (inc %) full)) (range (dec (count full))))]
    (cond
      (contains? keys' full) (err st :duplicate-key :key (describe full))
      ;; The inline check comes FIRST because both are true of `a = {b = 1}`
      ;; followed by `a.c = 2` -- `a` holds a value and `a` is an inline
      ;; table -- and only one of those tells the reader what to change.
      (some #(contains? inline %) prefixes)
      (err st :inline-table-is-closed
           :key (describe (first (filter #(contains? inline %) prefixes))))
      (some #(contains? keys' %) prefixes)
      (err st :key-is-not-a-table
           :key (describe (first (filter #(contains? keys' %) prefixes))))
      :else
      (assoc ctx
             :value (assoc-in value full v)
             :keys' (conj keys' full)
             :inline (if (and (map? v) (not (contains? dotted full)))
                       ;; A value that came from `{…}` is closed to later keys.
                       (conj inline full)
                       inline)
             :dotted (into dotted prefixes)))))

(defn- open-table [{:keys [value explicit aot dotted keys'] :as ctx} path st]
  (let [r (resolve-prefix ctx (vec (butlast path)))]
    (if (= :error (:status r))
      (merge (err st (:reason r)) (dissoc r :status))
      (let [base (:path r)
            full (conj base (last path))]
        (cond
          (contains? explicit (vec path)) (err st :table-redefined :key (describe path))
          (contains? aot (vec path)) (err st :table-was-an-array-of-tables :key (describe path))
          (contains? keys' full) (err st :key-is-not-a-table :key (describe path))
          (contains? dotted full) (err st :table-redefined :key (describe path))
          :else
          (assoc ctx
                 :value (if (= ::missing (get-in value full ::missing))
                          (assoc-in value full {})
                          value)
                 :current full
                 :explicit (conj explicit (vec path))))))))

(defn- open-array-of-tables [{:keys [value explicit aot] :as ctx} path st]
  (let [r (resolve-prefix ctx (vec (butlast path)))]
    (if (= :error (:status r))
      (merge (err st (:reason r)) (dissoc r :status))
      (let [base (:path r)
            full (conj base (last path))
            cur (get-in value full ::missing)]
        (cond
          (contains? explicit (vec path))
          (err st :conflicting-array-of-tables :key (describe path))
          (and (not= cur ::missing) (not (vector? cur)))
          (err st :key-is-not-an-array-of-tables :key (describe path))
          :else
          (let [arr (if (= cur ::missing) [] cur)
                arr (conj arr {})]
            (assoc ctx
                   :value (assoc-in value full arr)
                   :current (conj full (dec (count arr)))
                   :aot (conj aot (vec path)))))))))

(defn- read-header [ctx st]
  (let [aot? (starts? st "[[")
        st (adv st (if aot? 2 1))
        r (read-key (ws st))]
    (if (map? r)
      r
      (let [[st path] r
            st (ws st)]
        (if-not (starts? st (if aot? "]]" "]"))
          (err st :expected-close-bracket)
          (let [st (adv st (if aot? 2 1))
                ctx' (if aot?
                       (open-array-of-tables ctx path st)
                       (open-table ctx path st))]
            (if (= :error (:status ctx'))
              ctx'
              [st ctx'])))))))

(defn- read-statement [ctx st]
  (let [st (ws st)]
    (cond
      (= "[" (peek1 st)) (read-header ctx st)
      :else
      (let [r (read-key st)]
        (if (map? r)
          r
          (let [[st path] r
                st (ws st)]
            (if (not= "=" (peek1 st))
              (err st :expected-equals)
              (let [r2 (read-value (ws (adv st 1)))]
                (if (map? r2)
                  r2
                  (let [[st v] r2
                        ctx' (apply-key ctx path v st)]
                    (if (= :error (:status ctx'))
                      ctx'
                      [st ctx'])))))))))))

(defn- end-of-line
  "Whitespace, an optional comment, then a newline or end of input. Anything
  else after a statement is a second statement on one line, which TOML does
  not allow."
  [st]
  (let [st (-> st ws comment*)]
    (cond
      (eof? st) st
      (= "\n" (peek1 st)) (adv st 1)
      (starts? st "\r\n") (adv st 2)
      :else (err st :unexpected-trailing-content))))

(defn read
  "Parse a TOML document. Returns `{:status :ok :value m}` or
  `{:status :error :reason kw :line n :column n}`."
  [text]
  (loop [st {:s (str text) :i 0}
         ctx {:value {} :current [] :explicit #{} :aot #{}
              :inline #{} :dotted #{} :keys' #{}}]
    (let [st (ws-comment-newline st)]
      (if (eof? st)
        {:status :ok :value (:value ctx)}
        (let [r (read-statement ctx st)]
          (if (map? r)
            r
            (let [[st ctx] r
                  st' (end-of-line st)]
              (if (error? st')
                st'
                (recur st' ctx)))))))))

(defn read!
  "`read`, throwing on a malformed document."
  [text]
  (let [r (read text)]
    (if (= :ok (:status r))
      (:value r)
      (throw (ex-info (str "toml: " (name (:reason r))
                           " at line " (:line r) " column " (:column r))
                      r)))))
