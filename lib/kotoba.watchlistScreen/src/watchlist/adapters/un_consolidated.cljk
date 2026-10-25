(ns watchlist.adapters.un-consolidated
  "UN Security Council Consolidated List XML -> watchlist.model entities.
   Schema verified against the actual live file fetched from
   https://scsanctions.un.org/resources/xml/en/consolidated.xml during this
   ns's development (root <CONSOLIDATED_LIST>, dateGenerated attribute) —
   not reconstructed from memory. See
   test/fixtures/un_consolidated_sample.xml for a schema-faithful fixture
   (fabricated names, real element structure).

   Individuals carry FIRST_NAME/SECOND_NAME/THIRD_NAME as separate fields;
   entities carry the whole org name in FIRST_NAME alone (confirmed from the
   live file, not a guess — an odd schema choice on the UN's part, not
   this repo's)."
  (:require [kotoba.lang.text :as str]
            [watchlist.adapters.xml :as xml]
            [watchlist.model :as model]))

(defn- name-parts [el]
  (->> ["FIRST_NAME" "SECOND_NAME" "THIRD_NAME" "FOURTH_NAME"]
       (map #(xml/child-text el %))
       (remove str/blank?)))

(defn- entry-name [el] (str/join " " (name-parts el)))

(defn- alias-names [el alias-tag]
  (into [] (comp (map #(xml/child-text % "ALIAS_NAME")) (remove str/blank?))
        (xml/children el alias-tag)))

(defn- entry-nationalities [el]
  (into [] (comp (map #(xml/child-text % "VALUE")) (remove str/blank?))
        (xml/children el "NATIONALITY")))

(defn- entry-dob
  "UN dates of birth are discrete YEAR/MONTH/DAY fields (sometimes only YEAR,
   sometimes a FROM_YEAR/TO_YEAR range for an approximate date) rather than
   OFAC's free-text string — carried through as whatever fields are present,
   joined, not normalized into a single date type."
  [el]
  (when-let [dob-el (xml/child el "INDIVIDUAL_DATE_OF_BIRTH")]
    (let [parts (->> ["YEAR" "MONTH" "DAY" "FROM_YEAR" "TO_YEAR"]
                      (keep (fn [tag] (when-let [v (xml/child-text dob-el tag)] (str tag ":" v)))))]
      (when (seq parts) (str/join " " parts)))))

(defn individual->entity [el]
  (let [primary-name (entry-name el)]
    (when (seq primary-name)
      (model/entity (str "un-consolidated:" (xml/child-text el "DATAID")) :un-consolidated
                     {:type :individual
                      :primary-name primary-name
                      :aliases (alias-names el "INDIVIDUAL_ALIAS")
                      :dob (entry-dob el)
                      :nationality (entry-nationalities el)
                      :programs (remove str/blank? [(xml/child-text el "UN_LIST_TYPE")])}))))

(defn entity->entity [el]
  (let [primary-name (entry-name el)]
    (when (seq primary-name)
      (model/entity (str "un-consolidated:" (xml/child-text el "DATAID")) :un-consolidated
                     {:type :entity
                      :primary-name primary-name
                      :aliases (alias-names el "ENTITY_ALIAS")
                      :programs (remove str/blank? [(xml/child-text el "UN_LIST_TYPE")])}))))

(defn parse
  "UN Consolidated List XML string -> {:entities [...] :source-published-at
   str :entity-count int}. `:source-published-at` is the root element's
   `dateGenerated` attribute (an ISO-8601-ish timestamp string), carried
   through as-is."
  [xml-str]
  (let [root (xml/parse-elements xml-str)
        individuals (into [] (keep individual->entity)
                          (xml/children (xml/child root "INDIVIDUALS") "INDIVIDUAL"))
        entities (into [] (keep entity->entity)
                       (xml/children (xml/child root "ENTITIES") "ENTITY"))
        all (into individuals entities)]
    {:entities all
     :source-published-at (get-in root [:attrs "dateGenerated"])
     :entity-count (count all)}))
