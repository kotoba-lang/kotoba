(ns ooyake.coverage
  "Kotoba/CLJC coverage model for world-government atlas depth.

  Coverage here is member-support metadata. It never fabricates units; it only
  derives which functional categories an existing national body can support from
  stable id suffixes, explicit COFOG codes, and conservative name signals."
  (:require [kotoba.lang.text :as str]))

(def category->suffixes
  {:finance #{"finance" "mof" "treasury" "minefi" "mef" "fin" "fazenda"
              "minfin" "shcp" "kemenkeu" "hmb" "economia" "moef" "bmf"}
   :foreign #{"foreign" "mofa"}
   :defense #{"defense" "mod"}
   :interior #{"interior" "mic"}
   :justice #{"justice" "moj"}
   :health #{"health" "mhlw"}
   :education #{"education" "mext"}
   :agriculture #{"agriculture" "maff"}
   :environment #{"environment" "moe"}
   :transport #{"transport" "mlit"}
   :labour #{"labour"}
   :energy #{"energy"}
   :culture #{"culture"}
   :trade #{"trade" "meti"}
   :communications #{"communications"}
   :social #{"social"}
   :housing #{"housing"}
   :science #{"science"}
   :tourism #{"tourism"}
   :industry #{"industry"}
   :water #{"water"}
   :central-bank #{"central-bank" "boj" "fed" "boe" "banque" "bundesbank"
                   "bancaditalia" "boc" "pbc" "bcb" "cbr" "banxico" "bi"
                   "tcmb" "sarb" "bcra" "sama" "bok" "rbi" "rba"}
   :legislature #{"legislature"}
   :supreme-court #{"supreme-court"}
   :audit #{"audit"}
   :ombudsman #{"ombudsman"}
   :electoral #{"electoral"}
   :nhri #{"nhri"}
   :anticorruption #{"anticorruption"}
   :dataprotection #{"dataprotection"}
   :competition #{"competition"}
   :finreg #{"finreg"}
   :statistics #{"statistics"}
   :prosecutor #{"prosecutor"}
   :revenue #{"revenue" "nta"}})

(def suffix->category
  (into {}
        (mapcat (fn [[category suffixes]]
                  (map (fn [suffix] [suffix category]) suffixes)))
        category->suffixes))

(def cofog->categories
  {"01.1" #{:finance :foreign}
   "02" #{:defense}
   "02.1" #{:defense}
   "03.1" #{:interior}
   "03.3" #{:justice}
   "04.1" #{:trade :labour :competition}
   "04.2" #{:agriculture}
   "04.3" #{:energy}
   "04.5" #{:transport}
   "04.6" #{:communications}
   "04.7" #{:industry}
   "05" #{:environment}
   "05.1" #{:environment}
   "05.2" #{:environment :water}
   "05.3" #{:environment}
   "06.1" #{:housing}
   "06.3" #{:water}
   "07" #{:health}
   "09" #{:education}
   "09.4" #{:education :science}
   "10" #{:social}
   "10.5" #{:labour :social}})

(def category->signals
  {:water ["water" "hydraulic" "hydrology" "irrigation" "sanitation"]
   :industry ["industry" "industrial" "manufacturing" "productive development" "production"]
   :science ["science" "research" "technology" "innovation"]
   :competition ["competition" "antitrust" "consumer protection" "markets authority"]
   :audit ["audit" "auditor general" "court of accounts" "comptroller"]
   :housing ["housing" "urban development" "settlements"]
   :trade ["trade" "commerce" "economy" "economic affairs"]
   :communications ["communications" "telecommunications" "digital"]
   :labour ["labour" "labor" "employment"]
   :social ["social" "welfare" "family"]
   :tourism ["tourism"]
   :energy ["energy" "petroleum" "mines"]
   :environment ["environment" "climate"]
   :transport ["transport" "transportation" "infrastructure"]
   :agriculture ["agriculture" "fisheries" "forestry"]
   :culture ["culture" "sports"]
   :health ["health"]
   :education ["education"]
   :justice ["justice" "law"]
   :interior ["interior" "home affairs"]
   :foreign ["foreign" "external affairs"]
   :finance ["finance" "treasury"]
   :defense ["defense" "defence"]})

(defn categories
  []
  (-> category->suffixes keys sort vec))

(defn- text
  [unit]
  (str/lower
   (str (:gov.unit/id unit) " "
        (:gov.unit/name-en unit) " "
        (:gov.unit/name-local unit) " "
        (:gov.unit/name-romanized unit))))

(defn- national-suffix
  [unit]
  (when-let [id (:gov.unit/id unit)]
    (second (re-matches #"^gov\.[a-z]{3}\.([a-z0-9-]+)$" id))))

(defn- country-id?
  [unit]
  (= :country (:gov.unit/level unit)))

(defn- national-body?
  [unit]
  (boolean (and (national-suffix unit)
                (not (country-id? unit)))))

(defn unit-categories
  "Return the functional categories covered by a single national-body unit."
  [unit]
  (if-not (national-body? unit)
    #{}
    (let [suffix (national-suffix unit)
          from-suffix (some-> suffix suffix->category vector set)
          from-cofog (->> (:gov.unit/cofog unit)
                          (mapcat #(get cofog->categories (str %)))
                          set)
          t (text unit)
          from-name (->> category->signals
                         (keep (fn [[category signals]]
                                 (when (some #(str/includes? t %) signals)
                                   category)))
                         set)]
      (set (concat from-suffix from-cofog from-name)))))

(defn country-code
  [unit]
  (or (:gov.unit/jurisdiction unit)
      (second (re-matches #"^gov\.([a-z]{3})(?:\..*)?$" (:gov.unit/id unit)))))

(defn country-codes
  [units]
  (->> units
       (filter country-id?)
       (keep country-code)
       (filter #(= 3 (count %)))
       set))

(defn coverage-by-country
  [units]
  (let [countries (country-codes units)
        initial (zipmap countries (repeat #{}))]
    (reduce
     (fn [acc unit]
       (if-let [iso (country-code unit)]
         (if (contains? countries iso)
           (update acc iso into (unit-categories unit))
           acc)
         acc))
     initial
     units)))

(defn category-coverage
  [units]
  (let [by-country (coverage-by-country units)]
    (into {}
          (map (fn [category]
                 [category (count (filter #(contains? % category)
                                          (vals by-country)))]))
          (categories))))

(defn gap-records
  [units]
  (let [by-country (coverage-by-country units)]
    (->> (for [iso (sort (keys by-country))
               category (categories)
               :when (not (contains? (get by-country iso) category))]
           {:coverage.gap/jurisdiction iso
            :coverage.gap/category category
            :coverage.gap/status :missing-national-body
            :coverage.gap/source :derived-from-existing-units})
         vec)))

(defn summary
  [units]
  (let [by-country (coverage-by-country units)
        total-countries (count by-country)
        category-counts (category-coverage units)
        completeness (map count (vals by-country))]
    {:coverage/countries total-countries
     :coverage/categories (count (categories))
     :coverage/category-counts category-counts
     :coverage/average-completeness (if (seq completeness)
                                      (/ (reduce + completeness)
                                         (double total-countries))
                                      0.0)
     :coverage/gaps (count (gap-records units))}))
