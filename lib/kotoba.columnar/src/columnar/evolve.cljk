(ns columnar.evolve
  "Schema evolution: reading N files that do not agree about their columns as
  one table.

  A lake's table is a set of files written at different times. A column gets
  added, a writer changes a width, an old file predates a field entirely — and
  a query over the table has to answer as though there were one schema. This
  namespace decides what that schema is, and presents a source as though it
  had it.

  ## The type keyword is format-specific, and that is why this is here

  Parquet calls a string column `:byte-array`; Arrow calls it `:utf8`. Both
  readers decode to Clojure strings, so the **values** already agree and only
  the labels do not. A table spanning both formats therefore cannot compare
  types by keyword equality, and every consumer that tried would invent its
  own mapping.

  So `canonical` collapses the format names onto one lattice, and it lives
  beside `IColumnSource` for the same reason `columnar.bytes` does: it is the
  vocabulary the seam is spoken in, not a property of either format.

  ## Widening only, and refusals by name

  Two files agree if their columns canonicalise to the same class. Within a
  class the wider concrete type wins — `int64` over `int32`, `double` over
  `float` — and since both readers already produce Clojure numbers, that
  widening is a **relabelling and not a conversion**. Equal widths are ties
  between *aliases* (`:utf8` and `:byte-array` are the same class and the same
  size), and a tie goes to the first schema given: deterministic is the
  property that matters, and there is no principled winner between two names
  for one thing. Across classes there is
  no safe answer: `int` and `float` differ past 2^53, `string` and `int` do
  not compare, and guessing would put wrong values into a query that looks
  like it worked. Those are refused and the refusal names both types.

  `:null` unifies with anything. A column that is entirely null in one file
  makes no claim about its type, so it must not veto the type the other files
  agree on.

  ## An absent column is all-null, and that PRUNES

  The useful consequence. A file predating a column reports it as `{:rows n
  :nulls n}` — and `null_count == rows` is a proof, the one thing
  `columnar.stats` can rule a chunk out on without bounds. So a predicate on a
  column that a file does not have skips that file's chunks outright rather
  than reading them to discover nothing matches.

  ## What this does NOT do

  **Rename.** Resolution here is by name, and by name a rename is
  indistinguishable from a drop plus an add — the old column vanishes and a
  new one appears, which is exactly what this namespace will report. Telling
  them apart requires a stable identity per column that survives the rename,
  which no file we write carries today. Supporting rename means putting field
  IDs in the manifest and resolving through them, and pretending otherwise
  would silently turn a rename into data loss."
  (:require [columnar.source :as src]
            [columnar.vector :as vec]))

(def canonical
  "Format-specific type keywords onto one lattice.

  A keyword absent from this map canonicalises to itself, so an unknown type
  unifies with an identical unknown type and refuses everything else — which
  is the safe default for a type this namespace has never heard of."
  {:int8 :int :int16 :int :int32 :int :int64 :int
   :uint8 :int :uint16 :int :uint32 :int :uint64 :int
   :half-float :float :float :float :double :float
   :utf8 :string :large-utf8 :string :byte-array :string :string :string
   :bool :bool :boolean :bool
   :binary :binary :large-binary :binary
   :null :null})

(defn class-of [t] (get canonical t t))

(def ^:private width
  "Rank within a class. The wider concrete type wins a unification, so a table
  spanning an int32 file and an int64 file reports int64 — which is the only
  one of the two that can describe every value in the table."
  {:int8 1 :uint8 1 :int16 2 :uint16 2 :int32 3 :uint32 3 :int64 4 :uint64 4
   :half-float 1 :float 2 :double 3
   :byte-array 1 :utf8 1 :string 1 :large-utf8 2
   :binary 1 :large-binary 2
   :bool 1 :boolean 1})

