(ns toshokan.sources.loc
  "Library of Congress (LOC) loc.gov JSON API harvester.

  Endpoint: https://www.loc.gov/search/?fo=json (verified live 2026-07-19,
  no API key required). Rate limiting is dynamic/undocumented numerically;
  this namespace issues one sequential request per call and stays well
  under the documented ~1000-items/page, <100000-results-deep-paging
  ceilings (https://www.loc.gov/apis/json-and-yaml/working-within-limits/).
  Note loc.gov/robots.txt disallows crawlers on /search for *unattributed*
  bots -- this harvester sends an identifying User-Agent per LOC's own
  request in that doc, distinguishing it from an anonymous scraper."
  (:require [kotoba.lang.text :as str]
            [toshokan.quad :as quad]))

(def ^:const search-endpoint "https://www.loc.gov/search/")
(def ^:const source-key :loc)

(defn- normalize-url [u]
  (cond
    (nil? u) nil
    (str/starts-with? u "//") (str "https:" u)
    :else u))

(defn- entity-id [result]
  (let [lccn (first (:number_lccn result))]
    (str "loc:" (or lccn
                     (some-> (:id result) (str/replace #"^https?://" ""))
                     (:url result)))))

(defn parse-result
  [result]
  (let [item (:item result {})]
    {:entity (entity-id result)
     :source-url (normalize-url (or (:url result) (:id result)))
     :title (or (:title item) (:title result))
     :creators (or (:contributors item) (:contributor result))
     :publication-statement (:created_published item)
     :date (or (:date item) (:date result))
     :language (:language item)
     :lccn (:number_lccn result)
     :format (:format item)
     :subjects (:subjects item)}))

(defn parse-response
  "loc.gov JSON API response (already keywordized) -> seq of field-maps."
  [response]
  (->> (:results response)
       (remove #(= (:id %) nil))
       (map parse-result)))

(defn search
  "Returns a JS Promise of a seq of field-maps for `query` (free text).

  Optional `:page` (1-based, mapped to loc.gov `sp=`) pages deeper so the
  resident daemon can walk past the first result page."
  [query & {:keys [count page] :or {count 20 page 1}}]
  (-> (js/fetch (str search-endpoint "?q=" (js/encodeURIComponent query)
                     "&fo=json&c=" count
                     "&sp=" (or page 1))
                #js {:headers #js {"User-Agent" "toshokan-library-harvester/0.1 (kotoba-lang/toshokan; public bibliographic metadata preservation; https://github.com/kotoba-lang/toshokan)"}})
      (.then (fn [^js r]
               (if (.-ok r)
                 (.json r)
                 (throw (js/Error. (str "LOC search HTTP " (.-status r)))))))
      (.then #(js->clj % :keywordize-keys true))
      (.then parse-response)))

(defn ->quads
  [tx retrieved-at m]
  (quad/record->quads
   (:entity m) tx
   {:library/source source-key
    :library/source-url (:source-url m)
    :library/title (:title m)
    :library/creator (:creators m)
    :library/publication-statement (:publication-statement m)
    :library/date (:date m)
    :library/language (:language m)
    :library/lccn (:lccn m)
    :library/format (:format m)
    :library/subject (:subjects m)
    :library/retrieved-at retrieved-at}))
