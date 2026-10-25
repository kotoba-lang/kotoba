(ns tana.member
  "One member of a table: an object, and everything its footer said.

  A member is the unit a table prunes at the coarse level, and it is recorded
  as **what the footer said, plus where the bytes are** — statistics and byte
  ranges together. That pairing is the whole point: a planner that holds
  statistics but not ranges must still open the object to find out where a
  column chunk begins, which is the round trip the table exists to remove.

  ## This namespace takes footers as data, not as a library

  `from-parquet-footer` accepts the map `parquet.footer/parse` returns. It
  does not require the Parquet library, and must not: a table is not a
  Parquet thing, and a dependency here would land in every consumer of the
  table plane. The same is true of Arrow, ORC and anything else — a format
  adapter is a pure function from that format's metadata to this shape.

  ## Absence is recorded as absence

  A column chunk whose writer recorded no bounds is stored with `:stats`
  present and `:min`/`:max` missing. It is never stored as an empty map, and
  never as a wide-open interval: `columnar.stats` reads a missing bound as
  *no claim*, and a fabricated one would be a claim that permits a skip."
  (:require [kotoba.lang.text :as str]))

(defn- non-blank [s] (and (string? s) (not (str/blank? s)) s))

(defn data-page-at
  "Where the data pages begin, relative to the start of the chunk's range.

  Zero unless a dictionary page precedes them. A reader holding the chunk's
  bytes and not its footer cannot derive this, and guessing zero on a
  dictionary-encoded chunk reads the dictionary page header as a data page
  header — which parses."
  [{:keys [data-page-offset dictionary-page-offset]}]
  (if dictionary-page-offset (- data-page-offset (min dictionary-page-offset data-page-offset)) 0))

(defn chunk-range
  "The half-open byte range `[start end)` a Parquet column chunk occupies.

  A dictionary page, when present, precedes the data pages and is inside the
  same `total_compressed_size`, so the chunk begins at whichever offset comes
  first. This is the same rule `parquet.source/-read-column` applies at read
  time; recording a different one here would send the reader a range that
  parses as a different page."
  [{:keys [data-page-offset dictionary-page-offset total-compressed-size]}]
  (let [start (if dictionary-page-offset
                (min dictionary-page-offset data-page-offset)
                data-page-offset)]
    [start (+ start total-compressed-size)]))

(defn from-parquet-footer
  "A member from `{:object :size}` and a parsed Parquet footer map.

  -> `{:object :size :rows :chunks [{:rows n :columns {col {:range [s e)
        :stats {...} :codec :encodings}}}]}`

  `:stats` carries `:rows` always, and `:min`/`:max` only when the file
  recorded them. `:codec` travels because a planner can then refuse an
  unreadable chunk *before* fetching it — a refusal that costs a download is
  a refusal that arrived too late.

  `:type` and `:def-level` travel for a sharper reason: **without them the
  saving evaporates.** A reader that holds a chunk's bytes but not its
  physical type has to fetch the footer to learn it, which is the round trip
  the root was built to remove. They are two small integers and they are what
  makes a chunk decodable on its own."
  [{:keys [object size]} {:keys [columns row-groups num-rows schema] :as _footer}]
  (when-not (non-blank object)
    (throw (ex-info "a member needs an object address"
                    {:type :tana/invalid-member})))
  (when-not (and (number? size) (pos? size))
    (throw (ex-info "a member needs the object's size"
                    {:type :tana/invalid-member :object object})))
  {:object object
   :size size
   :rows (long (or num-rows 0))
   :chunks
   (let [def-levels (into {} (map (fn [el] [(:name el)
                                            (if (= :optional (:repetition el)) 1 0)]))
                          (rest schema))]
     (mapv (fn [rg]
           {:rows (:num-rows rg)
            :columns
            (into {}
                  (map (fn [col cm]
                         [col (cond-> {:range (chunk-range cm)
                                       :stats (cond-> {:rows (:num-values cm)}
                                                (contains? (:statistics cm) :min)
                                                (assoc :min (get-in cm [:statistics :min]))
                                                (contains? (:statistics cm) :max)
                                                (assoc :max (get-in cm [:statistics :max]))
                                                (contains? (:statistics cm) :nulls)
                                                (assoc :nulls (get-in cm [:statistics :nulls])))
                                       :codec (:codec cm)
                                       :type (:type cm)
                                       :data-at (data-page-at cm)
                                       :dictionary? (boolean (:dictionary-page-offset cm))
                                       :def-level (get def-levels col 0)}
                                (:encodings cm) (assoc :encodings (vec (:encodings cm))))])
                         columns (:columns rg)))})
           row-groups))})

(defn from-arrow
  "A member from `{:object :size}` and what an Arrow IPC file's metadata said.

  `metadata` is `{:fields [{:name ..}] :buffer-counts [n ..] :batches
  [{:rows :nodes :buffers :body-at} ..]}` — the shape `arrow.ipc/footer`,
  `arrow.ipc/buffer-counts` and `arrow.ipc/batch-header` return, as data.

  **Arrow records no column bounds.** Not a gap in this adapter and not
  something to paper over: a member built from Arrow reports `:rows` and
  `:nulls` and no `:min`/`:max`, so `columnar.stats` refuses to prune it and
  the root gives location without pruning. A format that records less plugs
  in by reporting less. Inventing a wide-open interval here would be a claim
  the data never made, and it would permit a skip.

  The range for a column is the span of **its** buffers — validity and values
  are separate buffers and both are needed, so one range covers from the
  first to the end of the last."
  [{:keys [object size]} {:keys [fields buffer-counts batches]}]
  (when-not (non-blank object)
    (throw (ex-info "a member needs an object address" {:type :tana/invalid-member})))
  (when-not (and (number? size) (pos? size))
    (throw (ex-info "a member needs the object's size"
                    {:type :tana/invalid-member :object object})))
  (let [names (mapv :name fields)
        base (reductions + 0 buffer-counts)]
    {:object object
     :size size
     :rows (reduce + 0 (map :rows batches))
     :chunks
     (mapv (fn [{:keys [rows nodes buffers body-at compression]}]
             {:rows rows
              :columns
              (into {}
                    (map-indexed
                     (fn [k col]
                       (let [from (nth base k)
                             mine (subvec (vec buffers) from (+ from (nth buffer-counts k)))
                             node (nth nodes k nil)]
                         [col {:range [(+ body-at (reduce min (map :offset mine)))
                                       (+ body-at (reduce max (map #(+ (:offset %) (:length %))
                                                                   mine)))]
                               ;; No :min/:max. Ever.
                               :stats {:rows (or (:length node) rows)
                                       :nulls (:nulls node)}
                               :codec (or compression :uncompressed)
                               :buffers (mapv (fn [b] [(+ body-at (:offset b)) (:length b)]) mine)}]))
                     names))})
           batches)}))

(defn columns
  "Column names this member has, as a set."
  [member]
  (into #{} (mapcat (comp keys :columns)) (:chunks member)))

(defn bounded?
  "Did this member record `min`/`max` for `column` in every chunk?

  The question a planner asks before claiming a prune is possible. A member
  that answers false is not broken — it is a format like Arrow IPC, which
  records no column bounds at all — and the consequence is that it is read,
  not that it is skipped."
  [member column]
  (every? (fn [chunk]
            (let [s (get-in chunk [:columns column :stats])]
              (and (contains? s :min) (contains? s :max))))
          (:chunks member)))
