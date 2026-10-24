(ns kotobase.lake.tabular
  "In-place analytic query over a raw tabular file, as an `IPatternSource`.

  This is the read side the lake was missing. `kotobase.lake.reader` decodes
  an object by reading all of it and returning all of its rows; that is right
  for a 4 KB JSON blob and useless for a 40 GB Parquet file. Here the object
  stays where it is and an engine that already knows how to read it answers
  one pattern at a time.

  ## Why a triple pattern is a good fit for a columnar file

  It is a projection and a filter, which is what these formats are built to
  serve:

      [?row \"price\" nil]   -> read the `price` column and nothing else
      [?row \"price\" 42]    -> and let the engine skip row groups whose
                              min/max cannot contain 42
      [nil nil nil]        -> read everything, honestly expensively

  So the pushdown is not something bolted on: the pattern already carries
  exactly the two things the file's index can act on.

  ## This namespace does not speak SQL

  `ITabularEngine` takes a **request** -- which columns, which row, which
  equality filters -- and the engine turns that into whatever dialect it
  speaks. Three things fall out of that boundary:

  - **No value from a query is ever concatenated into a statement here.**
    Column names are checked against `-columns` before they leave, and values
    travel as data. A pattern is attacker-controlled in a multi-tenant
    deployment; a source that built `WHERE \" p \" = '\" o \"'` would be a
    query-language-shaped injection.
  - **The pushdown is testable without an engine.** A fake that records
    requests proves the column was projected and the filter was pushed, which
    an answer-only test cannot: a source that reads every row and filters in
    memory returns identical answers. That is the same hazard
    `kotobase-storage` found in its sequential CAS tests -- correct answers
    from a mechanism that is not doing the work.
  - Dialect differences (how a row is numbered, how a file is named) stay in
    the engine.

  ## Two shapes, because a table row is not a set of facts

  | shape | row means | can express |
  |---|---|---|
  | `wide-source` | one subject, one column per predicate | at most ONE value per (subject, predicate) |
  | `long-source` | one datom, in `s`/`p`/`o` columns | anything |

  A normal analytics file is wide, and **wide cannot hold a multi-valued
  attribute** -- there is no cell for `alice likes tea` *and*
  `alice likes coffee`. That is a property of tables, not a gap here, and it
  is why `datom.source.conformance` (whose corpus contains exactly that pair)
  is run against `long-source` and cannot be run against `wide-source`.
  `wide-source` gets its own suite over a corpus a table can actually hold."
  (:require [kotoba.lang.text :as str]
            [datom.source :as source]))

(defprotocol ITabularEngine
  (-columns [engine]
    "Ordered column names of this relation, as strings. Read once at
    construction: it is the allowlist that keeps a pattern's predicate from
    reaching the engine as an identifier.")
  (-select [engine request]
    "`request` is `{:columns [..] :row n-or-nil :filters [[col value] ..]
    :predicates [[op col v] ..]}`.

    Returns a seq of maps keyed by column name (string), each carrying
    `:kotobase.lake.tabular/row` — the row's stable number.

    `:columns` nil means every column. `:filters` are equality predicates and
    `:predicates` are range/comparison ops (`:<` `:>` `:<=` `:>=` `:=`) the
    engine SHOULD push down so stats/byte-range can prune. Returning more
    rows than asked is a performance bug, not a correctness one, because
    this namespace re-checks. Returning FEWER is a correctness bug and the
    conformance suite catches it."))

(def ^:private row-key ::row)

;; ── subject encoding ────────────────────────────────────────────────────────

(defn row-subject
  "`<prefix>` + row number. The subject a wide row gets."
  [prefix n]
  (str prefix n))

(defn- parse-row
  "Row number from a subject, or nil when the subject is not ours.

  nil matters more than it looks: `merged` hands every pattern to every
  source, so a source that cannot recognise a foreign subject would answer it
  with a full scan. Returning nil here makes a foreign subject cost nothing."
  [prefix s]
  (when (and (string? s) (str/starts-with? s prefix))
    (let [tail (subs s (count prefix))]
      ;; A regex rather than char codes. `(int \1)` is the code point on the
      ;; JVM, but seq-ing a string in ClojureScript yields one-character
      ;; STRINGS and `(int "1")` is 0 -- so a char-code digit test says "not a
      ;; digit" for every digit, and every subject looks foreign. The JVM
      ;; suite passed while the cljs one returned nothing. Same defect this
      ;; repo already fixed once in `sniff/ascii-bytes`; it recurs because the
      ;; obvious spelling is wrong on exactly one of the two runtimes.
      (when (re-matches #"\d+" tail)
        (#?(:clj Long/parseLong :cljs js/parseInt) tail)))))

;; ── wide ────────────────────────────────────────────────────────────────────

(defrecord ^:no-doc WideSource [engine columns prefix]
  source/IPatternSource
  (-scan [_ [s p o]]
    (let [row (when (some? s) (parse-row prefix s))
          cols (set columns)]
      (cond
        ;; A subject that is not ours, or a predicate this file has no column
        ;; for. Both are ordinary in a merged source and neither reaches the
        ;; engine -- an unknown predicate especially must not, since it came
        ;; from a query.
        (and (some? s) (nil? row)) #{}
        (and (some? p) (not (cols p))) #{}
        :else
        (let [projected (if (some? p) [p] columns)
              rows (-select engine (cond-> {:columns projected :row row :filters []}
                                     (and (some? p) (some? o))
                                     (assoc :filters [[p o]])))]
          (into #{}
                (mapcat
                 (fn [r]
                   (let [n (get r row-key)]
                     (keep (fn [c]
                             (let [v (get r c)]
                               ;; A NULL cell is an ABSENT attribute, not an
                               ;; attribute whose value is nil. EAV has no
                               ;; way to say the latter and inventing one
                               ;; would make `[nil "price" nil]` return a
                               ;; datom for every row that has no price.
                               (when (some? v)
                                 (when (or (nil? o) (= o v))
                                   {:s (row-subject prefix n) :p c :o v}))))
                           projected))))
                rows)))))
  source/IRangeSource
  (-scan-range [_ attr lo hi opts]
    (let [cols (set columns)]
      (if (not (cols attr))
        #{}
        (let [preds (cond-> []
                      (some? lo) (conj [(if (:lo-open? opts) :> :>=) attr lo])
                      (some? hi) (conj [(if (false? (:hi-open? opts)) :<= :<) attr hi]))
              rows (-select engine {:columns [attr] :row nil :filters [] :predicates preds})]
          (into #{}
                (keep (fn [r]
                        (let [v (get r attr)]
                          (when (and (some? v) (source/in-range? v lo hi opts))
                            {:s (row-subject prefix (get r row-key)) :p attr :o v}))))
                rows))))))

(defn wide-source
  "An `IPatternSource` over a row-per-subject table.

  `:subject-prefix` is prepended to the row number to form the subject --
  pass the object's catalog id plus `#row` so a datom points back at the
  object it came from."
  [{:keys [engine subject-prefix] :or {subject-prefix "row"}}]
  (->WideSource engine (vec (-columns engine)) subject-prefix))

;; ── long ────────────────────────────────────────────────────────────────────

(defrecord ^:no-doc LongSource [engine s-col p-col o-col]
  source/IPatternSource
  (-scan [_ [s p o]]
    (let [filters (cond-> []
                    (some? s) (conj [s-col s])
                    (some? p) (conj [p-col p])
                    (some? o) (conj [o-col o]))
          rows (-select engine {:columns [s-col p-col o-col]
                                :row nil
                                :filters filters})]
      (into #{}
            (comp (map (fn [r] {:s (get r s-col) :p (get r p-col) :o (get r o-col)}))
                  ;; Re-checked rather than trusted: an engine that pushes a
                  ;; filter down imperfectly (a coarse row-group prune with no
                  ;; exact recheck) would otherwise widen the answer, and a
                  ;; source may never return a quad contradicting its pattern.
                  (filter (fn [q] (and (or (nil? s) (= s (:s q)))
                                       (or (nil? p) (= p (:p q)))
                                       (or (nil? o) (= o (:o q))))))
                  (filter (fn [q] (every? some? (vals q)))))
            rows))))

(defn long-source
  "An `IPatternSource` over a file that already stores one datom per row."
  [{:keys [engine s-column p-column o-column]
    :or {s-column "s" p-column "p" o-column "o"}}]
  (let [cols (set (-columns engine))
        missing (remove cols [s-column p-column o-column])]
    (when (seq missing)
      (throw (ex-info "long-source: relation lacks the datom columns"
                      {:type :kotobase.lake/missing-columns
                       :missing (vec missing) :columns (vec cols)})))
    (->LongSource engine s-column p-column o-column)))

(def row-attribute
  "The key `-select` must put a row's number under."
  row-key)
