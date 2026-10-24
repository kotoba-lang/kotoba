(ns vegetation.taxonomy
  "Biological taxonomy -> procedural generation parameters.

  Restored from `kami-vegetation/src/taxonomy.rs` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as part of
  the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Instead of hardcoding species meshes, generation patterns are derived
  from a hierarchical botanical classification (division / growth-habit /
  leaf-arrangement / leaf-shape / canopy-shape). Adding a new species means
  choosing keyword values + parameter tuning, not writing a new mesh fn.

  Also ports `OwnedTaxonomicProfile` (the dynamic / remote-catalog variant
  fed by `app.etzhayyim.apps.seibutsu.renderProfile` JSON responses) plus a
  minimal zero-dependency JSON reader sufficient to decode that wire
  format (this crate deliberately avoids any networking or 3rd-party JSON
  library dependency, matching the original Rust crate's no-networking-by-
  design constraint).")

;; ---------------------------------------------------------------------
;; Enums (Rust `enum` -> CLJC keyword + documented value set)
;; ---------------------------------------------------------------------

(def divisions
  "Plant division (highest rank that shapes morphology)."
  #{:bryophyta :pteridophyta :gymnospermae :angiospermae})

(def growth-habits
  "Overall plant architecture."
  #{:grass :herb :shrub :tree :succulent :mat :climber})

(def leaf-arrangements
  "Leaf arrangement pattern on the stem."
  #{:alternate :opposite :whorled :rosette :basal :none})

(def leaf-shapes
  "Leaf / foliage unit shape (drives per-leaf mesh geometry)."
  #{:linear :lanceolate :ovate :palmate :pinnate :needle :succulent :scale})

(def canopy-shapes
  "Overall silhouette shape of the foliage mass."
  #{:blade :fan :dome :cone :radial :column :carpet})

;; ---------------------------------------------------------------------
;; TaxonomicProfile — full procedural generation profile
;; ---------------------------------------------------------------------
;; Keys mirror the Rust struct fields 1:1 (snake_case -> kebab-case):
;;   :common-name :division :habit :arrangement :leaf-shape :canopy
;;   :height-range :stem-radius-base :stem-radius-top :leaf-count
;;   :leaf-size :color-base :color-tip

;; ── Preset catalog ──

(defn grass
  "Grass (Poaceae — Angiospermae, Grass habit)."
  []
  {:common-name "grass"
   :division :angiospermae
   :habit :grass
   :arrangement :basal
   :leaf-shape :linear
   :canopy :blade
   :height-range [0.7 1.4]
   :stem-radius-base 0.0
   :stem-radius-top 0.0
   :leaf-count 3
   :leaf-size 0.18
   :color-base [0.18 0.42 0.08]
   :color-tip [0.42 0.68 0.15]})

(defn fern
  "Fern (Pteridophyta, Herb habit)."
  []
  {:common-name "fern"
   :division :pteridophyta
   :habit :herb
   :arrangement :alternate
   :leaf-shape :pinnate
   :canopy :fan
   :height-range [0.8 1.5]
   :stem-radius-base 0.04
   :stem-radius-top 0.02
   :leaf-count 5
   :leaf-size 0.35
   :color-base [0.12 0.28 0.04]
   :color-tip [0.3 0.55 0.12]})

(defn palm
  "Palm tree (Angiospermae, Tree habit, radial canopy)."
  []
  {:common-name "palm"
   :division :angiospermae
   :habit :tree
   :arrangement :whorled
   :leaf-shape :pinnate
   :canopy :radial
   :height-range [0.85 1.25]
   :stem-radius-base 0.08
   :stem-radius-top 0.06
   :leaf-count 7
   :leaf-size 0.55
   :color-base [0.35 0.22 0.08]
   :color-tip [0.18 0.45 0.1]})

(defn conifer
  "Conifer (Gymnospermae, Tree habit, cone canopy)."
  []
  {:common-name "conifer"
   :division :gymnospermae
   :habit :tree
   :arrangement :whorled
   :leaf-shape :needle
   :canopy :cone
   :height-range [0.7 1.3]
   :stem-radius-base 0.09
   :stem-radius-top 0.03
   :leaf-count 3
   :leaf-size 0.42
   :color-base [0.25 0.18 0.08]
   :color-tip [0.12 0.3 0.08]})

(defn bush
  "Broadleaf bush (Angiospermae, Shrub habit, dome canopy)."
  []
  {:common-name "bush"
   :division :angiospermae
   :habit :shrub
   :arrangement :alternate
   :leaf-shape :ovate
   :canopy :dome
   :height-range [0.8 1.4]
   :stem-radius-base 0.06
   :stem-radius-top 0.04
   :leaf-count 6
   :leaf-size 0.33
   :color-base [0.15 0.28 0.06]
   :color-tip [0.28 0.48 0.1]})

(defn cactus
  "Columnar cactus (Angiospermae, Succulent habit, Column canopy)."
  []
  {:common-name "cactus"
   :division :angiospermae
   :habit :succulent
   :arrangement :none
   :leaf-shape :succulent
   :canopy :column
   :height-range [0.6 1.3]
   :stem-radius-base 0.22
   :stem-radius-top 0.18
   :leaf-count 0
   :leaf-size 0.0
   :color-base [0.22 0.38 0.18]
   :color-tip [0.32 0.52 0.22]})

(defn moss
  "Ground moss (Bryophyta, Mat habit, carpet canopy)."
  []
  {:common-name "moss"
   :division :bryophyta
   :habit :mat
   :arrangement :none
   :leaf-shape :scale
   :canopy :carpet
   :height-range [0.15 0.25]
   :stem-radius-base 0.0
   :stem-radius-top 0.0
   :leaf-count 1
   :leaf-size 0.45
   :color-base [0.16 0.30 0.08]
   :color-tip [0.32 0.54 0.14]})

(defn default-catalog
  "Standard catalog of 7 profiles."
  []
  [(grass) (fern) (palm) (conifer) (bush) (cactus) (moss)])

;; ---------------------------------------------------------------------
;; Remote catalog (seibutsu.etzhayyim.com bridge)
;; ---------------------------------------------------------------------
;; `kami-vegetation` has no networking by design (Rust core, runs in WASM).
;; The browser shell fetches `app.etzhayyim.apps.seibutsu.renderProfile` for
;; each species DID and feeds the resulting JSON through `from-json-str`.
;; `OwnedTaxonomicProfile` in the original Rust decouples the engine from
;; the static `&'static str` common-name of `TaxonomicProfile`; in CLJC
;; there is no such distinction (strings are always owned), so the same
;; map shape is reused for both — `from-json-str` simply returns a
;; TaxonomicProfile-shaped map.

(defn- parse-division [s]
  (case s
    "bryophyta" :bryophyta
    "pteridophyta" :pteridophyta
    "gymnospermae" :gymnospermae
    :angiospermae))

(defn- parse-habit [s]
  (case s
    "grass" :grass
    "herb" :herb
    "shrub" :shrub
    "tree" :tree
    "succulent" :succulent
    "mat" :mat
    "climber" :climber
    :herb))

(defn- parse-arrangement [s]
  (case s
    "alternate" :alternate
    "opposite" :opposite
    "whorled" :whorled
    "rosette" :rosette
    "basal" :basal
    :none))

(defn- parse-leaf-shape [s]
  (case s
    "linear" :linear
    "lanceolate" :lanceolate
    "ovate" :ovate
    "palmate" :palmate
    "pinnate" :pinnate
    "needle" :needle
    "succulent" :succulent
    :scale))

(defn- parse-canopy [s]
  (case s
    "blade" :blade
    "fan" :fan
    "dome" :dome
    "cone" :cone
    "radial" :radial
    "column" :column
    :carpet))

;; ── Minimal zero-dependency JSON reader ──
;; Sufficient to decode the flat camelCase object shape produced by
;; `seibutsu.renderProfile` (strings, numbers, arrays, nested objects).
;; Not a general-purpose JSON library.

(defn- ws-char? [c] (contains? #{\space \tab \newline \return} c))

(defn- digit-char? [c]
  #?(:clj (Character/isDigit ^char c)
     :cljs (contains? #{\0 \1 \2 \3 \4 \5 \6 \7 \8 \9} c)))

(defn- skip-ws* [s i]
  (let [n (count s)]
    (loop [i i]
      (if (and (< i n) (ws-char? (nth s i)))
        (recur (inc i))
        i))))

(declare parse-value)

(defn- parse-string [s i]
  (let [n (count s)]
    (loop [i (inc i) acc []]
      (let [c (nth s i)]
        (cond
          (= c \") [(apply str acc) (inc i)]
          (= c \\) (let [nc (nth s (inc i))
                         ch (case nc \n \newline \t \tab \r \return \" \" \\ \\ \/ \/ nc)]
                     (recur (+ i 2) (conj acc ch)))
          :else (recur (inc i) (conj acc c)))))))

(defn- parse-number [s i]
  (let [n (count s)]
    (loop [j i]
      (if (and (< j n) (or (digit-char? (nth s j))
                            (contains? #{\- \+ \. \e \E} (nth s j))))
        (recur (inc j))
        [(#?(:clj Double/parseDouble :cljs js/parseFloat) (subs s i j)) j]))))

(defn- parse-array [s i]
  (let [i (skip-ws* s (inc i))]
    (if (= (nth s i) \])
      [[] (inc i)]
      (loop [i i acc []]
        (let [[v i] (parse-value s i)
              i (skip-ws* s i)
              c (nth s i)]
          (if (= c \,)
            (recur (skip-ws* s (inc i)) (conj acc v))
            [(conj acc v) (inc i)]))))))

(defn- parse-object [s i]
  (let [i (skip-ws* s (inc i))]
    (if (= (nth s i) \})
      [{} (inc i)]
      (loop [i i acc {}]
        (let [i (skip-ws* s i)
              [k i] (parse-string s i)
              i (skip-ws* s i)
              i (inc i) ; skip ':'
              i (skip-ws* s i)
              [v i] (parse-value s i)
              i (skip-ws* s i)
              c (nth s i)
              acc' (assoc acc k v)]
          (if (= c \,)
            (recur (skip-ws* s (inc i)) acc')
            [acc' (inc i)]))))))

(defn- parse-value [s i]
  (let [i (skip-ws* s i)
        c (nth s i)]
    (cond
      (= c \") (parse-string s i)
      (= c \{) (parse-object s i)
      (= c \[) (parse-array s i)
      (= (subs s i (min (count s) (+ i 4))) "true") [true (+ i 4)]
      (= (subs s i (min (count s) (+ i 5))) "false") [false (+ i 5)]
      (= (subs s i (min (count s) (+ i 4))) "null") [nil (+ i 4)]
      :else (parse-number s i))))

(defn parse-json
  "Minimal zero-dependency JSON reader (object/array/string/number/bool/null).
   Sufficient for `seibutsu.renderProfile` response decoding."
  [s]
  (first (parse-value s 0)))

(defn from-json-map
  "Build a TaxonomicProfile-shaped map from a decoded camelCase JSON map
   (already parsed, e.g. via `parse-json`), matching the wire format of
   `app.etzhayyim.apps.seibutsu.renderProfile`."
  [m]
  (let [take-f (fn [k] (double (get m k 0.0)))
        take-u (fn [k] (long (get m k 0)))
        take-s (fn [k] (get m k ""))
        arr3 (fn [k] (let [a (get m k)] (if a (vec (take 3 (map double a))) [0.0 0.0 0.0])))
        arr2 (fn [k] (let [a (get m k)] (if a (vec (take 2 (map double a))) [0.0 1.0])))]
    {:common-name (take-s "commonName")
     :division (parse-division (take-s "division"))
     :habit (parse-habit (take-s "habit"))
     :arrangement (parse-arrangement (take-s "arrangement"))
     :leaf-shape (parse-leaf-shape (take-s "leafShape"))
     :canopy (parse-canopy (take-s "canopy"))
     :height-range (arr2 "heightRange")
     :stem-radius-base (take-f "stemRadiusBase")
     :stem-radius-top (take-f "stemRadiusTop")
     :leaf-count (take-u "leafCount")
     :leaf-size (take-f "leafSize")
     :color-base (arr3 "colorBase")
     :color-tip (arr3 "colorTip")}))

(defn from-json-str
  "Parse a single `seibutsu.renderProfile` response (camelCase JSON string)."
  [s]
  (from-json-map (parse-json s)))

;; ---------------------------------------------------------------------
;; RemoteCatalog — runtime catalog built from presets or renderProfile JSON
;; ---------------------------------------------------------------------

(defn remote-catalog-from-default
  "Runtime catalog seeded from the static presets."
  []
  {:profiles (default-catalog)})

(defn remote-catalog-push-json
  "Push one `renderProfile` JSON response into the catalog."
  [catalog json-str]
  (update catalog :profiles (fnil conj []) (from-json-str json-str)))
