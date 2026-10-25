(ns adl.dadl
  "dADL (Data Archetype Definition Language) -- the `<...>` keyed-value
  syntax ADL 1.4 uses for everything that ISN'T a constraint: the
  `language`, `description`, `ontology`, `revision_history` and
  `annotations` sections, and (reused verbatim by adl.cadl, since it is
  textually identical there) the primitive-constraint-object form
  `C_DV_QUANTITY <property = <...> list = <...>>`.

  Parsed values are plain EDN, not a bespoke record type, so a caller can
  `get-in`/`update` them with ordinary Clojure functions:

    string / number / boolean        -- as themselves
    `[id::code, code, ...]`          -- {:adl/kind :code-phrase :terminology id-or-nil :codes [...]}
    a `<>` with nothing in it        -- {:adl/kind :empty}
    a comma list of >1 primitives    -- {:adl/kind :list :items [...]}
    `key = <v> ...` / `[\"k\"] = <v> ...`
                                      -- {:adl/kind :object :entries [[key-repr v] ...]}
                                         where key-repr is a bare string for
                                         `name = ...` or {:adl/bracket-key s}
                                         for `[\"s\"] = ...`

  A `<...>` holding exactly ONE primitive/object collapses to that value
  directly rather than a 1-element :list -- there is no dADL syntax where
  the presence of an outer list-wrapper for a single item is itself
  significant, so unwrapping it loses no round-trip information (serializing
  a bare value and serializing a 1-item list of it produce the same text)
  while sparing every caller a `(if (= 1 (count items)) (first items) ...)`."
  (:require [kotoba.lang.text :as str]
            [adl.lexer :as lex]))

;; ---------------------------------------------------------------------
;; parsing
;; ---------------------------------------------------------------------

(defn parse-code-phrase
  "`[id::code, code, ...]` or bare `[code]` at i (s[i] = \"[\"). Distinct
  from a dADL bracket-key `[\"k\"]` by content, not position: this is
  called only where the caller has already established (by peeking past
  the `[`) that the first token is NOT a quoted string."
  [s i]
  (let [j (lex/expect s i "[")
        [first-tok k] (lex/read-dotted-code s j)
        double-colon? (lex/peek-lit? s k "::")]
    (if double-colon?
      (let [k2 (lex/expect s k "::")]
        (loop [codes [] k k2]
          (let [[code k3] (lex/read-dotted-code s k)
                codes (conj codes code)]
            (if (lex/peek-lit? s k3 ",")
              (recur codes (lex/expect s k3 ","))
              [{:adl/kind :code-phrase :terminology first-tok :codes codes}
               (lex/expect s k3 "]")]))))
      ;; no `id::`: either one bare code, or (rarer) a comma list of bare
      ;; codes sharing an implicit/local terminology, e.g. `[ac0001]`.
      (loop [codes [first-tok] k k]
        (if (lex/peek-lit? s k ",")
          (let [k2 (lex/expect s k ",")
                [code k3] (lex/read-dotted-code s k2)]
            (recur (conj codes code) k3))
          [{:adl/kind :code-phrase :terminology nil :codes codes}
           (lex/expect s k "]")])))))

