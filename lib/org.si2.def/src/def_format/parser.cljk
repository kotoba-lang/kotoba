(ns def-format.parser
  "Simplified line/section-based DEF (Design Exchange Format) parser (Si2,
  Silicon Integration Initiative, si2.org). Recognizes a practical subset
  of DEF syntax: DESIGN/UNITS/DIEAREA headers, COMPONENTS placement, NETS
  connectivity + simplified routed-wire geometry, and ROW/TRACKS
  placement-grid statements. Not full DEF grammar conformance (no
  SPECIALNETS, GCELLGRID, VIAS, PROPERTYDEFINITIONS, ...). Mirrors
  kotoba-lang/org-si2-lef's parse-lef in structure."
  (:require [kotoba.lang.text :as str]
            [def-format.component :as component]
            [def-format.net :as net]
            [def-format.row :as row]))

(defn- strip-semi [s] (str/replace (str s) #";$" ""))

(defn- parse-int [s default]
  (try #?(:clj (Long/parseLong (strip-semi s))
          :cljs (js/parseInt (strip-semi s) 10))
       (catch #?(:clj Exception :cljs js/Error) _ default)))

(defn- parse-paren-groups
  "From `tokens` starting at index `i`, consume `( a b )` groups while the
  current token is \"(\". Returns `[pairs next-index]`; used for both
  NETS instance/pin connections and routed-wire points, which share this
  shape."
  [tokens i]
  (loop [i i pairs []]
    (if (and (< i (count tokens)) (= "(" (nth tokens i)))
      (recur (+ i 4) (conj pairs [(nth tokens (+ i 1)) (nth tokens (+ i 2))]))
      [pairs i])))

(defn- component-status [s]
  (case (str/upper (strip-semi s))
    "PLACED" :placed "FIXED" :fixed "COVER" :cover "UNPLACED" :unplaced :unplaced))

(defn- parse-component-line
  "- <instance-name> <cell-ref> + PLACED ( x y ) <orientation> ; (or
  FIXED/COVER, or + UNPLACED ; with no location/orientation)."
  [tokens]
  (let [instance-name (nth tokens 1)
        cell-ref (nth tokens 2)
        status (component-status (nth tokens 4 "UNPLACED"))]
    (if (= status :unplaced)
      (component/component instance-name cell-ref status nil nil)
      (component/component instance-name cell-ref status
                            [(parse-int (nth tokens 6) 0) (parse-int (nth tokens 7) 0)]
                            (strip-semi (nth tokens 9 ""))))))

(defn- parse-net-line
  "- <name> ( inst pin ) ( inst pin ) ... [+ ROUTED <layer> ( x y ) ... ] ;"
  [tokens]
  (let [name (nth tokens 1)
        [conn-pairs i] (parse-paren-groups tokens 2)
        connections (mapv (fn [[inst pin]] (net/connection inst (strip-semi pin))) conn-pairs)
        routed (if (and (< (inc i) (count tokens))
                        (= "+" (nth tokens i)) (= "ROUTED" (nth tokens (inc i))))
                 (let [layer (nth tokens (+ i 2))
                       [pt-pairs _] (parse-paren-groups tokens (+ i 3))
                       points (mapv (fn [[x y]] [(parse-int x 0) (parse-int y 0)]) pt-pairs)]
                   [(net/routed-wire layer points)])
                 [])]
    (net/net name connections routed)))

(defn- parse-row-line
  "ROW <name> <site> <x> <y> <orient> DO <n> BY 1 STEP <step> 0 ;"
  [tokens]
  (row/row (nth tokens 1) (nth tokens 2)
           [(parse-int (nth tokens 3) 0) (parse-int (nth tokens 4) 0)]
           (nth tokens 5)
           (parse-int (nth tokens 7) 0)
           (parse-int (nth tokens 11) 0)))

(defn- parse-tracks-line
  "TRACKS <dir> <start> DO <count> STEP <step> LAYER <layer> ;"
  [tokens]
  (row/track (strip-semi (nth tokens 8))
             (case (str/upper (nth tokens 1)) "X" :x "Y" :y :x)
             (parse-int (nth tokens 2) 0)
             (parse-int (nth tokens 6) 0)
             (parse-int (nth tokens 4) 0)))

(defn parse-def
  "Parse a simplified DEF format string. Returns
  `[:ok {:design {...} :components [...] :nets [...] :rows [...] :tracks [...]}]`."
  [input]
  (loop [lines (str/split-lines input)
         section :top
         design {}
         components []
         nets []
         rows []
         tracks []]
    (if (empty? lines)
      [:ok {:design design :components components :nets nets :rows rows :tracks tracks}]
      (let [trimmed (str/trim (first lines))
            more (rest lines)
            tokens (when-not (str/blank? trimmed) (str/split trimmed #"\s+"))]
        (if (empty? tokens)
          (recur more section design components nets rows tracks)
          (case section
            :components
            (cond
              (= tokens ["END" "COMPONENTS"])
              (recur more :top design components nets rows tracks)

              (= (nth tokens 0) "-")
              (recur more section design (conj components (parse-component-line tokens)) nets rows tracks)

              :else (recur more section design components nets rows tracks))

            :nets
            (cond
              (= tokens ["END" "NETS"])
              (recur more :top design components nets rows tracks)

              (= (nth tokens 0) "-")
              (recur more section design components (conj nets (parse-net-line tokens)) rows tracks)

              :else (recur more section design components nets rows tracks))

            ;; :top
            (case (nth tokens 0)
              "DESIGN"
              (recur more section (assoc design :name (strip-semi (nth tokens 1))) components nets rows tracks)

              "UNITS"
              (recur more section (assoc design :units-distance-microns (parse-int (nth tokens 3) 1000))
                     components nets rows tracks)

              "DIEAREA"
              (recur more section
                     (assoc design :die-area [(parse-int (nth tokens 2) 0) (parse-int (nth tokens 3) 0)
                                               (parse-int (nth tokens 6) 0) (parse-int (nth tokens 7) 0)])
                     components nets rows tracks)

              "COMPONENTS" (recur more :components design components nets rows tracks)
              "NETS" (recur more :nets design components nets rows tracks)
              "ROW" (recur more section design components nets (conj rows (parse-row-line tokens)) tracks)
              "TRACKS" (recur more section design components nets rows (conj tracks (parse-tracks-line tokens)))

              (recur more section design components nets rows tracks))))))))
