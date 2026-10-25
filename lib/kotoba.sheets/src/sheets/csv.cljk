(ns sheets.csv
  "CSV in and out of a tab.

  A tab rather than a workbook, because CSV has no idea a workbook has more
  than one and pretending otherwise means inventing a convention — a sheet
  name in the first line, a file per tab in a zip — that nothing on the other
  end would agree with. One tab is what the format can carry, so one tab is
  what these take and return.

  ## RFC 4180, and the parts of it that matter

  A field is quoted when it contains a comma, a quote, a carriage return or a
  newline; a quote inside a quoted field is doubled. Reading accepts more
  than writing produces: bare CRLF or LF line endings, and an unterminated
  final quote is taken as ending at the end of input rather than throwing,
  because a truncated file should import as far as it goes and say what it
  got.

  ## What a cell becomes

  Text. Every value read from CSV is a string, including one that looks like
  a number, because CSV does not say and guessing is how a part number
  becomes a float. A caller that knows better converts.

  Writing is the mirror with one exception: a formula cell writes back as
  `=EXPR`, which is what a spreadsheet would show and what this library's own
  editor shows. There is no evaluation here — `sheets` has no evaluator — so
  a formula's *value* is not something this could write even if the
  convention said to."
  (:require [kotoba.lang.text :as str]
            [sheets.model :as model]))

