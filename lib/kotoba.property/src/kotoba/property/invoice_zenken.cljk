(ns kotoba.property.invoice-zenken
  "Portable parsing for the National Tax Agency 適格請求書発行事業者公表サイト
   全件データ (the invoice registry: every business registered to issue a
   qualified invoice under Japan's consumption-tax regime).

   ## Why this sits next to 法人番号 and not somewhere else

   A **corporation's** registration number is `T` + its 13-digit 法人番号, so for
   a company this is not a second identity — it is an *attribute* of the one it
   already has, and it answers a question the 法人番号 registry cannot: is this
   counterparty a 課税事業者 (and since when, and is the registration still
   live). It joins on `:company/houjin-bangou` with no translation.

   ## Sole proprietors are the reason this namespace has a kind guard

   An **individual's** registration number is *not* a 法人番号 — it is a number
   issued to a natural person, published alongside their name (and, where they
   asked for it, their trading name and address). That is natural-person data.
   `projectable?` says no for those rows, and the projector refuses to write
   them, so the rule is enforced by code rather than by a paragraph in
   DATA-GOVERNANCE.md that a future ingest might not read.

   That is also why 個人 rows can still be *collected* to a node-local corpus:
   answering \"is this one business registered\" for a named counterparty is a
   lookup, and a lookup does not require publishing a person-indexed dataset.

   出典：国税庁適格請求書発行事業者公表サイト（国税庁）
   https://www.invoice-kohyo.nta.go.jp/download/zenken を加工して作成"
  (:require [kotoba.lang.text :as str]))

(def source-id "nta-invoice-zenken")

(def authority-id "JP/NTA-Invoice")

(def dataset "invoice-registry")

(def licence "公共データ利用規約（第1.0版）(NTA)")

(def attribution
  "出典：国税庁適格請求書発行事業者公表サイト（国税庁）https://www.invoice-kohyo.nta.go.jp/download/zenken を加工して作成")

(def columns
  "The 24 columns of the 全件データ CSV, in file order.

   The file has no header row, so position is the only contract. These names
   are not inferred from the CSV — they are the JSON publish's own field names
   for the same records (`j_all_20260731.json`), which is the only artifact the
   authority ships that states the order unambiguously.

   Confirmed against the 2026-07-31 publish: `T1000020012131` is 苫小牧市, whose
   法人番号 registry row carries the same name and 北海道/213 codes."
  [:sequence-no :registration-no :process :correct :kind :country :latest
   :registered-at :updated-at
   ;; disposal (取消) comes BEFORE expire (失効) — the opposite of the order a
   ;; reader expects, and getting it backwards silently swaps two dates that
   ;; both mean "this registration ended".
   :disposal-date :expire-date
   :address :address-prefecture-code :address-city-code
   :address-request :address-request-prefecture-code :address-request-city-code
   :kana :name
   :address-inside :address-inside-prefecture-code :address-inside-city-code
   :trade-name :popular-or-previous-name])

(def column-count (count columns))

(def ^:private index-of-column
  (into {} (map-indexed (fn [i c] [c i]) columns)))

(def kinds
  "事業者区分 as the file publishes it: `1` for a sole proprietor, `2` for
   everything else (法人 and 人格のない社団等 both carry 2 — the *entity* type is
   which archive the row came from, not this column).

   A row whose kind is blank is a superseded publication: name, address and
   kind are all cleared, `latest` is 0, and an expire date is set. 555 of the
   7,906 rows in the 人格のない社団等 archive are of this shape."
  {"1" :individual
   "2" :corporate})

(def ^:private record-start-re
  ;; The registration number is quoted in the CSV (`1,"T1030005007532",01,...`)
  ;; — unlike the 法人番号 file, which quotes only its text fields.
  #"^\d+,\"?T[0-9]{13}\"?,")

(defn record-start? [line]
  (boolean (re-find record-start-re line)))

(defn parse-line
  "RFC-4180 line splitter: quoted fields, doubled quotes, commas inside quotes.
   Empty cells come back as nil."
  [line]
  (let [n (count line)]
    (loop [i 0 run-start 0 cell "" cells [] in-quotes? false]
      (if (>= i n)
        (mapv #(when-not (str/blank? %) %)
              (conj cells (str cell (subs line run-start n))))
        (let [c (nth line i)]
          (cond
            (and in-quotes? (= c \") (< (inc i) n) (= (nth line (inc i)) \"))
            (recur (+ i 2) (+ i 2) (str cell (subs line run-start i) "\"") cells true)

            (= c \")
            (recur (inc i) (inc i) (str cell (subs line run-start i))
                   cells (not in-quotes?))

            (and (= c \,) (not in-quotes?))
            (recur (inc i) (inc i) ""
                   (conj cells (str cell (subs line run-start i))) false)

            :else
            (recur (inc i) run-start cell cells in-quotes?)))))))

(defn cell [cells column] (nth cells (index-of-column column) nil))

(defn- put [m k v] (if (str/blank? v) m (assoc m k v)))

(defn row->record
  "One parsed row -> one portable entity, or nil if the row cannot be trusted
   positionally (wrong column count, or no `T` + 13 digits in column 2)."
  [cells]
  (when (and (= column-count (count cells))
             (let [n (cell cells :registration-no)]
               (and n (re-matches #"T[0-9]{13}" n))))
    (let [reg (cell cells :registration-no)
          kind (cell cells :kind)
          pref (cell cells :address-prefecture-code)
          individual? (= "1" kind)]
      (cond-> {:invoice/registration-no reg
               :invoice/latest? (= "1" (cell cells :latest))
               ;; Live = registered, and neither revoked nor expired. The
               ;; authority keeps those two endings in two columns; a consumer
               ;; asking "can I claim input tax against this invoice" needs the
               ;; conjunction, not either one.
               :invoice/active? (and (str/blank? (cell cells :disposal-date))
                                     (str/blank? (cell cells :expire-date)))
               :company/jurisdiction "JP"}
        kind (assoc :invoice/kind kind)
        ;; `put` drops blanks and therefore takes strings only; a boolean has
        ;; to be set with the presence of its source cell as the condition.
        (cell cells :country) (assoc :invoice/domestic? (= "1" (cell cells :country)))
        true (put :invoice/registered-at (cell cells :registered-at))
        true (put :invoice/updated-at (cell cells :updated-at))
        true (put :invoice/revoked-at (cell cells :disposal-date))
        true (put :invoice/expired-at (cell cells :expire-date))
        true (put :company/address (cell cells :address))
        pref (assoc :company/region (str "JP-" pref))
        ;; For a corporation or an unincorporated association the number is
        ;; `T` + the 法人番号, which is the join key to everything else. For a
        ;; sole proprietor the digits are NOT a 法人番号 and must not be
        ;; published under that attribute — that is exactly the confusion that
        ;; put two invoice numbers into a leads file as if they were corporate
        ;; numbers (ADR-2608181000's verification).
        (not individual?) (assoc :company/houjin-bangou (subs reg 1)
                                 :company/registration-no (subs reg 1))
        (not individual?) (put :company/legal-name (cell cells :name))
        (not individual?) (put :company/legal-name-kana (cell cells :kana))
        (not individual?) (put :invoice/trade-name (cell cells :trade-name))))))

(defn line->record [line] (row->record (parse-line line)))

(defn projectable?
  "May this record be written into a committed projection?

   No for 個人, and no for a blanked history row.

   Measured on the 2026-07-31 publish: the individual archive publishes **no
   names at all** — 0 of 200,000 sampled rows carry `name` or `tradeName`, only
   the number and the dates. So the reason to keep those rows off the shared
   plane is not that they are a name list; it is that a `T`-number for a sole
   proprietor identifies a natural person through the authority's own lookup
   site, and it joins to nothing here (there is no 法人番号 to join on). A
   node-local corpus can answer \"is this number registered, and since when\";
   a committed projection would be a person-linked identifier set with no query
   value."
  [rec]
  (boolean (and rec
                (not= "1" (:invoice/kind rec))
                (some? (:invoice/kind rec))
                (:company/houjin-bangou rec))))

(defn publish-id
  "`h_all_20260731_001.csv` / `j_all_20260731.csv` / `k_all_20260731_003.csv`
   -> `20260731`. The split index is not part of the publish."
  [entry-name]
  (some-> entry-name (->> (re-find #"_(\d{8})(?:_\d+)?\.csv$")) second))

(defn corpus-manifest
  [{:keys [publish content-sha256 observed-at sources record-count kinds-collected]}]
  (cond-> {:corpus/manifest true
           :corpus/format :edn-lines
           :source/dataset dataset
           :source/authority authority-id
           :source/licence licence
           :source/attribution attribution
           :source/publish publish
           :source/content-sha256 content-sha256
           :source/observed-at observed-at}
    sources (assoc :source/archives sources)
    kinds-collected (assoc :corpus/kinds (vec kinds-collected))
    record-count (assoc :corpus/record-count record-count)))
