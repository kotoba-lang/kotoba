(ns toshokan.sources.kb-nl
  "Koninklijke Bibliotheek (KB, National Library of the Netherlands) SRU
  harvester.

  Endpoint: http://jsru.kb.nl/sru/sru (verified live 2026-07-19 -- HTTP
  redirects to https, no auth/registration required; documented at
  https://www.kb.nl/onderzoeken-vinden/zoeken-in-collecties/sru).
  `x-collection=GGC` (Gemeenschappelijke Geautomatiseerde Catalogisering,
  the KB's general catalog) + `recordSchema=dcx` returns records under
  `info:srw/schema/1/dc-v1.1`: Dublin Core elements disambiguated via
  `xsi:type` (e.g. multiple <dc:title> for main title vs. subtitle,
  multiple <dc:identifier> for a resolver URI vs. an ISBN) rather than one
  element per concept -- similar shape to toshokan.sources.dnb, one layer
  more nested. Entity id is the PPN embedded in the resolver.kb.nl URI."
  (:require [kotoba.lang.text :as str]
            [toshokan.quad :as quad]))

(def ^:const sru-endpoint "http://jsru.kb.nl/sru/sru")
(def ^:const source-key :kb-nl)

(defn- values-by-xsi-type [tag type-fragment block]
  (->> (re-seq (re-pattern (str "<" tag "[^>]*xsi:type=\"[^\"]*" type-fragment "[^\"]*\"[^>]*>([^<]*)</" tag ">")) block)
       (map (comp str/trim second))
       (remove str/blank?)))

(defn- tag-values [tag block]
  (->> (re-seq (re-pattern (str "<" tag "[^>]*>([^<]*)</" tag ">")) block)
       (map (comp str/trim second))
       (remove str/blank?)))

(defn- record-datas [sru-xml]
  (map second (re-seq #"<srw:recordData>([\s\S]*?)</srw:recordData>" sru-xml)))

(defn- ppn
  "The URI form varies by cataloging backend/era: resolver.kb.nl uses
  `PPN:<n>`, older picarta.pica.nl records use `PPN=<n>` (real variance
  observed live, not hypothetical -- see kb_nl_test.cljs)."
  [source-url]
  (some-> (re-find #"PPN[:=](\d+)" (or source-url "")) second))

(defn parse-record [block]
  (let [source-url (or (first (values-by-xsi-type "dc:identifier" "dcterms:URI" block))
                        (first (values-by-xsi-type "dcx:recordIdentifier" "dcterms:URI" block)))
        titles (or (seq (values-by-xsi-type "dc:title" "dcx:maintitle" block))
                   (tag-values "dc:title" block))]
    (when (and source-url (ppn source-url) (seq titles))
      {:entity (str "kb-nl:" (ppn source-url))
       :source-url source-url
       :title (first titles)
       :creators (tag-values "dc:creator" block)
       :date (first (tag-values "dc:date" block))
       :language (first (values-by-xsi-type "dc:language" "ISO639-2" block))
       :isbn (values-by-xsi-type "dc:identifier" "dcterms:ISBN" block)
       :extent (tag-values "dcterms:extent" block)
       :subjects (tag-values "dc:subject" block)})))

(defn parse-records [sru-xml-text]
  (keep parse-record (record-datas sru-xml-text)))

(defn search
  "Returns a JS Promise of a seq of field-maps for `query` (SRU CQL over
  the GGC general catalog).
  Optional `:start-record` (1-based SRU startRecord) pages deeper so the
  resident daemon can walk past the first result page (verified live:
  startRecord=1 vs 4 return different titles)."
  [query & {:keys [max-records start-record] :or {max-records 20 start-record 1}}]
  (-> (js/fetch (str sru-endpoint
                     "?version=1.2&operation=searchRetrieve"
                     "&x-collection=GGC"
                     "&query=" (js/encodeURIComponent query)
                     "&recordSchema=dcx"
                     "&maximumRecords=" max-records
                     "&startRecord=" (or start-record 1))
                #js {:headers #js {"User-Agent" "toshokan-library-harvester/0.1 (kotoba-lang/toshokan; public bibliographic metadata preservation; https://github.com/kotoba-lang/toshokan)"}
                     :redirect "follow"})
      (.then (fn [^js r]
               (if (.-ok r)
                 (.text r)
                 (throw (js/Error. (str "KB SRU HTTP " (.-status r)))))))
      (.then parse-records)))

(defn ->quads
  [tx retrieved-at m]
  (quad/record->quads
   (:entity m) tx
   {:library/source source-key
    :library/source-url (:source-url m)
    :library/title (:title m)
    :library/creator (:creators m)
    :library/date (:date m)
    :library/language (:language m)
    :library/isbn (:isbn m)
    :library/extent (:extent m)
    :library/subject (:subjects m)
    :library/retrieved-at retrieved-at}))
