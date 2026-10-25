(ns toshokan.sources.nb-no
  "National Library of Norway (Nasjonalbiblioteket, nb.no) catalog
  harvester.

  Endpoint: https://api.nb.no/catalog/v1/items (verified live 2026-07-19,
  no auth/registration required; documented at
  https://api.nb.no/catalog/). Unlike toshokan.sources.loc's search
  endpoint, nb.no's item search response embeds full basic bibliographic
  metadata directly under each item's `metadata` key (title, creators,
  originInfo, identifiers, languages, subjectName) -- no second per-item
  fetch (e.g. to the linked `mods`/`dublincore` sub-resources) is needed
  for this scope. Plain JSON, no XML/regex parsing needed here."
  (:require [toshokan.quad :as quad]))

(def ^:const search-endpoint "https://api.nb.no/catalog/v1/items")
(def ^:const source-key :nb-no)

(defn parse-item [item]
  (let [m (:metadata item {})
        ids (:identifiers m {})
        origin (:originInfo m {})]
    (when (and (:sesamId ids) (:title m))
      {:entity (str "nb-no:" (:sesamId ids))
       :source-url (get-in item [:_links :self :href])
       :title (:title m)
       :creators (:creators m)
       :publisher (:publisher origin)
       :date (:issued origin)
       :language (map :code (:languages m))
       :isbn (concat (:isbn10 ids) (:isbn13 ids))
       :subjects (:subjectName m)})))

(defn parse-response
  "nb.no catalog search response (already keywordized) -> seq of
  field-maps."
  [response]
  (->> (get-in response [:_embedded :items])
       (keep parse-item)))

(defn search
  "Returns a JS Promise of a seq of field-maps for `query` (free text).
  Optional `:page` is 0-based (nb.no catalog API); daemon maps 1-based
  page → (dec page)."
  [query & {:keys [max-records page] :or {max-records 20 page 0}}]
  (-> (js/fetch (str search-endpoint "?q=" (js/encodeURIComponent query)
                     "&size=" max-records
                     "&page=" (or page 0))
                #js {:headers #js {"User-Agent" "toshokan-library-harvester/0.1 (kotoba-lang/toshokan; public bibliographic metadata preservation; https://github.com/kotoba-lang/toshokan)"}})
      (.then (fn [^js r]
               (if (.-ok r)
                 (.json r)
                 (throw (js/Error. (str "nb.no catalog HTTP " (.-status r)))))))
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
    :library/publisher (:publisher m)
    :library/date (:date m)
    :library/language (:language m)
    :library/isbn (:isbn m)
    :library/subject (:subjects m)
    :library/retrieved-at retrieved-at}))
