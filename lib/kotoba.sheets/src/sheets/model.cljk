(ns sheets.model
  (:require [kotoba.lang.text :as str]))

(defn workbook
  ([id] (workbook id {}))
  ([id attrs]
   (merge {:sheets/id id
           :sheets/type :workbook
           :sheets/tabs {}
           :sheets/named-ranges {}
           :sheets/charts []}
          attrs)))

(defn tab
  ([id] (tab id {}))
  ([id attrs]
   (merge {:sheets/id id
           :sheets/title id
           :sheets/cells {}}
          attrs)))

(def alphabet "ABCDEFGHIJKLMNOPQRSTUVWXYZ")

(defn column-name
  "1 → A, 26 → Z, 27 → AA.

  Bijective base-26: there is no zero digit, so the usual division has to
  borrow one before each step. Getting this wrong gives a workbook whose
  27th column is `BA`, which Excel opens without complaint and reads wrong.

  The letter comes out of `alphabet` by index rather than out of arithmetic
  on a character code. `(int ch)` does not mean the same thing on both
  hosts — on the JVM a character is a `Character` and `int` is its code
  point; in ClojureScript it is a one-character string and `int` coerces it
  to 0 — so the arithmetic version silently produced control characters and
  read every column as 1 under cljs.

  This lives here rather than in `sheets.xlsx`, where it was, because
  addressing is not a fact about a file format. It was written twice and got
  the same bug both times."
  [col]
  (loop [n (long col) out ""]
    (if (pos? n)
      (let [rem (mod (dec n) 26)]
        (recur (quot (dec n) 26) (str (subs alphabet rem (inc rem)) out)))
      out)))

(defn column-number
  "`A` → 1, `AA` → 27. The inverse of `column-name`, and nil for anything
  that is not all letters."
  [letters]
  (let [s (str/upper (str letters))]
    (when (seq s)
      (reduce (fn [n ch]
                (if-let [i (str/index-of alphabet ch)]
                  (+ (* 26 n) (inc i))
                  (reduced nil)))
              0
              s))))

(defn cell-key [row col]
  [(long row) (long col)])

(defn put-cell [tab row col value]
  (assoc-in tab [:sheets/cells (cell-key row col)] {:sheets/value value}))

(defn put-formula [tab row col expr]
  (assoc-in tab [:sheets/cells (cell-key row col)] {:sheets/formula expr}))

(defn put-cell-style [tab row col style]
  (assoc-in tab [:sheets/cells (cell-key row col) :sheets/style] style))

(defn get-cell [tab row col]
  (get-in tab [:sheets/cells (cell-key row col)]))

(defn add-tab [wb t]
  (assoc-in wb [:sheets/tabs (:sheets/id t)] t))

(defn add-named-range [wb id attrs]
  (assoc-in wb [:sheets/named-ranges id]
            (merge {:sheets/id id} attrs)))

(defn add-chart [wb chart]
  (update wb :sheets/charts conj chart))

(defn tab-by-id [wb id]
  (get-in wb [:sheets/tabs id]))

(defn range-values [tab row1 col1 row2 col2]
  (vec
   (for [row (range row1 (inc row2))]
     (vec
      (for [col (range col1 (inc col2))]
        (:sheets/value (get-cell tab row col)))))))

(defn sortable-range?
  "Whether the rows of this range can be reordered without changing what the
  workbook says.

  They cannot when the range holds a formula. A formula moves with its row
  and its references do not: `=B2*2` in row 2 is still `=B2*2` after it
  becomes row 5, so it now multiplies somebody else's number. Adjusting them
  is what a spreadsheet with a dependency graph does, and this does not have
  one — so the answer is no rather than a rearrangement that quietly
  computes something else.

  A formula elsewhere in the tab is fine: it points at addresses, and the
  values at those addresses are exactly what moved."
  [tab row1 col1 row2 col2]
  (not-any? (fn [[row col]]
              (:sheets/formula (get-cell tab row col)))
            (for [row (range row1 (inc row2))
                  col (range col1 (inc col2))]
              [row col])))

(defn- sort-key
  "What a cell sorts by: its number when it holds one, its text otherwise.

  Numbers before text, and empty last, which is what a person sorting a
  column of amounts with a gap in it expects — an empty cell is not the
  smallest amount, it is the absence of one."
  [value]
  (let [text (str value)
        number (when-not (str/blank? text)
                 #?(:clj (try (Double/parseDouble (str/trim text))
                              (catch Exception _ nil))
                    :cljs (let [n (js/parseFloat (str/trim text))]
                            (when (and (not (js/isNaN n))
                                       (re-matches #"\s*-?[0-9.eE+]+\s*" text))
                              n))))]
    (cond
      (str/blank? text) [2 0 ""]
      number [0 number ""]
      :else [1 0 text])))

(defn sort-range
  "The rows of a range, reordered by one of its columns.

  A whole row of the range moves together — sorting one column and leaving
  the rest is the classic way to destroy a table, and no interface should be
  able to ask for it. Everything the cell carries moves with it, styles
  included: a red total is red because of the number in it, not because of
  the row it was on.

  Returns the tab unchanged when the range holds a formula; ask
  `sortable-range?` first if you need to tell that from a range that was
  already in order."
  ([tab row1 col1 row2 col2 by-col] (sort-range tab row1 col1 row2 col2 by-col true))
  ([tab row1 col1 row2 col2 by-col ascending?]
   (if-not (sortable-range? tab row1 col1 row2 col2)
     tab
     (let [rows (vec (for [row (range row1 (inc row2))]
                       (vec (for [col (range col1 (inc col2))]
                              (get-cell tab row col)))))
           at (- by-col col1)
           ordered (cond->> (sort-by #(sort-key (:sheets/value (get % at))) rows)
                     (not ascending?) reverse)]
       (reduce (fn [acc [index cells]]
                 (reduce (fn [acc' [offset cell]]
                           (let [key (cell-key (+ row1 index) (+ col1 offset))]
                             ;; An empty cell in the range is stored as
                             ;; nothing rather than as an empty map, so a
                             ;; sorted tab has the same cell count as the
                             ;; one it came from.
                             (if cell
                               (assoc-in acc' [:sheets/cells key] cell)
                               (update acc' :sheets/cells dissoc key))))
                         acc
                         (map-indexed vector cells)))
               tab
               (map-indexed vector (vec ordered)))))))

(defn seed-workbook []
  (-> (workbook "gftd-sheets")
      (add-tab (-> (tab "plan" {:sheets/title "Plan"})
                   (put-cell 1 1 "Workstream")
                   (put-cell 1 2 "Owner")
                   (put-cell 2 1 "Slides")
                   (put-cell 2 2 "GFTD")))))