(defn- iso8601-duration-ch? [c] (boolean (and c (re-matches #"[A-Za-z0-9]" c))))

(defn- read-piped-bound
  "A piped-interval bound is either a plain number or an ISO 8601 duration
  literal (`PT5M`, `P1Y`, `PT0S`) -- real archetypes constrain DV_DURATION
  values this way (`value matches {|PT5M|}`). Distinguished on sight: a
  duration literal always starts with `P`; nothing else legally does at
  this position."
  [s i]
  (let [j (lex/skip-ws-and-comments s i)]
    (if (= "P" (lex/char-at s j))
      (let [n (count s)
            end (loop [k (inc j)] (if (and (< k n) (iso8601-duration-ch? (lex/char-at s k))) (recur (inc k)) k))]
        [{:adl/kind :duration :text (subs s j end)} end])
      (lex/read-number s j))))

(defn- piped-bound-str [b] (if (and (map? b) (= :duration (:adl/kind b))) (:text b) (str b)))

(defn parse-piped-interval
  "`|min..max|`, `|>=n|`, `|<=n|`, `|>n|`, `|<n|`, or `|n|` (exact), where a
  bound is a number or (see read-piped-bound) an ISO 8601 duration literal.
  This is formally a cADL construct (a magnitude/precision constraint), but
  it also occurs as an ordinary dADL primitive VALUE: a C_DV_QUANTITY
  constraint's `list` entries are dADL-shaped (`magnitude = <|>=0.0|>`,
  `precision = <|2|>`) with a piped interval as the value, right alongside
  plain strings (`units = <\"mm[Hg]\">`) -- so this lives here, not in
  adl.cadl, and adl.cadl re-exports it rather than duplicating it.
  `s[i]` must be `|`."
  [s i]
  (let [j (lex/expect s i "|")
        cmp (cond (lex/peek-lit? s j ">=") [:>= (lex/expect s j ">=")]
                  (lex/peek-lit? s j "<=") [:<= (lex/expect s j "<=")]
                  (lex/peek-lit? s j ">") [:> (lex/expect s j ">")]
                  (lex/peek-lit? s j "<") [:< (lex/expect s j "<")]
                  :else nil)]
    (if cmp
      (let [[op j2] cmp
            [n j3] (read-piped-bound s j2)]
        [{:adl/kind :piped-interval :op op :value n} (lex/expect s j3 "|")])
      (let [[lo j2] (read-piped-bound s j)]
        (if (lex/peek-lit? s j2 "..")
          (let [j3 (lex/expect s j2 "..")
                [hi j4] (read-piped-bound s j3)]
            [{:adl/kind :piped-interval :op :range :lower lo :upper hi} (lex/expect s j4 "|")])
          [{:adl/kind :piped-interval :op := :value lo} (lex/expect s j2 "|")])))))

(defn piped-interval-str [{:keys [op value lower upper]}]
  (str "|" (case op
             := (piped-bound-str value)
             :range (str (piped-bound-str lower) ".." (piped-bound-str upper))
             (str (name op) (piped-bound-str value)))
       "|"))

(declare parse-value)

(defn- parse-primitive
  "One primitive: string, number, boolean, code-phrase, piped interval, or
  a bare `...` ellipsis. That last one is not part of ADL's own grammar,
  but shows up verbatim in real published CKM archetypes as an authoring
  placeholder for a truncated example list (`terminologies_available =
  <\"SNOMED-CT\", ...>`, `other_contributors = <\"...\", ...>` -- seen in
  both `openEHR-EHR-OBSERVATION.demo.v1` and `.intravascular_pressure.v1`
  independently). Refusing to parse it would make this library unable to
  read real openEHR org content over one non-conformant token; accepting
  it and round-tripping it back out verbatim is more useful than either
  silently dropping it or hard-failing on it."
  [s i]
  (let [j (lex/skip-ws-and-comments s i)]
    (cond
      (lex/peek-lit? s j "\"") (lex/read-string-literal s j)
      (lex/peek-lit? s j "True") [true (lex/expect s j "True")]
      (lex/peek-lit? s j "False") [false (lex/expect s j "False")]
      (lex/peek-lit? s j "...") [{:adl/kind :ellipsis} (lex/expect s j "...")]
      (lex/peek-lit? s j "[") (parse-code-phrase s j)
      (lex/peek-lit? s j "|") (parse-piped-interval s j)
      (or (lex/digit-ch? (lex/char-at s j))
          (lex/peek-lit? s j "-"))
      (lex/read-number s j)
      :else
      (throw (lex/adl-error :adl/expected-primitive
                             {:at j :context (subs s j (min (count s) (+ j 40)))})))))

(defn- bracket-key?
  "True when s[i] is `[` immediately introducing a quoted-string key (an
  assoc-map entry `[\"k\"] = ...`) rather than a code-phrase primitive
  (`[id::code]`). A plain peek, never throws/consumes -- callers use it to
  decide whether to keep looping over entries, including at the point where
  there may be nothing left at all (the closing `>`)."
  [s i]
  (let [j (lex/skip-ws-and-comments s i)]
    (and (lex/peek-lit? s j "[")
         (lex/peek-lit? s (inc j) "\""))))

(defn- parse-entry
  "One `name = <value>` or `[\"key\"] = <value>` pair. Returns
  [[key-repr value] next-index]."
  [s i]
  (let [j (lex/skip-ws-and-comments s i)]
    (if (lex/peek-lit? s j "[")
      (let [k (lex/expect s j "[")
            [key-str k2] (lex/read-string-literal s k)
            k3 (lex/expect s k2 "]")
            k4 (lex/expect s k3 "=")
            [v k5] (parse-value s k4)]
        [[{:adl/bracket-key key-str} v] k5])
      (let [[name k2] (lex/read-ident s j)
            k3 (lex/expect s k2 "=")
            [v k4] (parse-value s k3)]
        [[name v] k4]))))

(defn- try-parse-entry
  "Like parse-entry, but returns nil (consuming nothing -- callers only
  ever call this at a point where failure means \"the object body is
  over\", so there is nothing to roll back other than not returning an
  index) instead of throwing when the input at i is not shaped like an
  entry. This is how parse-object-body's loop terminates: dADL sections and
  object bodies have no reserved end-keyword, they simply stop being
  `key = value` pairs (the next token is either `>` or an outer section
  name, and neither is followed by `=`/parses as an entry)."
  [s i]
  (try
    (parse-entry s i)
    (catch #?(:clj Exception :cljs :default) e
      ;; Only a *malformed-entry-shape* failure means \"not an entry\" --
      ;; re-throw anything else (a genuinely malformed nested value, e.g.)
      ;; so it surfaces as its own real error instead of being silently
      ;; read as \"this must not have been an entry after all\" and
      ;; misreported one level up as an unrelated `:adl/expected-primitive`
      ;; on the entry's NAME. Caught this exact miscategorization during
      ;; development: a bug in code-phrase parsing was being reported as
      ;; if `property` were not a valid dADL identifier.
      (if (lex/adl-error? (ex-data e)) nil (throw e)))))

(defn- consume-entries
  "Loops try-parse-entry from k, accumulating [key value] pairs, and stops
  the moment it returns nil -- the ONLY thing that means \"no more
  entries\" (see try-parse-entry's own docstring: it re-throws anything
  that isn't specifically a malformed-entry-shape failure, so a genuine
  internal bug never gets silently read as end-of-object here either).
  Returns [entries next-index].

  Earlier versions of this loop kept going based on a separate, weaker
  \"does the next token merely start with an identifier or a bracket-key\"
  peek (`looks-like-entry-start?`) instead of re-trying the entry parse
  itself. That is unsound: the very next SECTION keyword after a one-entry
  dADL section (e.g. `description` right after a one-line `language`
  section's `original_language = <...>`) also starts with an identifier,
  so the peek said \"keep going\", `parse-entry` then choked expecting `=`
  after `description`, and the resulting error pointed at content several
  lines later -- caught round-tripping a real published archetype whose
  `language` section is exactly this shape."
  [s k]
  (loop [entries [] k k]
    (if-let [[kv k2] (try-parse-entry s k)]
      (recur (conj entries kv) k2)
      [entries k])))

(defn parse-value-body
  "Parses the content between `<` and the matching `>` (exclusive of both
  delimiters) starting at i. Returns [value next-index], where next-index
  points at the `>`."
  [s i]
  (let [j (lex/skip-ws-and-comments s i)]
    (cond
      (lex/peek-lit? s j ">")
      [{:adl/kind :empty} j]

      ;; `[\"k\"] = ...` (assoc list) vs a bare `[id::code]` primitive value
      ;; are disambiguated by what's inside the bracket, not just its
      ;; presence -- see bracket-key?.
      (and (lex/peek-lit? s j "[") (bracket-key? s j))
      (let [[entries k2] (consume-entries s j)]
        [{:adl/kind :object :entries entries} k2])

      (and (lex/ident-start-ch? (lex/char-at s j))
           (not (lex/peek-lit? s j "True"))
           (not (lex/peek-lit? s j "False"))
           (try-parse-entry s j))
      (let [[entries k2] (consume-entries s j)]
        [{:adl/kind :object :entries entries} k2])

      :else
      (loop [items [] k j]
        (let [[v k2] (parse-primitive s k)
              items (conj items v)]
          (if (lex/peek-lit? s k2 ",")
            (recur items (lex/expect s k2 ","))
            [(case (count items)
               1 (first items)
               {:adl/kind :list :items items})
             k2]))))))

