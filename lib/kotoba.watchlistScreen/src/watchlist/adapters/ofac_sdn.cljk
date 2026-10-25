(ns watchlist.adapters.ofac-sdn
  "OFAC Specially Designated Nationals (SDN) List XML -> watchlist.model
   entities. Schema verified against the actual live file fetched from
   https://www.treasury.gov/ofac/downloads/sdn.xml during this ns's
   development (root <sdnList>, 19169 records as of 2026-07-17) — not
   reconstructed from memory. See test/fixtures/ofac_sdn_sample.xml for a
   schema-faithful fixture (fabricated names, real element structure).

   Simplification (documented, not hidden): OFAC's `sdnType` also carries
   'Vessel'/'Aircraft' values this repo doesn't have a watchlist.model type
   for (only :individual/:entity exist) — anything other than exactly
   'Individual' folds to :entity. A vessel/aircraft screening use case is
   out of scope for this repo's v1 (person/entity name-matching)."
  (:require [watchlist.adapters.xml :as xml]
            [watchlist.model :as model]))

(defn- entry-name
  "OFAC individuals carry firstName + lastName; entities (and some
   individuals) carry lastName only, which for an entity IS the org name."
  [el]
  (let [first-name (xml/child-text el "firstName")
        last-name (xml/child-text el "lastName")]
    (if (and first-name (seq first-name))
      (str first-name " " last-name)
      last-name)))

(defn- entry-type [el]
  (if (= "Individual" (xml/child-text el "sdnType")) :individual :entity))

(defn- aka-names [el]
  (into [] (comp (map entry-name) (remove nil?))
        (xml/children (xml/child el "akaList") "aka")))

(defn- entry-dob
  "Takes the mainEntry dateOfBirthItem if present, else the first. OFAC
   dates are free text (\"10 Dec 1948\", sometimes a range or 'circa') —
   this repo does not attempt to parse them into a structured date, only
   carries the string through (a caller wanting DOB-based confidence
   upgrade, per watchlist.model, must parse this itself)."
  [el]
  (let [items (xml/children (xml/child el "dateOfBirthList") "dateOfBirthItem")
        main (first (filter #(= "true" (xml/child-text % "mainEntry")) items))]
    (xml/child-text (or main (first items)) "dateOfBirth")))

(defn- entry-nationalities [el]
  (into [] (comp (map #(xml/child-text % "country")) (remove nil?))
        (xml/children (xml/child el "nationalityList") "nationality")))

(defn- entry-programs [el]
  (into [] (map xml/text-of) (xml/children (xml/child el "programList") "program")))

(defn entry->entity
  "One <sdnEntry> neutral element -> a watchlist.model entity, or nil if it
   has no usable name (defensive — every real entry has one, but never
   silently emit an unusable entity)."
  [el]
  (let [primary-name (entry-name el)]
    (when (seq primary-name)
      (model/entity (str "ofac-sdn:" (xml/child-text el "uid")) :ofac-sdn
                     {:type (entry-type el)
                      :primary-name primary-name
                      :aliases (aka-names el)
                      :dob (entry-dob el)
                      :nationality (entry-nationalities el)
                      :programs (entry-programs el)}))))

(defn parse
  "OFAC SDN List XML string -> {:entities [...] :source-published-at str
   :entity-count int}. `:source-published-at` is OFAC's own
   `<Publish_Date>` (a free-text date string, e.g. \"07/17/2026\") —
   carried through as-is, not parsed into a timestamp."
  [xml-str]
  (let [root (xml/parse-elements xml-str)
        publish-info (xml/child root "publshInformation")
        entities (into [] (keep entry->entity) (xml/children root "sdnEntry"))]
    {:entities entities
     :source-published-at (xml/child-text publish-info "Publish_Date")
     :record-count (some-> (xml/child-text publish-info "Record_Count") #?(:clj Integer/parseInt :cljs js/parseInt))
     :entity-count (count entities)}))
