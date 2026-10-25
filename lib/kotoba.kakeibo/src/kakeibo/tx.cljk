(ns kakeibo.tx
  "Statement rows -> canonical transactions.

  A *row* is whatever a statement export gives us as a map of column label to
  text. A *mapping* (data, per institution+document — see
  `resources/mappings/`) says which columns carry the date, the description,
  the money, and the institution's own reference. Nothing here parses PDFs or
  touches the network: extracting rows from a downloaded document is a host
  capability, and `kotoba-lang/statement-fetch` is what puts the document on
  disk in the first place.

  `normalize-rows` never drops a row quietly. Rows it cannot read come back
  under `:kakeibo/rejected` with the reason and the original row attached, so
  \"nothing spent\" and \"could not read\" never render the same — the rule
  `kotoba-lang/macos-inventory` states for probes, applied to money."
  (:require [kotoba.lang.text :as str]
            [kakeibo.amount :as amount]))

;; ---------------------------------------------------------------------------
;; Dates
;; ---------------------------------------------------------------------------

(def ^:private date-orders #{:ymd :dmy :mdy})

(defn- pad2 [s] (if (= 1 (count s)) (str "0" s) s))

(defn- digit-groups
  "Split normalized date text into its runs of digits: \"2026年7月1日\" ->
  (\"2026\" \"7\" \"1\")."
  [s]
  (->> (str/split s #"[^0-9]+")
       (remove str/blank?)))

(defn normalize-date
  "Normalize statement date text to ISO `YYYY-MM-DD`.

  Returns `{:date/iso \"2026-07-01\"}` or `{:date/problem ...}`. Accepts
  `2026-07-01`, `2026/7/1`, `2026.07.01`, `2026年7月1日`. Non-`:ymd` column
  orders must be declared by the mapping — a bare `03/04/2026` is genuinely
  ambiguous, so it is a problem rather than a coin flip.

  Range-checks month 1-12 and day 1-31 only. It deliberately does not know
  that February has 28 days: calendar validity belongs to whatever consumes
  the ISO string, and rejecting 2026-02-30 here would mean carrying a
  calendar in a parser."
  ([text] (normalize-date text :ymd))
  ([text order]
   (cond
     (not (contains? date-orders order))
     {:date/problem :unsupported-date-order :date/input text :date/order order}

     (or (nil? text) (and (string? text) (str/blank? text)))
     {:date/problem :blank :date/input text}

     :else
     (let [groups (digit-groups (amount/normalize-width (str text)))]
       (if (not= 3 (count groups))
         {:date/problem :unrecognized-date :date/input text}
         (let [[a b c] groups
               [y m d] (case order
                         :ymd [a b c]
                         :dmy [c b a]
                         :mdy [c a b])]
           (cond
             (not= 4 (count y)) {:date/problem :non-four-digit-year :date/input text}
             (> (count m) 2)    {:date/problem :unrecognized-date :date/input text}
             (> (count d) 2)    {:date/problem :unrecognized-date :date/input text}
             :else
             (let [mi (amount/parse m 1)
                   di (amount/parse d 1)
                   mv (:amount/minor mi)
                   dv (:amount/minor di)]
               (cond
                 (or (nil? mv) (nil? dv))
                 {:date/problem :unrecognized-date :date/input text}

                 (or (< mv 1) (> mv 12))
                 {:date/problem :month-out-of-range :date/input text}

                 (or (< dv 1) (> dv 31))
                 {:date/problem :day-out-of-range :date/input text}

                 :else
                 {:date/iso (str y "-" (pad2 m) "-" (pad2 d))})))))))))

;; ---------------------------------------------------------------------------
;; Descriptions
;; ---------------------------------------------------------------------------

(defn normalize-description
  "Fold width and collapse whitespace. Used for dedup keys and category
  matching; `:tx/description` keeps whatever the statement actually said."
  [text]
  (when (some? text)
    (-> (amount/normalize-width (str text))
        str/trim
        (str/replace #"\s+" " "))))

;; ---------------------------------------------------------------------------
;; Mapping validation
;; ---------------------------------------------------------------------------

(defn validate-mapping
  "Return a vector of problems with a mapping, empty when it is usable."
  [{:mapping/keys [institution account currency scale columns date-order] :as m}]
  (let [scale (or scale 1)
        cols  (or columns {})]
    (cond-> []
      (nil? institution)            (conj :missing-institution)
      (nil? account)                (conj :missing-account)
      (str/blank? (str currency))   (conj :missing-currency)
      (nil? (amount/fraction-digits scale)) (conj :unsupported-scale)
      (and (some? date-order)
           (not (contains? date-orders date-order))) (conj :unsupported-date-order)
      (nil? (:date cols))           (conj :missing-date-column)
      (nil? (:description cols))    (conj :missing-description-column)
      (and (nil? (:amount cols))
           (or (nil? (:in cols)) (nil? (:out cols))))
      (conj :missing-amount-columns)
      (nil? m)                      (conj :missing-mapping))))

;; ---------------------------------------------------------------------------
;; Row -> transaction
;; ---------------------------------------------------------------------------

(defn row->tx
  "Convert one statement row to a canonical transaction.

  Returns `{:kakeibo/tx {...}}` or `{:kakeibo/problems [...] :kakeibo/row row}`.
  All problems for the row are collected, not just the first, so a broken
  mapping surfaces in one pass instead of one ingest per column."
  [mapping row row-index]
  (let [{:mapping/keys [institution document account currency scale columns date-order]} mapping
        scale     (or scale 1)
        order     (or date-order :ymd)
        cols      (or columns {})
        date-res  (normalize-date (get row (:date cols)) order)
        amt-res   (if (:amount cols)
                    (amount/parse (get row (:amount cols)) scale)
                    (amount/parse-signed {:in  (get row (:in cols))
                                          :out (get row (:out cols))}
                                         scale))
        desc      (normalize-description (get row (:description cols)))
        ref       (when-let [rc (:ref cols)]
                    (let [v (normalize-description (get row rc))]
                      (when-not (str/blank? (str v)) v)))
        problems  (cond-> []
                    (:date/problem date-res)   (conj {:problem (:date/problem date-res)
                                                      :field :date})
                    (:amount/problem amt-res)  (conj {:problem (:amount/problem amt-res)
                                                      :field :amount})
                    (str/blank? (str desc))    (conj {:problem :blank-description
                                                      :field :description}))]
    (if (seq problems)
      {:kakeibo/problems problems :kakeibo/row row :kakeibo/row-index row-index}
      {:kakeibo/tx (cond-> {:tx/account     account
                            :tx/date        (:date/iso date-res)
                            :tx/amount      (:amount/minor amt-res)
                            :tx/currency    currency
                            :tx/description (str/trim (str (get row (:description cols))))
                            :tx/normalized  desc
                            :tx/source      {:source/institution institution
                                             :source/document    document
                                             :source/row         row-index}}
                     ref (assoc :tx/ref ref))})))

(defn normalize-rows
  "Convert a whole statement export.

  Returns
  `{:kakeibo/txs [...] :kakeibo/rejected [...] :kakeibo/read n :kakeibo/mapping-problems [...]}`.

  A mapping that does not validate yields zero transactions and the mapping
  problems — it does not partially ingest, because a wrong column mapping
  produces plausible-looking transactions, which is the failure mode that
  actually loses money."
  [mapping rows]
  (let [mapping-problems (validate-mapping mapping)]
    (if (seq mapping-problems)
      {:kakeibo/txs [] :kakeibo/rejected [] :kakeibo/read (count rows)
       :kakeibo/mapping-problems mapping-problems}
      (let [results (map-indexed (fn [i row] (row->tx mapping row i)) rows)]
        {:kakeibo/txs      (vec (keep :kakeibo/tx results))
         :kakeibo/rejected (vec (filter :kakeibo/problems results))
         :kakeibo/read     (count rows)
         :kakeibo/mapping-problems []}))))
