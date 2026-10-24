(ns icd10.chapters
  "The 22 ICD-10 chapter boundaries (A00-B99, C00-D48, ...) — structural
  navigation facts WHO publishes in the plain table of contents of every
  edition (see e.g. the WHO ICD-10 Online Browser's own chapter index).
  Deciding which chapter a given code falls in is a range comparison over
  these widely published boundaries; it is not a reproduction of the
  classification itself, which would require the actual disease/condition
  labels this repo deliberately does not carry — see README."
  (:require [icd10.code :as code]))

(def chapters
  "Each entry: Roman-numeral chapter number, the WHO-published title
  (structural table-of-contents text, not tabular-list content), and the
  inclusive `[start end]` category-code range (compared as [letter digits]
  pairs, since \"J9\" < \"J18\" as *categories* even though \"J9\" < \"J18\"
  is false as plain strings — see `chapter-for`)."
  [{:chapter "I" :title "Certain infectious and parasitic diseases" :range ["A00" "B99"]}
   {:chapter "II" :title "Neoplasms" :range ["C00" "D48"]}
   {:chapter "III" :title "Diseases of the blood and blood-forming organs and certain disorders involving the immune mechanism" :range ["D50" "D89"]}
   {:chapter "IV" :title "Endocrine, nutritional and metabolic diseases" :range ["E00" "E90"]}
   {:chapter "V" :title "Mental and behavioural disorders" :range ["F00" "F99"]}
   {:chapter "VI" :title "Diseases of the nervous system" :range ["G00" "G99"]}
   {:chapter "VII" :title "Diseases of the eye and adnexa" :range ["H00" "H59"]}
   {:chapter "VIII" :title "Diseases of the ear and mastoid process" :range ["H60" "H95"]}
   {:chapter "IX" :title "Diseases of the circulatory system" :range ["I00" "I99"]}
   {:chapter "X" :title "Diseases of the respiratory system" :range ["J00" "J99"]}
   {:chapter "XI" :title "Diseases of the digestive system" :range ["K00" "K93"]}
   {:chapter "XII" :title "Diseases of the skin and subcutaneous tissue" :range ["L00" "L99"]}
   {:chapter "XIII" :title "Diseases of the musculoskeletal system and connective tissue" :range ["M00" "M99"]}
   {:chapter "XIV" :title "Diseases of the genitourinary system" :range ["N00" "N99"]}
   {:chapter "XV" :title "Pregnancy, childbirth and the puerperium" :range ["O00" "O99"]}
   {:chapter "XVI" :title "Certain conditions originating in the perinatal period" :range ["P00" "P96"]}
   {:chapter "XVII" :title "Congenital malformations, deformations and chromosomal abnormalities" :range ["Q00" "Q99"]}
   {:chapter "XVIII" :title "Symptoms, signs and abnormal clinical and laboratory findings, not elsewhere classified" :range ["R00" "R99"]}
   {:chapter "XIX" :title "Injury, poisoning and certain other consequences of external causes" :range ["S00" "T98"]}
   {:chapter "XX" :title "External causes of morbidity and mortality" :range ["V01" "Y98"]}
   {:chapter "XXI" :title "Factors influencing health status and contact with health services" :range ["Z00" "Z99"]}
   {:chapter "XXII" :title "Codes for special purposes" :range ["U00" "U99"]}])

(defn- category-key
  "[letter digits-as-int] so range comparison is numeric on the digit pair,
  not lexicographic on the raw 3-char string -- lexicographic string
  comparison would put \"J9\" after \"J18\" (since \"9\" > \"1\" as the
  first differing character), which is wrong: as ICD-10 categories there
  is no J9, but the general form must still compare correctly wherever a
  1-digit boundary and a 2-digit one are compared, e.g. a caller-supplied
  partial code."
  [category3]
  [(subs category3 0 1) #?(:clj (Long/parseLong (subs category3 1 3))
                            :cljs (js/parseInt (subs category3 1 3) 10))])

(defn- in-range? [k [lo hi]]
  (let [lo-k (category-key lo) hi-k (category-key hi)]
    (and (<= 0 (compare k lo-k)) (<= 0 (compare hi-k k)))))

(defn chapter-for-category
  "The chapter map whose range contains `category3` (a 3-char category
  code like \"J18\"), or nil if none does (a structurally valid category
  letter+digit combination is not guaranteed to fall inside an allocated
  chapter block -- e.g. `A99` sits past Chapter I's published upper bound
  of B99... no wait: A-letter codes span into B, so this is more relevant
  for a letter like `C48`, which is not in Chapter I or II's exact digit
  span; returning nil rather than guessing is the honest answer)."
  [category3]
  (when (and (string? category3) (re-matches #"[A-Z][0-9]{2}" category3))
    (let [k (category-key category3)]
      (some #(when (in-range? k (:range %)) %) chapters))))

(defn chapter-for-code
  "Like chapter-for-category, but takes a full parsed code map (from
  icd10.code/parse) or a raw code string."
  [code-or-map]
  (let [m (if (string? code-or-map)
            (let [[tag v] (code/parse code-or-map)] (when (= tag :ok) v))
            code-or-map)]
    (when m (chapter-for-category (:category m)))))
