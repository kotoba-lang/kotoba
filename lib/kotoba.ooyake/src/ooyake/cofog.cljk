(ns ooyake.cofog
  "COFOG-backed public-administration classification helpers.

  This namespace is pure data + pure functions. It does not claim official
  authority; it gives ooyake a stable government-function vocabulary for
  ministry-level atlas rows."
  (:require [kotoba.lang.text :as str]))

(def cofog-divisions
  {"01" {:cofog/code "01"
         :cofog/name "General public services"
         :cofog/name-ja "一般公共サービス"}
   "02" {:cofog/code "02"
         :cofog/name "Defence"
         :cofog/name-ja "防衛"}
   "03" {:cofog/code "03"
         :cofog/name "Public order and safety"
         :cofog/name-ja "公共秩序・安全"}
   "04" {:cofog/code "04"
         :cofog/name "Economic affairs"
         :cofog/name-ja "経済業務"}
   "05" {:cofog/code "05"
         :cofog/name "Environmental protection"
         :cofog/name-ja "環境保護"}
   "06" {:cofog/code "06"
         :cofog/name "Housing and community amenities"
         :cofog/name-ja "住宅・地域アメニティ"}
   "07" {:cofog/code "07"
         :cofog/name "Health"
         :cofog/name-ja "保健"}
   "08" {:cofog/code "08"
         :cofog/name "Recreation, culture and religion"
         :cofog/name-ja "娯楽・文化・宗教"}
   "09" {:cofog/code "09"
         :cofog/name "Education"
         :cofog/name-ja "教育"}
   "10" {:cofog/code "10"
         :cofog/name "Social protection"
         :cofog/name-ja "社会保護"}})

(def cofog-classes
  {"01.1" {:cofog/code "01.1" :cofog/parent "01" :cofog/name "Executive and legislative organs, financial and fiscal affairs, external affairs"}
   "01.2" {:cofog/code "01.2" :cofog/parent "01" :cofog/name "Foreign economic aid"}
   "01.3" {:cofog/code "01.3" :cofog/parent "01" :cofog/name "General services"}
   "01.7" {:cofog/code "01.7" :cofog/parent "01" :cofog/name "Public debt transactions"}
   "02.1" {:cofog/code "02.1" :cofog/parent "02" :cofog/name "Military defence"}
   "02.2" {:cofog/code "02.2" :cofog/parent "02" :cofog/name "Civil defence"}
   "03.1" {:cofog/code "03.1" :cofog/parent "03" :cofog/name "Police services"}
   "03.2" {:cofog/code "03.2" :cofog/parent "03" :cofog/name "Fire-protection services"}
   "03.3" {:cofog/code "03.3" :cofog/parent "03" :cofog/name "Law courts"}
   "04.1" {:cofog/code "04.1" :cofog/parent "04" :cofog/name "General economic, commercial and labour affairs"}
   "04.2" {:cofog/code "04.2" :cofog/parent "04" :cofog/name "Agriculture, forestry, fishing and hunting"}
   "04.3" {:cofog/code "04.3" :cofog/parent "04" :cofog/name "Fuel and energy"}
   "04.5" {:cofog/code "04.5" :cofog/parent "04" :cofog/name "Transport"}
   "04.6" {:cofog/code "04.6" :cofog/parent "04" :cofog/name "Communication"}
   "04.7" {:cofog/code "04.7" :cofog/parent "04" :cofog/name "Other industries"}
   "05.1" {:cofog/code "05.1" :cofog/parent "05" :cofog/name "Waste management"}
   "05.2" {:cofog/code "05.2" :cofog/parent "05" :cofog/name "Waste water management"}
   "05.3" {:cofog/code "05.3" :cofog/parent "05" :cofog/name "Pollution abatement"}
   "06.1" {:cofog/code "06.1" :cofog/parent "06" :cofog/name "Housing development"}
   "06.3" {:cofog/code "06.3" :cofog/parent "06" :cofog/name "Water supply"}
   "07.1" {:cofog/code "07.1" :cofog/parent "07" :cofog/name "Medical products, appliances and equipment"}
   "07.2" {:cofog/code "07.2" :cofog/parent "07" :cofog/name "Outpatient services"}
   "07.3" {:cofog/code "07.3" :cofog/parent "07" :cofog/name "Hospital services"}
   "08.1" {:cofog/code "08.1" :cofog/parent "08" :cofog/name "Recreational and sporting services"}
   "08.2" {:cofog/code "08.2" :cofog/parent "08" :cofog/name "Cultural services"}
   "09.1" {:cofog/code "09.1" :cofog/parent "09" :cofog/name "Pre-primary and primary education"}
   "09.2" {:cofog/code "09.2" :cofog/parent "09" :cofog/name "Secondary education"}
   "09.4" {:cofog/code "09.4" :cofog/parent "09" :cofog/name "Tertiary education"}
   "10.1" {:cofog/code "10.1" :cofog/parent "10" :cofog/name "Sickness and disability"}
   "10.2" {:cofog/code "10.2" :cofog/parent "10" :cofog/name "Old age"}
   "10.4" {:cofog/code "10.4" :cofog/parent "10" :cofog/name "Family and children"}
   "10.5" {:cofog/code "10.5" :cofog/parent "10" :cofog/name "Unemployment"}})

