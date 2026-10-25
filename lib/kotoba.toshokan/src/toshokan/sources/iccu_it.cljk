(ns toshokan.sources.iccu-it
  "Italy's OPAC SBN (Servizio Bibliotecario Nazionale, coordinated by
  ICCU -- Istituto Centrale per il Catalogo Unico, the national union
  catalog authority) JSON search harvester.

  Endpoint: http://opac.sbn.it/opacmobilegw/search.json (verified live
  2026-07-19, no auth needed). IMPORTANT CAVEAT, unlike this repo's other
  sources: ICCU's own documented protocol for programmatic access is
  Z39.50 (per https://www.iccu.sbn.it/en/interlibrary-loan-and-document-delivery-ill-sbn/technical-specifications-and-documentation-/index.html),
  not this JSON endpoint. This endpoint is the mobile-app backend for
  opac.sbn.it -- real, live, served directly from ICCU's own official
  domain (not a third-party scrape of someone else's system, unlike the
  situation this repo ruled out for Iran/Russia), but NOT formally
  published/versioned as a public developer API; a third-party writeup
  (https://literarymachin.es/sbn-json-api/) that documents it explicitly
  recommends contacting ICCU before building production software against
  it. Treat this integration as more likely to break/change than the
  other sources here, and reconsider it if ICCU ever publishes and
  documents a stable SRU/OAI-PMH endpoint instead."
  (:require [kotoba.lang.text :as str]
            [toshokan.quad :as quad]))

(def ^:const search-endpoint "http://opac.sbn.it/opacmobilegw/search.json")
(def ^:const source-key :iccu-it)

(defn- entity-id [codice]
  (some-> codice (str/replace "\\" "-") (->> (str "iccu-it:"))))

(defn- extract-year [pubblicazione]
  (some-> (re-find #"(1[5-9]\d\d|20\d\d)" (or pubblicazione "")) first))

(defn parse-item [item]
  (when (and (:codiceIdentificativo item) (:titolo item))
    {:entity (entity-id (:codiceIdentificativo item))
     :title (:titolo item)
     :creators (some-> (:autorePrincipale item) vector)
     :publication-statement (:pubblicazione item)
     :date (extract-year (:pubblicazione item))
     :format (:tipo item)
     :level (:livello item)}))

(defn parse-response
  "search.json response (already keywordized) -> seq of field-maps."
  [response]
  (keep parse-item (:briefRecords response)))

(defn search
  "Returns a JS Promise of a seq of field-maps for `query` (free text).
  Optional `:start` is 0-based row offset (OPAC SBN `start=`)."
  [query & {:keys [max-records start] :or {max-records 20 start 0}}]
  (-> (js/fetch (str search-endpoint "?any=" (js/encodeURIComponent query)
                     "&type=0&start=" (or start 0)
                     "&rows=" max-records)
                #js {:headers #js {"User-Agent" "toshokan-library-harvester/0.1 (kotoba-lang/toshokan; public bibliographic metadata preservation; https://github.com/kotoba-lang/toshokan)"}})
      (.then (fn [^js r]
               (if (.-ok r)
                 (.json r)
                 (throw (js/Error. (str "OPAC SBN HTTP " (.-status r)))))))
      (.then #(js->clj % :keywordize-keys true))
      (.then parse-response)))

(defn ->quads
  [tx retrieved-at m]
  (quad/record->quads
   (:entity m) tx
   {:library/source source-key
    :library/title (:title m)
    :library/creator (:creators m)
    :library/publication-statement (:publication-statement m)
    :library/date (:date m)
    :library/format (:format m)
    :library/level (:level m)
    :library/retrieved-at retrieved-at}))
