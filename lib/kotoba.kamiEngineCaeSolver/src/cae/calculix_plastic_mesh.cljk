(ns cae.calculix-plastic-mesh
  "Generate C3D8 material-nonlinearity meshes with a controlled strain gradient."
  (:require [kotoba.lang.text :as str]))

(defn- nid [n layer i j] (inc (+ (* layer (inc n) (inc n)) (* i (inc n)) j)))
(defn- csv [xs] (str/join ", " xs))
(defn- set-lines [xs] (map csv (partition-all 16 xs)))

(defn gradient-plastic-input
  [{:keys [divisions mean-displacement gradient youngs-modulus poisson-ratio]
    :or {mean-displacement 0.0025 gradient 0.003 youngs-modulus 210000.0 poisson-ratio 0.3}}]
  (when-not (pos? divisions) (throw (ex-info "positive plastic mesh divisions required" {:divisions divisions})))
  (let [n divisions nodes (for [layer (range 2) i (range (inc n)) j (range (inc n))]
                            [(nid n layer i j) (/ (double i) n) (/ (double j) n) (double layer)])
        elements (for [i (range n) j (range n)]
                   [(inc (+ (* i n) j))
                    (nid n 0 i j) (nid n 0 (inc i) j) (nid n 0 (inc i) (inc j)) (nid n 0 i (inc j))
                    (nid n 1 i j) (nid n 1 (inc i) j) (nid n 1 (inc i) (inc j)) (nid n 1 i (inc j))])
        all (map first nodes) base (for [i (range (inc n)) j (range (inc n))] (nid n 0 i j))
        top (for [i (range (inc n)) j (range (inc n))] (nid n 1 i j))
        uz (fn [i] (+ mean-displacement (* gradient (- (/ (double i) n) 0.5))))
        lines (concat
               ["*HEADING" "Kotoba CAE gradient elastoplastic PEEQ mesh sensitivity" "*NODE"]
               (map csv nodes) ["*ELEMENT, TYPE=C3D8, ELSET=SPECIMEN"] (map csv elements)
               ["*NSET, NSET=ALL"] (set-lines all) ["*NSET, NSET=BASE"] (set-lines base)
               ["*NSET, NSET=TOP"] (set-lines top)
               ["*SOLID SECTION, ELSET=SPECIMEN, MATERIAL=STEEL" "*MATERIAL, NAME=STEEL"
                "*ELASTIC" (csv [youngs-modulus poisson-ratio]) "*PLASTIC" "250., 0." "300., 0.01"
                "*BOUNDARY" "ALL, 1, 2, 0." "BASE, 3, 3, 0."]
               (for [i (range (inc n)) j (range (inc n))] (csv [(nid n 1 i j) 3 3 (uz i)]))
               ["*STEP, INC=200" "*STATIC" "0.02, 1., 1.e-6, 0.05"
                "*NODE PRINT, NSET=TOP, TOTALS=YES" "U, RF"
                "*EL PRINT, ELSET=SPECIMEN" "S, E, PEEQ"
                "*EL FILE" "PEEQ" "*END STEP"])]
    {:input (str (str/join "\n" lines) "\n") :divisions n
     :nodes (* 2 (inc n) (inc n)) :elements (* n n) :top-nodes (count top)}))
