(ns toshokan.sources.dnb
  "German National Library (Deutsche Nationalbibliothek, DNB) SRU
  harvester.

  Endpoint: https://services.dnb.de/sru/dnb (verified live 2026-07-19, no
  auth/registration required; DNB's own docs at
  https://www.dnb.de/EN/Professionell/Metadatendienste/Datenbezug/SRU/sru_node.html
  ask non-commercial callers to keep request rates modest -- this
  namespace issues one sequential request per call, no internal
  concurrency). recordSchema=oai_dc returns plain OAI Dublin Core, NOT
  double-HTML-escaped the way NDL's dcndl schema is -- <recordData> holds
  directly-parseable <dc:*> XML, so this parser is simpler than
  toshokan.sources.ndl's."
  (:require [kotoba.lang.text :as str]
            [toshokan.quad :as quad]))

(def ^:const sru-endpoint "https://services.dnb.de/sru/dnb")
(def ^:const source-key :dnb)

(defn- tag-values [tag block]
  (->> (re-seq (re-pattern (str "<" tag "[^>]*>([\\s\\S]*?)</" tag ">")) block)
       (map (comp str/trim second))
       (remove str/blank?)))

(defn- identifiers-by-type [block type-fragment]
  (->> (re-seq (re-pattern (str "<dc:identifier[^>]*xsi:type=\"[^\"]*" type-fragment "[^\"]*\"[^>]*>([\\s\\S]*?)</dc:identifier>")) block)
       (map (comp str/trim second))))

(defn- record-datas [sru-xml]
  (map second (re-seq #"<recordData>([\s\S]*?)</recordData>" sru-xml)))

(defn parse-record [block]
  (let [idns (identifiers-by-type block "IDN")
        titles (tag-values "dc:title" block)
        ;; Prefer an explicit tel:URL when present; otherwise the stable
        ;; d-nb.info permalink for the IDN (canonical catalog page).
        source-url (or (first (identifiers-by-type block "URL"))
                       (when (seq idns) (str "https://d-nb.info/" (first idns))))]
    (when (and (seq idns) (seq titles))
      {:entity (str "dnb:" (first idns))
       :source-url source-url
       :title (first titles)
       :creators (tag-values "dc:creator" block)
       :publishers (tag-values "dc:publisher" block)
       :date (first (tag-values "dc:date" block))
       :language (first (tag-values "dc:language" block))
       :isbn (map #(first (str/split % #"\s")) (identifiers-by-type block "ISBN"))
       :subjects (tag-values "dc:subject" block)
       :format (first (tag-values "dc:format" block))})))

(defn parse-records [sru-xml-text]
  (keep parse-record (record-datas sru-xml-text)))

(defn search
  "Returns a JS Promise of a seq of field-maps for `query` (SRU CQL, e.g.
  `(str \"WOE=\" q)` for a general word search).
  Optional `:start-record` (1-based) pages past the first result window
  (batch77: without this the daemon re-fetched page 1 forever → all-dups)."
  [query & {:keys [max-records start-record] :or {max-records 20 start-record 1}}]
  (-> (js/fetch (str sru-endpoint
                     "?version=1.1&operation=searchRetrieve"
                     "&query=" (js/encodeURIComponent query)
                     "&recordSchema=oai_dc"
                     "&maximumRecords=" max-records
                     "&startRecord=" (or start-record 1))
                #js {:headers #js {"User-Agent" "toshokan-library-harvester/0.1 (kotoba-lang/toshokan; public bibliographic metadata preservation; https://github.com/kotoba-lang/toshokan)"}})
      (.then (fn [^js r]
               (if (.-ok r)
                 (.text r)
                 (throw (js/Error. (str "DNB SRU HTTP " (.-status r)))))))
      (.then parse-records)))

(defn ->quads
  [tx retrieved-at m]
  (quad/record->quads
   (:entity m) tx
   {:library/source source-key
    :library/source-url (:source-url m)
    :library/title (:title m)
    :library/creator (:creators m)
    :library/publisher (:publishers m)
    :library/date (:date m)
    :library/language (:language m)
    :library/isbn (:isbn m)
    :library/subject (:subjects m)
    :library/format (:format m)
    :library/retrieved-at retrieved-at}))
