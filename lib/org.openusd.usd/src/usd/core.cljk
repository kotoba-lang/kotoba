(ns usd.core
  "USD (Pixar Universal Scene Description) as data — 'hiccup for scenes'. The USDA (ASCII) form is
   already a declarative, hierarchical scene description, so it maps almost 1:1 onto EDN — a prim
   hierarchy / material / xform is composable data you fork and diff like the rest of the kotoba.* world,
   and it bridges the GPU axis (kotoba.wgsl / kotoba.spirv) to the Pixar/Omniverse axis. `.cljc`.

   USDA is a tree (not infix/line/pair), so it does not use kotoba.expr. A prim is
   `[spec type? name meta? & body]`; body mixes attributes, relationships, and nested prims:
     spec     :def / :over / :class           → def / over / class
     type     a string \"Xform\"/\"Sphere\"/…     (omit for a typeless prim)
     name     keyword/string                  → quoted \"name\"
     meta     a map {:kind \"component\"}        → ( … ) prim metadata
     [:attr \"double\" :radius 2]               → double radius = 2
     [:attr \"color3f[]\" \"primvars:displayColor\" [[1 0 0]]] → color3f[] … = [(1, 0, 0)]
     [:rel :material:binding [:path \"/W/m\"]]  → rel material:binding = </W/m>
   Values follow USDA types: a vector of scalars is a tuple (1, 2, 3); a vector of vectors is an array
   of tuples [(…), …]; [:array …] is a scalar array [1, 2, 3]; [:asset \"p\"] → @p@; [:path \"/p\"] →
   </p>; a keyword/string is a quoted token/string. Top level: (usda {layer-meta} prim…).

   `parse`/`parse-prim` are the inverse direction (ADR-0048 §4): USDA text → this same EDN shape.
   Scope is symmetric with the emitter above — the ASCII-text subset only, no binary .usdc/.usdz, no
   composition arcs beyond a `variantSet` block or a `prepend`-style metadata key. See `parse`'s
   docstring for the exact (small, honestly-documented) set of round-trip asymmetries."
  (:require [kotoba.lang.text :as str]))

(defn- pname [x] (if (keyword? x) (name x) (str x)))   ;; prim/property name (keeps ns colons in strings)

(defn- qstr [s] (str \" (-> (str s) (str/replace "\\" "\\\\") (str/replace "\"" "\\\"")) \"))  ;; escape "/\\

(declare val*)
(defn- val* [v]
  (cond
    (and (vector? v) (= :array (first v))) (str "[" (str/join ", " (map val* (rest v))) "]")
    (and (vector? v) (= :asset (first v))) (str "@" (second v) "@")
    (and (vector? v) (= :path  (first v))) (str "<" (second v) ">")
    (vector? v) (if (every? vector? v)                                   ;; array of tuples
                  (str "[" (str/join ", " (map val* v)) "]")
                  (str "(" (str/join ", " (map val* v)) ")"))            ;; tuple (float3 / color3f / …)
    (string? v)  (qstr v)                    ;; quoted string, internal " / \ escaped
    (keyword? v) (qstr (name v))             ;; token literal
    (nil? v)     "None"                      ;; USDA's literal for an unset/cleared rel or optional value
    :else        (str v)))                    ;; number

(defn attr [[_ typ nm value]] (str typ " " (pname nm) " = " (val* value)))
(defn rel  [[_ nm value]]     (str "rel " (pname nm) " = " (val* value)))

;; composition-arc metadata that USD list-edits — emitted with the idiomatic `prepend`.
(def ^:private list-op #{:references :payload :inherits :specializes :apiSchemas :variantSets})
(defn- meta-line [k v]
  (str (when (list-op k) "prepend ") (pname k) " = " (val* v)))

(defn- indent [s n]
  (let [p (apply str (repeat n " "))] (str p (str/replace s "\n" (str "\n" p)))))

(declare item)
(defn- block [items] (str/join "\n" (map #(indent (item %) 4) items)))

(defn prim
  "Compile one [spec type? name meta? & body] prim form to a USDA prim block. Prim metadata (a map
   after the name) may carry composition arcs — :references :payload :inherits :apiSchemas
   :variantSets — which are emitted as `prepend …`; other keys (e.g. :kind) emit as-is."
  [form]
  (let [[spec & r] form
        typ  (when (string? (first r)) (first r))
        r    (if typ (rest r) r)
        nm   (first r)
        r    (rest r)
        meta (when (map? (first r)) (first r))
        body (if meta (rest r) r)]
    (str (name spec) (when typ (str " " typ)) " \"" (pname nm) "\""
         (when (seq meta)
           (str " (\n" (str/join "\n" (for [[k v] meta] (str "    " (meta-line k v)))) "\n)"))
         (if (seq body) (str "\n{\n" (block body) "\n}") "\n{\n}"))))

(defn- variant-set
  "[:variant-set \"name\" {\"variant\" [body…] …}] → a USD variantSet block."
  [[_ vname variants]]
  (str "variantSet \"" vname "\" = {\n"
       (str/join "\n" (for [[vn vbody] variants]
                        (str "    \"" vn "\" {\n"
                             (str/join "\n" (map #(indent (item %) 8) vbody))
                             "\n    }")))
       "\n}"))

(defn- item [form]
  (case (first form)
    :attr        (attr form)
    :rel         (rel form)
    :variant-set (variant-set form)
    (prim form)))

(defn usda
  "Compile a USDA layer: optional {layer-metadata} then top-level prims."
  [opts & prims]
  (str "#usda 1.0\n"
       (when (seq opts)
         (str "(\n" (str/join "\n" (for [[k v] opts] (str "    " (pname k) " = " (val* v)))) "\n)\n"))
       "\n"
       (str/join "\n\n" (map item prims))
       "\n"))

;; ---------------------------------------------------------------------------------------------
;; Parser — the inverse of the emitter above (ADR-0048 §4). Scope is deliberately the same ASCII-
;; text subset the emitter targets: def/over/class prim blocks (possibly nested), typed attribute
;; and `rel` relationship statements, `variantSet` blocks, comments, and the scalar/tuple/array
;; value grammar `val*` produces. Binary `.usdc`/`.usdz` and composition arcs beyond a simple
;; `variantSet` text block or a `prepend`-style metadata key (references/payload/sublayers/
;; relocates as their own body-level statements) are an explicit non-goal — see "Relationship to
;; ADR-2605261800" in ADR-0048, which reserves that larger effort to `kami-usd`/`kami-usd-native`.
;; Hitting one of those raises a clear ex-info naming this scope rather than silently mis-parsing.
;;
;; This is a hand-rolled recursive-descent parser over a flat token stream (not line-based), so it
;; is tolerant of arbitrary whitespace/newlines/comments between tokens — exactly the tolerance the
;; real USDA grammar allows and DCC-authored files exercise.

(defn- ws-char?   [c] (contains? #{\space \tab \newline \return} c))
(defn- word-char? [c] (boolean (re-matches #"[A-Za-z0-9_:.+\-]" (str c))))

(defn- str->long   [w] #?(:clj (Long/parseLong w) :cljs (js/parseInt w 10)))
(defn- str->double [w] #?(:clj (Double/parseDouble w) :cljs (js/parseFloat w)))

(defn- sym->value
  "Interpret a bare (unquoted) token in *value* position: true/false/None literals, an int, a
   float/double (has a '.' or exponent), else fall back to a keyword (an unquoted enum-like word —
   real USDA scalar values are otherwise always quoted, so this path is rarely hit)."
  [w]
  (cond
    (= w "true")  true
    (= w "false") false
    (= w "None")  nil
    (re-matches #"[+-]?[0-9]+" w) (str->long w)
    (re-matches #"[+-]?(?:[0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)?" w) (str->double w)
    :else (keyword w)))

(defn- read-while [s i pred]
  (let [n (count s)]
    (loop [j i] (if (and (< j n) (pred (nth s j))) (recur (inc j)) j))))

(defn- read-until
  "Scan from i (just past an opening delimiter) to the next `close` char (no escaping — used for
   @asset@ and <path> refs, neither of which nests or escapes in practice). Returns [content j]
   with j the index just past `close`."
  [s i close]
  (let [n (count s)]
    (loop [j i]
      (cond
        (>= j n)             (throw (ex-info (str "USDA parse error: unterminated '" close "' reference") {:index i}))
        (= (nth s j) close)  [(subs s i j) (inc j)]
        :else                (recur (inc j))))))

(defn- read-string-lit
  "Scan a double-quoted string body from i (just past the opening quote), honoring \\\" and \\\\.
   Returns [content j] with j just past the closing quote."
  [s i]
  (let [n (count s)]
    (loop [j i acc []]
      (if (>= j n)
        (throw (ex-info "USDA parse error: unterminated string literal" {:index i}))
        (let [c (nth s j)]
          (cond
            (= c \\)  (recur (+ j 2) (conj acc (nth s (inc j))))
            (= c \")  [(apply str acc) (inc j)]
            :else     (recur (inc j) (conj acc c))))))))

(defn- tokenize
  "Lex USDA text into a vector of [kind value] tokens: :sym (bare word, incl. a `word[]` array-type
   suffix glued on with no space), :str (quoted string), :asset (@...@), :path (<...>), :punct (one
   of `{ } ( ) [ ] =`). Comments (# to end of line — this also swallows the `#usda 1.0` header line
   itself, which carries no information `usda`/`prim` need back) and commas (pure separators in this
   grammar) are dropped."
  [s]
  (let [n (count s)]
    (loop [i 0 out (transient [])]
      (if (>= i n)
        (persistent! out)
        (let [c (nth s i)]
          (cond
            (ws-char? c) (recur (inc i) out)
            (= c \,)     (recur (inc i) out)
            (= c \#)     (recur (read-while s i #(not= % \newline)) out)
            (= c \")     (let [[v j] (read-string-lit s (inc i))] (recur j (conj! out [:str v])))
            (= c \@)     (let [[v j] (read-until s (inc i) \@)] (recur j (conj! out [:asset v])))
            (= c \<)     (let [[v j] (read-until s (inc i) \>)] (recur j (conj! out [:path v])))
            (contains? #{\{ \} \( \) \[ \] \=} c) (recur (inc i) (conj! out [:punct (str c)]))
            (word-char? c)
            (let [j (read-while s i word-char?)]
              (if (and (< (inc j) n) (= (nth s j) \[) (= (nth s (inc j)) \]))
                (recur (+ j 2) (conj! out [:sym (str (subs s i j) "[]")]))
                (recur j (conj! out [:sym (subs s i j)]))))
            :else (recur (inc i) out)))))))     ;; skip any other stray char defensively

(def ^:private qualifier-kw  #{"custom" "uniform" "varying"})
(def ^:private list-edit-kw  #{"prepend" "append" "add" "delete" "reorder"})
(def ^:private unsupported-note
  " (ADR-0048 scope: this parser handles def/over/class prims, typed attributes, `rel`
   relationships, variantSet blocks, comments, and scalar/tuple/array values — binary .usdc/.usdz
   and composition arcs beyond that, e.g. references/payload/sublayers as body-level statements,
   are out of scope; see ADR-0048 'Relationship to ADR-2605261800'.)")

(declare parse-value* parse-seq* parse-item* parse-prim* parse-body*
         parse-variant-set* parse-rel* parse-attr* parse-meta*)

(defn- tok  [toks i] (get toks i))
(defn- tk=  [toks i kind v] (let [[k v'] (tok toks i)] (and (= k kind) (= v' v))))

(defn- expect [toks i kind v]
  (if (tk= toks i kind v)
    (inc i)
    (throw (ex-info (str "USDA parse error: expected " (pr-str v) ", got " (pr-str (tok toks i)))
                     {:index i :token (tok toks i)}))))

(defn- skip-balanced
  "Skip a ( … ) group starting at index i (a '(' token), honoring nesting. Used to tolerate
   attribute-level metadata (e.g. `(interpolation = \"vertex\")`) this library has no EDN slot for
   yet — dropped, not crashed on. Returns the index just past the matching ')'."
  [toks i]
  (loop [j (inc i) depth 1]
    (cond
      (>= j (count toks))      (throw (ex-info "USDA parse error: unbalanced '('" {:index i}))
      (tk= toks j :punct "(")  (recur (inc j) (inc depth))
      (tk= toks j :punct ")")  (if (= depth 1) (inc j) (recur (inc j) (dec depth)))
      :else                    (recur (inc j) depth))))

(defn- parse-seq*
  "Read value* elements up to (and past) the `close` punctuation token."
  [toks i close]
  (loop [j i acc []]
    (if (tk= toks j :punct close)
      [acc (inc j)]
      (let [[v j'] (parse-value* toks j)]
        (recur j' (conj acc v))))))

(defn- parse-value*
  "Inverse of `val*`: (…) → a tuple (bare vector); [x, y] → an array — bare vector-of-vectors when
   every element is itself a vector (array of tuples / assets / paths, matching how `val*` decides
   tuple-vs-array on the way out), else `[:array e1 e2 …]`; @p@ → [:asset p]; <p> → [:path p]; a
   quoted string → a Clojure string; true/false/None → boolean/nil; a bare number → int or double."
  [toks i]
  (let [[k v] (tok toks i)]
    (case k
      :str   [v (inc i)]
      :asset [[:asset v] (inc i)]
      :path  [[:path v] (inc i)]
      :sym   [(sym->value v) (inc i)]
      :punct (case v
               "(" (parse-seq* toks (inc i) ")")
               "[" (let [[elems j] (parse-seq* toks (inc i) "]")]
                     [(if (or (empty? elems) (every? vector? elems)) (vec elems) (into [:array] elems))
                      j])
               (throw (ex-info (str "USDA parse error: unexpected token in value position: " (pr-str [k v])
                                     unsupported-note)
                                {:index i})))
      (throw (ex-info "USDA parse error: unexpected end of input while reading a value" {:index i})))))

(defn- parse-meta*
  "Parse a `( key = value  prepend key2 = value2  … )` metadata block. `i` points just past the
   opening '('. A leading list-edit keyword (prepend/append/add/delete/reorder) on any entry is
   recognized and dropped — this library's own emitter always re-derives `prepend` from the fixed
   `list-op` key set on the way out, so dropping it here is lossless for keys this repo emits, and
   an honest, documented gap for the other four operators (see README 'Parser: known gaps')."
  [toks i]
  (loop [j i m {}]
    (if (tk= toks j :punct ")")
      [m (inc j)]
      (let [j          (if (and (= :sym (first (tok toks j))) (list-edit-kw (second (tok toks j))))
                          (inc j) j)
            [kk kv]    (tok toks j)
            _          (when-not (#{:sym :str} kk)
                         (throw (ex-info (str "USDA parse error: expected a metadata key, got " (pr-str (tok toks j)))
                                          {:index j})))
            j          (expect toks (inc j) :punct "=")
            [val j]    (parse-value* toks j)]
        (recur j (assoc m (keyword kv) val))))))

(defn- parse-attr*
  "`i` points at the attribute's type token; `quals` are any uniform/custom/varying qualifier words
   already consumed by the caller — folded back into the returned type string (e.g. \"uniform
   token[]\") so they round-trip through `attr` as plain text with no new EDN slot needed."
  [toks i quals]
  (let [[tkind type-word] (tok toks i)
        _        (when-not (= tkind :sym)
                   (throw (ex-info (str "USDA parse error: expected an attribute type, got " (pr-str (tok toks i))
                                         unsupported-note)
                                    {:index i})))
        typ      (if (seq quals) (str (str/join " " quals) " " type-word) type-word)
        i        (inc i)
        [nk nv]  (tok toks i)
        _        (when-not (#{:sym :str} nk)
                   (throw (ex-info (str "USDA parse error: expected an attribute name, got " (pr-str (tok toks i))
                                         unsupported-note)
                                    {:index i})))
        i        (expect toks (inc i) :punct "=")
        [val i]  (parse-value* toks i)
        i        (if (tk= toks i :punct "(") (skip-balanced toks i) i)]   ;; drop attr-level metadata
    [[:attr typ (keyword nv) val] i]))

(defn- parse-rel*
  "`i` points just past the `rel` keyword (any qualifier already consumed by the caller)."
  [toks i]
  (let [[nk nv] (tok toks i)
        _       (when-not (#{:sym :str} nk)
                  (throw (ex-info (str "USDA parse error: expected a relationship name, got " (pr-str (tok toks i)))
                                   {:index i})))
        i       (expect toks (inc i) :punct "=")
        [val i] (parse-value* toks i)]
    [[:rel (keyword nv) val] i]))

(defn- parse-variant-set*
  "`i` points just past the `variantSet` keyword."
  [toks i]
  (let [[nk vname] (tok toks i)
        _          (when-not (= nk :str)
                     (throw (ex-info "USDA parse error: variantSet name must be a quoted string" {:index i})))
        i          (expect toks (inc i) :punct "=")
        i          (expect toks i :punct "{")
        [variants i]
        (loop [j i m {}]
          (if (tk= toks j :punct "}")
            [m (inc j)]
            (let [[vk vn] (tok toks j)
                  _       (when-not (= vk :str)
                            (throw (ex-info "USDA parse error: variant name must be a quoted string" {:index j})))
                  j       (expect toks (inc j) :punct "{")
                  [body j] (parse-body* toks j)]
              (recur j (assoc m vn body)))))]
    [[:variant-set vname variants] i]))

(defn- parse-body*
  "Read [:attr …]/[:rel …]/[:variant-set …]/nested-prim items up to (and past) a closing '}'."
  [toks i]
  (loop [j i acc []]
    (if (tk= toks j :punct "}")
      [acc (inc j)]
      (let [[it j'] (parse-item* toks j)]
        (recur j' (conj acc it))))))

(defn- parse-prim*
  "`i` points just past the def/over/class keyword; `spec-kw` is that keyword (:def/:over/:class)."
  [toks i spec-kw]
  (let [[k1 v1]   (tok toks i)
        has-type? (= k1 :sym)
        typ       (when has-type? v1)
        i         (if has-type? (inc i) i)
        [nk nv]   (tok toks i)
        _         (when-not (= nk :str)
                    (throw (ex-info "USDA parse error: prim name must be a quoted string" {:index i})))
        i         (inc i)
        [meta i]  (if (tk= toks i :punct "(") (parse-meta* toks (inc i)) [nil i])
        i         (expect toks i :punct "{")
        [body i]  (parse-body* toks i)]
    [(into (if typ [spec-kw typ (keyword nv)] [spec-kw (keyword nv)])
           (concat (when (seq meta) [meta]) body))
     i]))

(defn- parse-item* [toks i]
  (let [[k v] (tok toks i)]
    (cond
      (nil? k)
      (throw (ex-info "USDA parse error: unexpected end of input" {:index i}))

      (and (= k :sym) (#{"def" "over" "class"} v))
      (parse-prim* toks (inc i) (keyword v))

      (and (= k :sym) (= v "variantSet"))
      (parse-variant-set* toks (inc i))

      (and (= k :sym) (= v "rel"))
      (parse-rel* toks (inc i))

      (and (= k :sym) (or (qualifier-kw v) (list-edit-kw v)))
      (loop [j i quals []]
        (let [[jk jv] (tok toks j)]
          (if (and (= jk :sym) (or (qualifier-kw jv) (list-edit-kw jv)))
            (recur (inc j) (if (qualifier-kw jv) (conj quals jv) quals))
            (cond
              (and (= jk :sym) (= jv "rel"))         (parse-rel* toks (inc j))
              (and (= jk :sym) (= jv "variantSet"))  (parse-variant-set* toks (inc j))
              (= jk :sym)                            (parse-attr* toks j quals)
              :else (throw (ex-info (str "USDA parse error: expected rel/variantSet/attribute after "
                                          "a qualifier, got " (pr-str (tok toks j)) unsupported-note)
                                     {:index j}))))))

      (= k :sym)
      (parse-attr* toks i [])

      :else
      (throw (ex-info (str "USDA parse error: unsupported construct at token " i ": " (pr-str [k v])
                            unsupported-note)
                       {:index i :token [k v]})))))

(defn parse-prim
  "Parse a single `def/over/class Type? \"name\" (meta)? { body }` USDA block — the text `prim`
   produces — back into the `[spec type? name meta? & body]` vector `prim` accepts. For a whole
   layer (`#usda` header + optional layer metadata + one or more top-level prims), use `parse`."
  [s]
  (let [toks  (tokenize s)
        [k v] (tok toks 0)]
    (when-not (and (= k :sym) (#{"def" "over" "class"} v))
      (throw (ex-info "USDA parse error: expected a def/over/class prim" {:got (tok toks 0)})))
    (first (parse-prim* toks 1 (keyword v)))))

(defn parse
  "Parse a full USDA layer — the text `usda` produces — into `{:opts {...} :prims [...]}`, the
   shape consumed by `(apply usda opts prims)`. Tolerant of comments (#…) and whitespace/newlines
   anywhere between tokens (it is a token-stream parser, not line-based).

   Known, honestly-documented round-trip asymmetries (none of these lose structure — they collapse
   a distinction USDA text itself does not carry):
     - USDA has no lexical difference between a token/keyword and a plain string (`val*` renders
       both as a quoted string), so every plain scalar *value* comes back as a Clojure string, never
       a keyword — e.g. round-tripping `{:upAxis :Y}` yields `{:upAxis \"Y\"}`. Prim/attribute/
       relationship *names*, and asset (`[:asset ..]`)/path (`[:path ..]`)/array (`[:array ..]`)
       tagged values, are unambiguous and round-trip exactly.
     - `uniform`/`custom`/`varying` attribute qualifiers are folded into the returned type string
       (\"uniform token[]\") rather than a separate field.
     - list-edit operators other than `prepend` (`add`/`delete`/`append`/`reorder`) are recognized
       and discarded, not reproduced (this library's own emitter only ever produces `prepend`).
     - attribute-level metadata blocks (e.g. `(interpolation = \"vertex\")`) are recognized and
       skipped — there is no EDN slot for per-attribute metadata today.
   Out of scope entirely (raises a clear `ex-info` naming ADR-0048 rather than mis-parsing):
   binary `.usdc`/`.usdz`, `timeSamples`, and composition arcs as body-level statements (references/
   payload/sublayers/relocates) — `variantSet` blocks and `prepend`-metadata-key composition arcs
   (as already emitted by `prim`/`usda`) are supported."
  [s]
  (when-not (str/includes? (subs s 0 (min 64 (count s))) "#usda")
    (throw (ex-info "USDA parse error: input does not start with a '#usda' header" {})))
  (let [toks    (tokenize s)
        [opts i] (if (tk= toks 0 :punct "(") (parse-meta* toks 1) [{} 0])
        n       (count toks)]
    (loop [j i prims []]
      (if (>= j n)
        {:opts opts :prims prims}
        (let [[it j'] (parse-item* toks j)]
          (recur j' (conj prims it)))))))
