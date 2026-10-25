(ns toshokan.sources.bnf
  "Bibliothèque nationale de France (BnF) SRU harvester.

  Endpoint: http://catalogue.bnf.fr/api/SRU (verified live 2026-07-19, no
  auth/registration required; documented at
  https://www.bnf.fr/fr/catalogue-general-de-la-bnf-api-sru). BnF's
  default `recordSchema=unimarcXchange` returns UNIMARC tag/subfield XML
  (would need a UNIMARC field-mapping table to parse); `recordSchema=
  dublincore` instead returns plain OAI Dublin Core, directly comparable
  to toshokan.sources.dnb's oai_dc -- used here for the same reason: no
  full XML/DOM parser dependency needed for this stable, simple schema.
  Note BnF's `dc:identifier` is overloaded (an ark: URL AND, when present,
  an \"ISBN <digits>\" string) -- disambiguated here by content shape
  rather than an xsi:type attribute (BnF's dublincore doesn't emit one,
  unlike DNB's)."
  (:require [kotoba.lang.text :as str]
            [toshokan.quad :as quad]))

(def ^:const sru-endpoint "http://catalogue.bnf.fr/api/SRU")
(def ^:const source-key :bnf)

(defn- tag-values [tag block]
  (->> (re-seq (re-pattern (str "<" tag "[^>]*>([\\s\\S]*?)</" tag ">")) block)
       (map (comp str/trim second))
       (remove str/blank?)))

(defn- record-datas [sru-xml]
  (map second (re-seq #"<srw:recordData>([\s\S]*?)</srw:recordData>" sru-xml)))

(defn- ark-id [url]
  (some-> url (str/split #"/") last))

(defn parse-record [block]
  (let [identifiers (tag-values "dc:identifier" block)
        source-url (first (filter #(str/starts-with? % "http") identifiers))
        isbn (->> identifiers
                  (filter #(str/starts-with? % "ISBN"))
                  (map #(str/trim (subs % 4))))
        titles (tag-values "dc:title" block)]
    (when (and source-url (seq titles))
      {:entity (str "bnf:" (ark-id source-url))
       :source-url source-url
       :title (first titles)
       :creators (tag-values "dc:creator" block)
       :publishers (tag-values "dc:publisher" block)
       :date (first (tag-values "dc:date" block))
       :language (first (tag-values "dc:language" block))
       :isbn isbn
       :format (first (tag-values "dc:format" block))})))

(defn parse-records [sru-xml-text]
  (keep parse-record (record-datas sru-xml-text)))

(defn search
  "Returns a JS Promise of a seq of field-maps for `query` (SRU CQL, e.g.
  `(str \"bib.title all \\\"\" q \"\\\"\")`).
  Optional `:start-record` (1-based) pages past the first result window
  (batch77: without this the daemon re-fetched page 1 forever → all-dups)."
  [query & {:keys [max-records start-record] :or {max-records 20 start-record 1}}]
  (-> (js/fetch (str sru-endpoint
                     "?version=1.2&operation=searchRetrieve"
                     "&query=" (js/encodeURIComponent query)
                     "&recordSchema=dublincore"
                     "&maximumRecords=" max-records
                     "&startRecord=" (or start-record 1))
                #js {:headers #js {"User-Agent" "toshokan-library-harvester/0.1 (kotoba-lang/toshokan; public bibliographic metadata preservation; https://github.com/kotoba-lang/toshokan)"}})
      (.then (fn [^js r]
               (if (.-ok r)
                 (.text r)
                 (throw (js/Error. (str "BnF SRU HTTP " (.-status r)))))))
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
    :library/format (:format m)
    :library/retrieved-at retrieved-at}))