(def ^:private needs-quoting #"[,\"\r\n]")

(defn- write-field [value]
  (let [text (cond (nil? value) ""
                   (string? value) value
                   :else (str value))]
    (if (re-find needs-quoting text)
      (str "\"" (str/replace text "\"" "\"\"") "\"")
      text)))

(defn- cell-text
  "One cell as CSV text. A formula keeps its leading `=`."
  [cell]
  (cond
    (nil? cell) ""
    (contains? cell :sheets/formula) (str "=" (:sheets/formula cell))
    :else (:sheets/value cell)))

(defn tab-bounds
  "`[rows cols]` — the furthest row and column the tab has a cell in.

  `[0 0]` for an empty tab, which is what makes writing one produce nothing
  rather than a line of commas."
  [tab]
  (reduce (fn [[rows cols] [row col]]
            [(max rows (long row)) (max cols (long col))])
          [0 0]
          (keys (:sheets/cells tab))))

(defn tab->csv
  "A tab as CSV text, `\\r\\n` separated as the RFC says.

  Rectangular: every row is padded to the widest column the tab uses, because
  a reader that meets a short row has to guess whether the cells are missing
  or the file is."
  [tab]
  (let [[rows cols] (tab-bounds tab)]
    (if (zero? rows)
      ""
      (str/join "\r\n"
                (for [row (range 1 (inc rows))]
                  (str/join "," (for [col (range 1 (inc cols))]
                                  (write-field (cell-text (model/get-cell tab row col))))))))))

(defn parse-csv
  "CSV text as a vector of vectors of strings.

  Separate from `csv->tab` because it is the half worth testing on its own,
  and because a caller that wants the grid rather than a tab should not have
  to build one to get it."
  [text]
  ;; A vector of characters rather than a StringBuilder: this namespace is
  ;; `.cljc` and the rest of `sheets` runs on both hosts, so it does not get
  ;; to reach for a Java class.
  (let [text (str text)
        n (count text)
        at (fn [i] (subs text i (inc i)))
        done (fn [chars] (apply str chars))]
    (loop [i 0, field [], row [], rows [], quoted? false, seen-any? false]
      (if (>= i n)
        (let [row (conj row (done field))]
          (if (or seen-any? (seq field)) (conj rows row) rows))
        (let [c (at i)]
          (cond
            quoted?
            (cond
              (and (= c "\"") (< (inc i) n) (= (at (inc i)) "\""))
              (recur (+ i 2) (conj field "\"") row rows true true)
              (= c "\"") (recur (inc i) field row rows false true)
              :else (recur (inc i) (conj field c) row rows true true))

            (= c "\"") (recur (inc i) field row rows true true)
            (= c ",") (recur (inc i) [] (conj row (done field)) rows false true)

            (or (= c "\n") (= c "\r"))
            (let [skip (if (and (= c "\r") (< (inc i) n) (= (at (inc i)) "\n")) 2 1)]
              (recur (+ i skip) [] [] (conj rows (conj row (done field))) false false))

            :else (recur (inc i) (conj field c) row rows false true)))))))

(defn csv->tab
  "CSV text as a tab.

  Empty fields are left out rather than stored as empty strings: a cell that
  is not there and a cell holding `\"\"` are different things to
  `sheets.validate` and to anything counting them, and CSV cannot tell them
  apart. Leaving them out is the reading that does not invent data.

  A field beginning with `=` becomes a formula, which is the inverse of what
  `tab->csv` writes."
  ([id text] (csv->tab id text {}))
  ([id text attrs]
   (reduce
    (fn [tab [row-index row]]
      (reduce
       (fn [tab [col-index field]]
         (cond
           (str/blank? field) tab
           (str/starts-with? field "=")
           (model/put-formula tab (inc row-index) (inc col-index) (subs field 1))
           :else (model/put-cell tab (inc row-index) (inc col-index) field)))
       tab
       (map-indexed vector row)))
    (model/tab id attrs)
    (map-indexed vector (parse-csv text)))))

(defn workbook->csv
  "One tab of `workbook`, by id. Nil when there is no such tab."
  [workbook tab-id]
  (some-> (model/tab-by-id workbook tab-id) tab->csv))

(defn unexpressed
  "What `workbook->csv` will drop from this workbook, one entry per thing.

  Shaped like `sheets.validate/problems`, the same as
  `sheets.xlsx/unexpressed`. All `:info`: a CSV not carrying something is a
  property of CSV.

  The first entry is the one that surprises people. **A CSV is one table**,
  so every other tab is left behind — and unlike the losses below, that one
  is most of the document.

  A formula goes out as its own text, `=SUM(B2:B9)`, rather than as what it
  comes to. Excel re-evaluates it on open, which is why it is written that
  way; a reader that is not a spreadsheet gets the formula. Both are
  defensible and only one can be written, so the choice is reported rather
  than argued."
  [workbook tab-id]
  (let [entry (fn [code id msg]
                {:sheets/severity :info :sheets/code code :sheets/id id
                 :sheets/msg msg})
        tab (model/tab-by-id workbook tab-id)
        others (remove #(= tab-id (key %)) (:sheets/tabs workbook))]
    (vec
     (concat
      (when (seq others)
        [(entry :csv/other-tabs-dropped tab-id
                (str "CSV は1つの表なので、他の " (count others)
                     " タブは書き出されません。"))])
      (when (some #(contains? % :sheets/formula) (vals (:sheets/cells tab)))
        [(entry :csv/formulas-as-text tab-id
                "数式は計算結果ではなく =SUM(...) のまま書き出されます。")])
      (when (some :sheets/style (vals (:sheets/cells tab)))
        [(entry :csv/cell-styles-dropped tab-id
                "セルの書式（色・太字・表示形式）は書き出されません。")])
      (when (seq (:sheets/named-ranges workbook))
        [(entry :csv/named-ranges-dropped tab-id
                (str (count (:sheets/named-ranges workbook))
                     " 件の名前付き範囲は書き出されません。"))])
      (when (seq (:sheets/charts workbook))
        [(entry :csv/charts-dropped tab-id
                (str (count (:sheets/charts workbook))
                     " 件のグラフは書き出されません。"))])))))

(defn import-csv
  "`workbook` with `text` added as a tab.

  Replaces a tab of the same id, because importing the same file twice
  should leave one tab rather than a second one nobody asked for."
  ([workbook tab-id text] (import-csv workbook tab-id text {}))
  ([workbook tab-id text attrs]
   (model/add-tab workbook (csv->tab tab-id text attrs))))