(defn unify-type
  "The type that describes both `a` and `b`, or a throw naming the conflict."
  [column a b]
  (cond
    (= a b) a
    (= :null (class-of a)) b
    (= :null (class-of b)) a
    (not= (class-of a) (class-of b))
    (throw (ex-info (str "column " (pr-str column) " has incompatible types across files: "
                         (pr-str a) " and " (pr-str b))
                    {:type :columnar/incompatible-types
                     :column column :types [a b]
                     :classes [(class-of a) (class-of b)]}))
    :else (if (>= (get width a 0) (get width b 0)) a b)))

(defn unify
  "One schema from many. `schemas` is a seq of `{column type}` maps.

  Column order is first appearance across `schemas` in the order given, for
  the reason `columnar.group` orders its output that way: a map's seq order is
  unspecified and differs between runtimes, and a table schema that changes
  order between the JVM and ClojureScript would make every plan built from it
  runtime-dependent."
  [schemas]
  (let [order (reduce (fn [o s] (reduce (fn [o c] (if (some #{c} o) o (conj o c)))
                                        o (keys s)))
                      [] schemas)]
    {:columns order
     :types (reduce (fn [acc s]
                      (reduce (fn [acc [c t]]
                                (assoc acc c (if (contains? acc c)
                                               (unify-type c (get acc c) t)
                                               t)))
                              acc s))
                    {} schemas)}))

(defn missing-column
  "An all-null column of `n` rows.

  `:valid` is all false, so `columnar.stats/from-column` reports
  `nulls == rows` and every operator treats the values as absent rather than
  as some sentinel."
  [type n]
  (vec/of type (clojure.core/vec (repeat n nil)) (clojure.core/vec (repeat n false))))

(defn reconcile
  "`source` presented as though it had `schema` — `{:columns [..] :types {..}}`.

  Columns the source does not have are synthesised as all-null. Columns it has
  that the schema does not are hidden: the schema is the allowlist, and a
  table must not grow a column because one member happens to carry it.

  Statistics pass through untouched for columns that exist, and a synthesised
  column reports `{:rows n :nulls n}` — never bounds. Both halves matter: the
  first is what keeps real pruning working, the second is what makes an absent
  column prunable without inventing a claim about values that are not there."
  [source {:keys [columns types] :as schema}]
  (let [have (set (src/-schema source))
        wanted (clojure.core/vec columns)]
    (doseq [c wanted]
      (when-not (contains? types c)
        (throw (ex-info (str "schema names column " (pr-str c) " with no type")
                        {:type :columnar/schema-incomplete :column c :schema schema}))))
    (reify src/IColumnSource
      (-schema [_] wanted)
      (-chunk-count [_] (src/-chunk-count source))
      (-chunk-rows [_ chunk] (src/-chunk-rows source chunk))
      (-chunk-stats [_ chunk column]
        (if (contains? have column)
          (src/-chunk-stats source chunk column)
          (let [n (src/-chunk-rows source chunk)]
            ;; No :min/:max — the column is not there, so there is nothing to
            ;; claim. `nulls == rows` is the proof that DOES hold, and it is
            ;; the one `columnar.stats` can prune on.
            {:rows n :nulls n})))
      (-read-column [_ chunk column]
        (if (contains? have column)
          ;; Relabelled to the unified type. Both readers already produce
          ;; Clojure values, so widening within a class is a label change and
          ;; not a conversion -- and doing it here keeps every column of the
          ;; table reporting one type.
          (assoc (src/-read-column source chunk column) :type (get types column))
          (missing-column (get types column) (src/-chunk-rows source chunk)))))))

(defn schema-of
  "`{column type}` for a source, from its own schema and one chunk's columns.

  Reads the columns, so it is the expensive way to learn a schema and exists
  for callers that have no manifest. A lake records member schemas instead."
  [source]
  (if (zero? (src/-chunk-count source))
    {}
    (into {} (map (fn [c] [c (:type (src/-read-column source 0 c))]))
          (src/-schema source))))
