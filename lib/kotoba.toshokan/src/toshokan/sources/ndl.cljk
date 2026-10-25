(ns toshokan.sources.ndl
  "National Diet Library (NDL, 国立国会図書館) SRU harvester.

  Endpoint: https://ndlsearch.ndl.go.jp/api/sru (verified live 2026-07-19,
  no auth/registration required for non-commercial use per
  https://ndlsearch.ndl.go.jp/en/help/api). recordSchema=dcndl returns
  DC-NDL v2 (RDF/XML), HTML-entity-escaped inside each <recordData>
  element. This namespace unescapes and regex-extracts the handful of
  fields toshokan cares about rather than pulling in a full XML/DOM
  parser dependency -- adequate for this stable, well-documented schema;
  revisit with a real parser if NDL's field shape drifts.

  NDL asks non-commercial callers to attribute \"NDL Search API\" and to
  avoid sustained high-concurrency traffic (no fixed numeric rate limit is
  published) -- this namespace issues one sequential request per call, no
  internal concurrency."
  (:require [kotoba.lang.text :as str]
            [toshokan.quad :as quad]
            [toshokan.sources.ndl-core :as core]))

(def ^:const sru-endpoint "https://ndlsearch.ndl.go.jp/api/sru")
(def ^:const source-key :ndl)

(def parse-bib-resource core/parse-bib-resource)
(def parse-records core/parse-records)

(defn search
  "Returns a JS Promise of a seq of field-maps for `query` (SRU CQL, e.g.
  `(str \"title=\\\"\" q \"\\\"\")`).

  Optional `:start-record` (1-based SRU startRecord) pages deeper into a result
  set so the resident daemon can self-grow past the first page."
  [query & {:keys [max-records start-record] :or {max-records 20 start-record 1}}]
  (-> (js/fetch (str sru-endpoint
                     "?operation=searchRetrieve&version=1.2"
                     "&query=" (js/encodeURIComponent query)
                     "&recordSchema=dcndl"
                     "&maximumRecords=" max-records
                     "&startRecord=" (or start-record 1))
                #js {:headers #js {"User-Agent" "toshokan-library-harvester/0.1 (kotoba-lang/toshokan; public bibliographic metadata preservation; https://github.com/kotoba-lang/toshokan)"}})
      (.then (fn [^js r]
               (if (.-ok r)
                 (.text r)
                 (throw (js/Error. (str "NDL SRU HTTP " (.-status r)))))))
      (.then parse-records)))

(defn ->quads
  "field-map (as returned by search/parse-records) + retrieved-at ISO
  string + tx -> seq of [entity attr value tx :add] quads."
  [tx retrieved-at m]
  (quad/record->quads
   (:entity m) tx
   {:library/source source-key
    :library/source-url (:source-url m)
    :library/title (:title m)
    :library/creator (:creators m)
    :library/publisher (:publishers m)
    :library/date (:issued m)
    :library/ndc (:ndc m)
    :library/extent (:extent m)
    :library/retrieved-at retrieved-at}))