(def ministry-kind->cofog
  {:head-of-government ["01.1"]
   :finance ["01.1"]
   :treasury ["01.1"]
   :foreign ["01.1"]
   :defense ["02"]
   :defence ["02"]
   :interior ["03.1"]
   :justice ["03.3"]
   :economy ["04.1"]
   :commerce ["04.1"]
   :industry ["04.7"]
   :labour ["04.1" "10.5"]
   :labor ["04.1" "10.5"]
   :agriculture ["04.2"]
   :energy ["04.3"]
   :transport ["04.5"]
   :communications ["04.6"]
   :environment ["05"]
   :housing ["06.1"]
   :water ["06.3"]
   :health ["07"]
   :culture ["08.2"]
   :tourism ["04.7"]
   :education ["09"]
   :science ["09.4"]
   :social ["10"]
   :welfare ["10"]})

(defn normalize-code
  [code]
  (let [s (str/trim (str code))]
    (cond
      (re-matches #"\d" s) (str "0" s)
      (re-matches #"\d\.\d" s) (str "0" s)
      :else s)))

(defn division-code
  [code]
  (subs (normalize-code code) 0 2))

(defn cofog-entry
  [code]
  (let [code* (normalize-code code)]
    (or (get cofog-classes code*)
        (get cofog-divisions code*))))

(defn valid-code?
  [code]
  (boolean (cofog-entry code)))

(defn- text-token
  [unit]
  (str/lower
   (str (:gov.unit/id unit) " "
        (:gov.unit/name-en unit) " "
        (:gov.unit/name-local unit) " "
        (:gov.unit/name-romanized unit))))

(defn infer-ministry-kind
  [unit]
  (or (:gov.unit/ministry-kind unit)
      (some (fn [[kind patterns]]
              (when (some #(str/includes? (text-token unit) %) patterns)
                kind))
            {:defense ["defense" "defence" "防衛"]
             :foreign ["foreign" "外務"]
             :finance ["finance" "treasury" "財務" "税"]
             :interior ["interior" "home affairs" "内務" "総務"]
             :justice ["justice" "司法" "法務"]
             :health ["health" "保健" "厚生"]
             :education ["education" "文部" "教育"]
             :environment ["environment" "環境"]
             :agriculture ["agriculture" "農"]
             :transport ["transport" "交通" "運輸"]
             :energy ["energy" "資源" "エネルギー"]
             :culture ["culture" "文化"]
             :social ["social" "welfare" "福祉"]})))

(defn classify-unit
  "Return a normalized COFOG classification for a :gov.unit map.

  Explicit :gov.unit/cofog wins. If absent, ministry kind is inferred from an
  explicit :gov.unit/ministry-kind or conservative name/id heuristics."
  [unit]
  (let [explicit (seq (:gov.unit/cofog unit))
        kind (infer-ministry-kind unit)
        codes (or explicit (get ministry-kind->cofog kind))
        normalized (->> codes (map normalize-code) (filter valid-code?) vec)]
    {:gov.unit/id (:gov.unit/id unit)
     :gov.unit/level (:gov.unit/level unit)
     :gov.unit/ministry-kind kind
     :gov.unit/cofog normalized
     :cofog/divisions (->> normalized (map division-code) distinct vec)
     :cofog/source (if explicit :explicit :inferred)}))

(defn ministry-unit
  "Construct a ministry-level atlas row with COFOG attached.

  The caller supplies provenance and verification status; this helper only
  enforces the government-function classification shape."
  [{:keys [jurisdiction ministry-kind slug name-en name-local parent official-url
           wikidata sourcing provenance last-verified verification-status]}]
  (let [kind (keyword ministry-kind)
        id (str "gov." jurisdiction "." (or slug (name kind)))
        unit {:gov.unit/id id
              :gov.unit/atlas-did (str "did:web:etzhayyim.com:gov:" jurisdiction ":ministry:" (or slug (name kind)))
              :gov.unit/parent (or parent (str "gov." jurisdiction))
              :gov.unit/level :ministry
              :gov.unit/branch :executive
              :gov.unit/jurisdiction jurisdiction
              :gov.unit/ministry-kind kind
              :gov.unit/name-en name-en
              :gov.unit/name-local name-local
              :gov.unit/official-url official-url
              :gov.unit/wikidata wikidata
              :gov.unit/status :active
              :gov.unit/sourcing sourcing
              :gov.unit/provenance provenance
              :gov.unit/last-verified last-verified
              :gov.unit/verification-status verification-status}
        classification (classify-unit unit)]
    (assoc unit :gov.unit/cofog (:gov.unit/cofog classification))))

(defn classification-record
  [unit]
  (let [classification (classify-unit unit)]
    {:cofog.classification/unit-id (:gov.unit/id classification)
     :cofog.classification/unit-level (:gov.unit/level classification)
     :cofog.classification/ministry-kind (:gov.unit/ministry-kind classification)
     :cofog.classification/codes (:gov.unit/cofog classification)
     :cofog.classification/divisions (:cofog/divisions classification)
     :cofog.classification/source (:cofog/source classification)}))
