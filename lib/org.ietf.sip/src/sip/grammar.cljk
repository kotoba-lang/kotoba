(ns sip.grammar
  "Character-level SIP grammar primitives — RFC 3261 §25 (the full ABNF).
  Everything above this namespace (`sip.uri`, `sip.headers`, `sip.message`)
  is built out of these: tokens, quoted strings with backslash escapes,
  `;name=value` parameter tails, and top-level comma lists that don't get
  confused by commas hiding inside a quoted string or an angle-bracket
  URI.

  The classic wrong way to parse any of this is `(str/split s
  #\";\")` or `#\",\")` — which is exactly wrong the moment a quoted
  `Reason` string contains a comma (`Reason: SIP;cause=200;text=\"Call
  completed, thanks\"` is a real, legal header value) or a `tel:` URI's
  own parameters sit inside `<...>` next to a header-level `;tag=`. Every
  splitter here is a real scanner that tracks quote/bracket state, not a
  regex split."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------
;; token grammar (RFC 3261 §25.1)
;;
;;   token = 1*(alphanum / "-" / "." / "!" / "%" / "*" / "_" / "+" / "`"
;;              / "'" / "~")
;; ---------------------------------------------------------------------

(def ^:private token-extra-chars #{\- \. \! \% \* \_ \+ \` \' \~})

(defn char-code
  "A char's numeric code point, portable across JVM and JS.

  `(int c)` on a Clojure `Character` gives the code point on the JVM —
  but ClojureScript has no character type at all (`\\a` reads as a
  length-1 JS string), and `int` on a non-numeric string coerces through
  `NaN -> 0` rather than throwing. So `(int \\a)`, `(int \\=)`, every
  character comparison in this namespace silently became `(<= 0 0 0)` —
  true for everything — under cljs, which is a much worse failure than a
  crash: `token-char?` accepted every character including `=`, `;`, `,`
  and space, so parameter/token boundaries stopped being found at all.
  `.charCodeAt` is what actually reads a JS string's code unit."
  [c]
  #?(:clj (int c) :cljs (.charCodeAt c 0)))

(defn digit-char?
  [c]
  (<= (char-code \0) (char-code c) (char-code \9)))

(defn alpha-char?
  [c]
  (or (<= (char-code \a) (char-code c) (char-code \z))
      (<= (char-code \A) (char-code c) (char-code \Z))))

(defn alnum-char? [c] (or (digit-char? c) (alpha-char? c)))

(defn all-digits?
  "True for a non-empty string of ASCII digits only — the shape every
  numeric SIP header value (`Content-Length`, `Max-Forwards`, `CSeq`'s
  sequence number, a URI's port) must have before it's safe to hand to a
  string->number parser. Rejects `\"\"`, leading `+`/`-`, whitespace and
  anything `#?(:clj Long/parseLong :cljs js/parseInt)` would otherwise
  silently tolerate or mis-parse."
  [s]
  (and (seq s) (every? digit-char? s)))

(defn parse-uint
  "Parse `s` as a non-negative integer, or `nil` if it isn't
  `all-digits?`. The single portable numeric parser this codec uses —
  every header/URI field that's 'digits' goes through this, so there is
  exactly one place a `+123` or `12.0` or `1e10` could sneak past as a
  number, and it's guarded."
  [s]
  (when (all-digits? s)
    #?(:clj (Long/parseLong s) :cljs (js/parseInt s 10))))

(defn token-char?
  [c]
  (or (alnum-char? c)
      (contains? token-extra-chars c)))

(defn- ch [s i] (nth s i))

(defn read-token
  "From index `i` in `s`, read the longest run of token characters.
  Returns `[token next-i]`; `token` is `\"\"` (and `next-i` is `i`) if `s`
  doesn't start with a token character at `i` — this never fails, callers
  check for an empty result themselves, matching how the rest of this
  namespace reports 'nothing matched here' without throwing."
  [s i]
  (let [n (count s)]
    (loop [j i]
      (if (and (< j n) (token-char? (ch s j)))
        (recur (inc j))
        [(subs s i j) j]))))

(defn skip-lws
  "Advance past runs of space/tab (linear whitespace) starting at `i`.
  Headers are unfolded (CRLF+WSP -> WSP, `unfold-headers` in
  `sip.message`) before any of this namespace ever sees them, so LWS here
  is always a single physical line's worth of SP/HTAB — never an embedded
  CRLF."
  [s i]
  (let [n (count s)]
    (loop [j i]
      (if (and (< j n) (contains? #{\space \tab} (ch s j)))
        (recur (inc j))
        j))))

;; ---------------------------------------------------------------------
;; quoted-string (RFC 3261 §25.1)
;;
;;   quoted-string = SWS DQUOTE *(qdtext / quoted-pair) DQUOTE
;;   quoted-pair   = "\" CHAR   ; backslash escapes the following char
;;                              ; literally, whatever it is
;; ---------------------------------------------------------------------

(defn read-quoted-string
  "`s[i]` must be `\\\"`. Reads the closing-quote-terminated quoted string,
  unescaping `\\X` -> `X` (RFC 3261's `quoted-pair`: a backslash makes the
  *next* character literal, including another backslash or a quote — so
  `\\\\` is one literal backslash and `\\\"` is a literal quote that does
  NOT end the string). Returns `[unescaped-text next-i]` where `next-i`
  is just past the closing quote, or `[:error :sip/unterminated-quote]`
  if the string runs off the end of `s` with no closing quote — a
  backslash as the very last character (nothing left to escape) is the
  same error, since it can never be followed by a terminator."
  [s i]
  (let [n (count s)]
    ;; A plain vector-of-chars accumulator rather than `StringBuilder` —
    ;; `StringBuilder` doesn't exist in ClojureScript (nbb/browser), and
    ;; SIP header values are short enough that the O(n) `apply str` at
    ;; the end costs nothing worth optimising away.
    (loop [j (inc i) buf (transient [])]
      (cond
        (>= j n) [:error :sip/unterminated-quote]
        (= (ch s j) \\) (if (>= (inc j) n)
                          [:error :sip/unterminated-quote]
                          (recur (+ j 2) (conj! buf (ch s (inc j)))))
        (= (ch s j) \") [(apply str (persistent! buf)) (inc j)]
        :else (recur (inc j) (conj! buf (ch s j)))))))

(defn escape-quoted
  "Inverse of `read-quoted-string`'s unescaping: backslash-escape `\\` and
  `\"` so `text` can be written back between quotes on the wire."
  [text]
  (-> (str text)
      (str/replace "\\" "\\\\")
      (str/replace "\"" "\\\"")))

;; ---------------------------------------------------------------------
;; scan-balanced: find the end of a run of text that may contain quoted
;; strings and/or an angle-bracketed URI, stopping at the first
;; *top-level* occurrence of any character in `stop-chars` (top-level =
;; not inside a quoted string, not inside `<...>`).
;; ---------------------------------------------------------------------

(defn scan-balanced
  "From `i`, advance to the first top-level character in `stop-chars` (or
  end of string), skipping over the contents of quoted strings and
  `<...>` angle brackets so a `;` or `,` inside either of those doesn't
  end the scan early. Returns the index of the stop character (or
  `(count s)`).

  This is what makes `sip.headers`'s address-header parsing safe against
  a Request-URI-with-parameters sitting inside `<...>` right next to a
  header-level `;tag=...` — naive scanning for the next `;` would stop
  inside the URI's own parameters instead of after the closing `>`."
  [s i stop-chars]
  (let [n (count s)]
    (loop [j i depth 0]
      (if (>= j n)
        j
        (let [c (ch s j)]
          (cond
            (= c \") (let [r (read-quoted-string s j)]
                       (if (= :error (first r))
                         j ;; unterminated quote — stop here, let the caller report it
                         (recur (second r) depth)))
            (and (= c \<) (zero? depth)) (recur (inc j) (inc depth))
            (and (= c \>) (pos? depth)) (recur (inc j) (dec depth))
            (and (zero? depth) (contains? stop-chars c)) j
            :else (recur (inc j) depth)))))))

;; ---------------------------------------------------------------------
;; ;name=value parameter tails
;;
;;   generic-param = token [ EQUAL gen-value ]
;;   gen-value     = token / host / quoted-string
;; ---------------------------------------------------------------------

(defn- read-param-value
  "The right-hand side of `name=value`: a quoted string if `s[i]` is `\"`,
  otherwise the run up to the next top-level character in `stop-chars`
  (this covers both the `token` and `host` alternatives of `gen-value` —
  an IPv6 reference `[::1]` is not a `token` under the strict grammar, but
  treating 'everything up to the next stop character' as the value
  handles it without a separate host-vs-token branch). `stop-chars`
  matters for SIP-URI `uri-parameters`, where a value must not swallow
  the `?` that starts the URI's `headers` component."
  [s i stop-chars]
  (if (and (< i (count s)) (= (ch s i) \"))
    (read-quoted-string s i)
    (let [end (scan-balanced s i stop-chars)]
      [(subs s i end) end])))

(defn parse-params-tail
  "`s[i]` is either `;` (more parameters follow) or `(count s)` (none do).
  Reads every `;name` / `;name=value` pair to the end of `s`, or until a
  character in `stop-chars` (default `#{}`, i.e. read to the end — pass
  `#{\\?}` when parsing SIP-URI `uri-parameters`, which must stop before
  the URI's `?headers` component rather than absorb it into the last
  parameter's value). Returns `{name value-or-true}` — a bare `;lr` or
  `;received` shows up as `{\"lr\" true}`, matching the grammar's
  `token [ EQUAL gen-value ]` where the `= value` part is optional.
  Parameter names are lower-cased (SIP parameter names are
  case-insensitive, RFC 3261 §19.1.1 / 20); the handful of header field
  parameter *values* the wire cares about the case of (`branch`'s magic
  cookie, tags) are untouched.

  Never errors — a malformed tail (stray `;` with nothing after it, e.g.)
  is simply not added to the map, since RFC 3261 headers commonly appear
  with vendor extension parameters this codec has no obligation to
  validate."
  ([s i] (parse-params-tail s i #{}))
  ([s i stop-chars]
   (let [n (count s)
         value-stop (conj stop-chars \;)]
     (loop [j0 i params (transient {})]
       ;; RFC 3261 25.1: `SEMI = SWS ";" SWS`, so whitespace is allowed on
       ;; BOTH sides. Skipping it only after the `;` made
       ;; `<sip:a@b> ;tag=x` -- which is valid SIP, and what an unfolded
       ;; continuation line produces -- decode with no parameters at all,
       ;; silently losing the To/From tag a dialog is identified by.
       (let [j (skip-lws s j0)]
         (if (or (>= j n) (contains? stop-chars (ch s j)) (not= (ch s j) \;))
           (persistent! params)
           (let [j (skip-lws s (inc j))
                 [name j2] (read-token s j)]
             (if (empty? name)
               (persistent! params)
               (if (and (< j2 n) (= (ch s j2) \=))
                 (let [[val j3] (read-param-value s (inc j2) value-stop)]
                   ;; and the trailing half of the next SEMI is not part of
                   ;; this value: `;tag=x ;q=1` has tag "x", not "x ".
                   (recur j3 (assoc! params (str/lower name)
                                     (if (string? val) (str/trimr val) val))))
                 (recur j2 (assoc! params (str/lower name) true)))))))))))

(defn encode-params
  "Inverse of `parse-params-tail`: `{name value}` -> `;name=value` pairs,
  in a deterministic order (sorted by name) so `encode` output is
  reproducible across runs even though Clojure maps don't guarantee
  iteration order. `true` values encode as the bare `;name` form.
  A value containing characters outside `token` grammar is quoted."
  [params]
  (apply str
         (for [[k v] (sort-by key params)]
           (cond
             (true? v) (str ";" k)
             (and (string? v) (every? token-char? v) (seq v))
             (str ";" k "=" v)
             :else (str ";" k "=\"" (escape-quoted v) "\"")))))

;; ---------------------------------------------------------------------
;; top-level comma lists
;;
;;   header-value = value *(COMMA value)
;; ---------------------------------------------------------------------

(defn split-top-level
  "Split `s` on `sep-char` at the top level only — not inside a quoted
  string, and not inside `<...>` — trimming surrounding linear whitespace
  off each piece. `(split-top-level \",\" \"a, \\\"b,c\\\", <sip:x;y=1,2>\")`
  yields 2 pieces, not 4."
  [s sep-char]
  (let [n (count s)]
    (loop [i (skip-lws s 0) pieces []]
      (let [end (scan-balanced s i #{sep-char})
            piece (str/trim (subs s i end))
            pieces (conj pieces piece)]
        (if (>= end n)
          pieces
          (recur (skip-lws s (inc end)) pieces))))))