(defn parse-value
  "Parses a full `<...>` dADL value at i. Returns [value next-index]."
  [s i]
  (let [j (lex/expect s i "<")
        [v k] (parse-value-body s j)]
    [v (lex/expect s k ">")]))

(defn parse
  "Public entry point: parses one `<...>` dADL value from the start of `s`,
  returning `[:ok value]` or `[:error kw detail]` -- never throws."
  [s]
  (try
    (let [[v i] (parse-value s 0)
          i (lex/skip-ws-and-comments s i)]
      (if (= i (count s))
        [:ok v]
        [:error :adl/trailing-content {:at i}]))
    (catch #?(:clj Exception :cljs :default) e
      (if (lex/adl-error? (ex-data e))
        [:error (:adl/error (ex-data e)) (dissoc (ex-data e) :adl/error)]
        (throw e)))))

;; ---------------------------------------------------------------------
;; serializing
;; ---------------------------------------------------------------------

(defn- escape-string [s]
  (-> s (str/replace "\\" "\\\\") (str/replace "\"" "\\\"")))

(defn code-phrase-str [{:keys [terminology codes]}]
  (str "[" (when terminology (str terminology "::")) (str/join ", " codes) "]"))

(defn- primitive-str [v]
  (cond
    (string? v) (str "\"" (escape-string v) "\"")
    (true? v) "True"
    (false? v) "False"
    (number? v) (str v)
    (and (map? v) (= :code-phrase (:adl/kind v))) (code-phrase-str v)
    (and (map? v) (= :piped-interval (:adl/kind v))) (piped-interval-str v)
    (and (map? v) (= :ellipsis (:adl/kind v))) "..."
    :else (throw (lex/adl-error :adl/unserializable-primitive {:value v}))))

