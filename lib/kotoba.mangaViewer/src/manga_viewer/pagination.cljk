(ns manga-viewer.pagination
  "Pure paging logic for the reader (ADR-2607070500).

  A *unit* is the vector of 0-based page indexes shown together on the stage.
  Spread mode follows Japanese RTL print convention (same as the
  manga.gftd.ai reader): the cover stands alone, then pages pair up —
  rendering order within a pair is right→left (manga-viewer.render reverses
  the unit).")

(defn single-image-pages? [work]
  (every? #(= 1 (count (:page/images %))) (:manga/pages work)))

(defn supported-modes
  "Modes the work can render. Spread pairing only makes sense when every
  page is a single composed image; panel-per-image works read as paged
  single + vertical scroll."
  [work]
  (if (single-image-pages? work)
    [:spread :single :scroll]
    [:single :scroll]))

(defn units
  "Display units for `page-count` pages in `mode`."
  [page-count mode]
  (cond
    (zero? page-count) []
    (= mode :spread) (into [[0]] (mapv vec (partition-all 2 (range 1 page-count))))
    (= mode :scroll) [(vec (range page-count))]
    :else (mapv vector (range page-count))))

(defn clamp-unit [units i]
  (cond
    (empty? units) 0
    (< i 0) 0
    (>= i (count units)) (dec (count units))
    :else i))

(defn unit-for-page
  "Unit index containing 0-based page index `page-idx` (e.g. to keep the
  reader position when switching modes)."
  [units page-idx]
  (or (first (keep-indexed (fn [i u] (when (some #{page-idx} u) i)) units))
      0))

(defn unit-label
  "Counter label like \"3-4 / 45\" (1-based page numbers)."
  [units i page-count]
  (let [u (get units (clamp-unit units i))]
    (when (seq u)
      (str (inc (first u))
           (when (> (count u) 1) (str "-" (inc (last u))))
           " / " page-count))))
