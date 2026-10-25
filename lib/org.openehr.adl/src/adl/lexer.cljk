(ns adl.lexer
  "Shared character-level lexical helpers for the ADL 1.4 grammar: cADL
  (constraint ADL, the `definition` section) and dADL (data ADL, the
  `language`/`description`/`ontology`/`invariant`/`revision_history`/
  `annotations` sections) share one lexical layer -- comments, whitespace,
  identifiers, quoted strings, numbers -- and differ only in what they build
  out of it.

  This is a direct character-index scanner over the whole document, not a
  separate tokenizer pass. ADL's grammar is context-sensitive exactly where
  it matters most: an object's `{...}` body is a list of ATTRIBUTES, but an
  attribute's `{...}` body is a list of OBJECTS-or-primitive-alternatives,
  and which one applies depends on nesting DEPTH, not on any bounded
  lookahead over a token stream. A pre-cut token vector would just make the
  caller reconstruct the source-position bookkeeping a plain string index
  already carries for free -- so this mirrors kotoba-lang/xml's xml.parse
  and this workspace's other wire-format codecs (org-dnp3, org-modbus):
  every function here is `[s i] -> [value next-index]` (or throws
  `ex-info` with an `:adl/error` key, which every public entry point in
  adl.dadl/adl.cadl/adl.archetype/adl.path catches and turns into a named
  `[:error ...]` result -- see those namespaces for why `throw` never
  escapes a public function).

  Char classification here uses `re-matches` against a length-1 string
  rather than `(int c)` range comparisons or `Character/isLetter`-style
  interop: ADL identifiers are pure ASCII, and per this workspace's own
  incident history, `(int c)` on a character silently returns 0 under
  ClojureScript (a JVM `char`'s numeric coercion does not carry over) --
  the exact class of bug this library's dual-runtime verification exists
  to catch. A regex against a 1-character string is slower per-char but
  behaves identically on both runtimes, and these documents are a few
  hundred lines, not a hot loop."
  (:require [kotoba.lang.text :as str]))

(defn adl-error
  "Builds the ex-info this namespace's parsers throw on malformed input.
  Every PUBLIC parse entry point (adl.dadl/parse-value, adl.cadl/parse-object,
  adl.archetype/parse, adl.path/parse) wraps its body in a catch that turns
  this back into a plain `[:error kw detail]` return value -- callers of a
  parser never see an exception, only a tagged result, per this workspace's
  \"named errors, not throw\" rule. `throw`/`catch` stays purely an internal
  control-flow shortcut between here and that one boundary."
  [kw detail]
  (ex-info (str "adl/" (name kw)) (assoc detail :adl/error kw)))

(defn adl-error? [e] (and (map? e) (contains? e :adl/error)))

(defn- ch [s i] (when (< i (count s)) (subs s i (inc i))))

(defn char-at
  "The single character at i as a length-1 string, or nil past the end.
  Exposed (unlike the private `ch` above) so adl.dadl/adl.cadl/adl.path can
  classify `s[j]` after their own `skip-ws-and-comments` without each
  re-deriving the same `(subs s j (min (count s) (inc j)))` bounds-check."
  [s i]
  (ch s i))

(defn ws-ch? [c] (boolean (and c (re-matches #"[ \t\n\r]" c))))
(defn letter-ch? [c] (boolean (and c (re-matches #"[A-Za-z]" c))))
(defn digit-ch? [c] (boolean (and c (re-matches #"[0-9]" c))))
(defn ident-start-ch? [c] (boolean (and c (re-matches #"[A-Za-z_]" c))))
(defn ident-cont-ch? [c] (boolean (and c (re-matches #"[A-Za-z0-9_]" c))))

(defn skip-ws
  "Index after any run of plain whitespace at i (no comments)."
  [s i]
  (let [n (count s)]
    (loop [i i] (if (and (< i n) (ws-ch? (ch s i))) (recur (inc i)) i))))

(defn skip-to-eol [s i]
  (let [n (count s)]
    (loop [i i] (if (and (< i n) (not= "\n" (ch s i))) (recur (inc i)) i))))

(defn skip-ws-and-comments
  "Index after any run of whitespace and `-- to end of line` comments.
  ADL/dADL has no block-comment syntax -- only this Eiffel-style line form."
  [s i]
  (let [n (count s)]
    (loop [i (skip-ws s i)]
      (if (and (< (inc i) n) (= "-" (ch s i)) (= "-" (ch s (inc i))))
        (recur (skip-ws s (skip-to-eol s i)))
        i))))

(defn trailing-comment
  "If, skipping only plain whitespace (not crossing a comment we'd then
  re-consume) from i there is a `-- text` run before the next newline,
  returns [trimmed-text index-after-eol]; else [nil i].

  Used right where an object or attribute's opening `{` has just been
  consumed, to capture the archetype author's inline label, e.g.
  `OBSERVATION[at0000] matches {\\t-- Demonstration` -- that label is
  archetype content (round-tripped back out on serialize), not a comment
  to discard, which is why it is pulled out explicitly here instead of via
  `skip-ws-and-comments`."
  [s i]
  (let [j (skip-ws s i)
        n (count s)]
    (if (and (< (inc j) n) (= "-" (ch s j)) (= "-" (ch s (inc j))))
      (let [text-start (+ j 2)
            eol (skip-to-eol s text-start)]
        [(str/trim (subs s text-start eol)) eol])
      [nil i])))

(defn peek-lit?
  "True when literal `lit` occurs at s[i] (after skipping ws+comments)."
  [s i lit]
  (let [j (skip-ws-and-comments s i)
        end (+ j (count lit))]
    (and (<= end (count s)) (= lit (subs s j end)))))

(defn expect
  "Skips ws+comments, then requires literal `lit` at the cursor and returns
  the index right after it. Throws `:adl/expected-literal` (see adl-error)
  otherwise -- every recursive-descent call in this library is written
  unconditionally against a successful `expect`, with the single outer
  `try/catch` at each namespace's public entry point turning a throw here
  into that call's `[:error :adl/expected-literal {...}]`."
  [s i lit]
  (let [j (skip-ws-and-comments s i)
        end (+ j (count lit))]
    (if (and (<= end (count s)) (= lit (subs s j end)))
      end
      (throw (adl-error :adl/expected-literal
                         {:expected lit :at j
                          :context (subs s j (min (count s) (+ j 40)))})))))

(defn read-ident
  "Reads `[A-Za-z_][A-Za-z0-9_]*` at i (after ws+comments). Returns
  [ident-string next-index]. Throws `:adl/expected-identifier` on a
  non-identifier start."
  [s i]
  (let [j (skip-ws-and-comments s i)
        n (count s)]
    (when-not (ident-start-ch? (ch s j))
      (throw (adl-error :adl/expected-identifier
                         {:at j :context (subs s j (min n (+ j 40)))})))
    (loop [k (inc j)]
      (if (and (< k n) (ident-cont-ch? (ch s k)))
        (recur (inc k))
        [(subs s j k) k]))))

(defn code-start-ch? [c] (boolean (and c (re-matches #"[A-Za-z0-9_]" c))))
(defn code-cont-ch? [c] (boolean (and c (re-matches #"[A-Za-z0-9_\-]" c))))

(defn read-code-token
  "Reads a terminology-id/code token: `[A-Za-z0-9_][A-Za-z0-9_-]*`, e.g.
  `ISO_639-1`, `openehr`, `local`, `at0007`, or a bare numeric terminology
  code like openEHR's own `125` (`[openehr::125]`, a DV_QUANTITY property
  id). Distinct from read-ident (attribute/type names) two ways: terminology
  ids in real archetypes contain hyphens (ISO 639's own designation does)
  where snake_case attribute names never do, and codes may start with a
  digit where an identifier never can -- widening read-ident itself would
  let both leak into contexts where ADL's actual grammar doesn't allow
  them."
  [s i]
  (let [j (skip-ws-and-comments s i)
        n (count s)]
    (when-not (code-start-ch? (ch s j))
      (throw (adl-error :adl/expected-identifier
                         {:at j :context (subs s j (min n (+ j 40)))})))
    (loop [k (inc j)]
      (if (and (< k n) (code-cont-ch? (ch s k)))
        (recur (inc k))
        [(subs s j k) k]))))

(defn read-dotted-code
  "read-code-token plus trailing `.segment` runs (node-id specialisation,
  e.g. `at0001.1`)."
  [s i]
  (let [[first-seg j] (read-code-token s i)]
    (loop [acc first-seg k j]
      (if (and (< k (count s)) (= "." (ch s k))
               (code-start-ch? (ch s (inc k))))
        (let [[seg k2] (read-code-token s (inc k))]
          (recur (str acc "." seg) k2))
        [acc k]))))

(defn read-dotted-ident
  "Like read-ident but also consumes trailing `.segment` runs sharing the
  same char class, e.g. archetype node-id specialisation `at0001.1` or a
  reference-model attribute path segment `archetype_id/value` (the `/` is
  handled by the caller; this only owns the `.`-joined tail)."
  [s i]
  (let [[first-seg j] (read-ident s i)]
    (loop [acc first-seg k j]
      (if (and (< k (count s)) (= "." (ch s k))
               (ident-start-ch? (ch s (inc k))))
        (let [[seg k2] (read-ident s (inc k))]
          (recur (str acc "." seg) k2))
        [acc k]))))

(defn read-string-literal
  "Reads a `\"...\"` dADL string at i (after ws+comments), honoring `\\\"`
  and `\\\\` escapes and passing every other character -- including a
  literal embedded newline, which real archetypes contain (a multi-line
  `other_details` value in a published CKM archetype is exactly this) --
  through unchanged. Returns [string next-index-after-closing-quote]."
  [s i]
  (let [j (skip-ws-and-comments s i)
        n (count s)]
    (when-not (= "\"" (ch s j))
      (throw (adl-error :adl/expected-string {:at j})))
    (loop [k (inc j) out (transient [])]
      (cond
        (>= k n)
        (throw (adl-error :adl/unterminated-string {:at j}))

        (and (= "\\" (ch s k)) (< (inc k) n))
        (recur (+ k 2) (conj! out (ch s (inc k))))

        (= "\"" (ch s k))
        [(apply str (persistent! out)) (inc k)]

        :else
        (recur (inc k) (conj! out (ch s k)))))))

(defn read-number
  "Reads an optionally-signed integer or decimal at i (after ws+comments).
  Returns [clojure-number next-index] -- a Long/long for an integer token,
  a Double/double for one with a `.`. Parsing (not just lexing) happens
  here because both call sites (dADL primitive values and cADL interval
  bounds) want the numeric value, never the source text."
  [s i]
  (let [j (skip-ws-and-comments s i)
        n (count s)
        neg? (= "-" (ch s j))
        j2 (if neg? (inc j) j)]
    (when-not (digit-ch? (ch s j2))
      (throw (adl-error :adl/expected-number {:at j})))
    (let [int-end (loop [k j2] (if (and (< k n) (digit-ch? (ch s k))) (recur (inc k)) k))
          frac? (and (= "." (ch s int-end)) (digit-ch? (ch s (inc int-end))))
          end (if frac?
                (loop [k (inc int-end)] (if (and (< k n) (digit-ch? (ch s k))) (recur (inc k)) k))
                int-end)
          text (subs s j end)]
      [(if frac?
         #?(:clj (Double/parseDouble text) :cljs (js/parseFloat text))
         #?(:clj (Long/parseLong text) :cljs (js/parseInt text 10)))
       end])))