(declare value-str)

(defn- key-str [k]
  (if (map? k) (str "[\"" (escape-string (:adl/bracket-key k)) "\"]") (name k)))

(defn value-body-str [v indent]
  (cond
    (and (map? v) (= :empty (:adl/kind v))) ""

    (and (map? v) (= :object (:adl/kind v)))
    (let [pad (str/join (repeat (inc indent) "\t"))]
      (str/join
       ""
       (for [[k entry-v] (:entries v)]
         (str "\n" pad (key-str k) " = " (value-str entry-v (inc indent))))))

    (and (map? v) (= :list (:adl/kind v)))
    (str/join ", " (map primitive-str (:items v)))

    (and (map? v) (= :code-phrase (:adl/kind v))) (code-phrase-str v)

    :else (primitive-str v)))

(defn value-str
  "Serializes a parsed dADL value back to `<...>` text. `indent` is the
  current tab-depth, used only for the cosmetic indentation of nested
  `:object` entries -- parsing ignores whitespace amount entirely, so this
  choice affects readability, never `parse(serialize(x)) = x`."
  [v indent]
  (let [body (value-body-str v indent)]
    (if (and (map? v) (= :object (:adl/kind v)) (seq (:entries v)))
      (str "<" body "\n" (str/join (repeat indent "\t")) ">")
      (str "<" body ">"))))

;; ---------------------------------------------------------------------
;; flat `name = <value> ...` sequences with no enclosing `<>` -- how a
;; dADL SECTION's body looks directly under `language`/`description`/
;; `ontology`. adl.archetype calls these; exposed here because they share
;; parse-entry's loop-until-it-stops-looking-like-an-entry termination.
;; ---------------------------------------------------------------------

(defn parse-entries-until
  "Parses zero or more `key = <value>`/`[\"k\"] = <value>` entries starting
  at i, stopping (without consuming) at the first position that is not the
  start of another entry -- which is exactly how a dADL section ends: the
  next top-level section keyword (`definition`, `ontology`, ...) or EOF is
  never itself followed by `=`. Returns [entries next-index]."
  [s i]
  (consume-entries s i))

(defn entries-str
  "Serializes a flat entry sequence (as returned by parse-entries-until) at
  the given indent depth -- one `key = <value>` per line, no enclosing
  `<>` -- for a dADL section body."
  [entries indent]
  (let [pad (str/join (repeat indent "\t"))]
    (str/join
     ""
     (for [[k v] entries]
       (str pad (key-str k) " = " (value-str v indent) "\n")))))
