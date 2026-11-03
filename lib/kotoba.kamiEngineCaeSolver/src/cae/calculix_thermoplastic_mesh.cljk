(ns cae.calculix-thermoplastic-mesh
  "Generate consistently refined 1x1xN coupled thermoplastic C3D8 meshes."
  (:require [kotoba.lang.text :as str]))

(defn- node-id [layer corner] (+ 1 (* 4 layer) corner))
(defn- csv [xs] (str/join ", " xs))
(defn- set-lines [xs] (map csv (partition-all 16 xs)))

(defn coupled-input [{:keys [layers steady-state?] :or {layers 2 steady-state? false}}]
  (when-not (and (integer? layers) (pos? layers) (even? layers))
    (throw (ex-info "a positive even thermoplastic layer count is required" {:layers layers})))
  (let [xy [[0.0 0.0] [1.0 0.0] [1.0 1.0] [0.0 1.0]]
        nodes (for [layer (range (inc layers)) corner (range 4)
                    :let [[x y] (nth xy corner)]]
                [(node-id layer corner) x y (/ (double layer) layers)])
        elements (for [layer (range layers)]
                   (into [(inc layer)]
                         (concat (map #(node-id layer %) (range 4))
                                 (map #(node-id (inc layer) %) (range 4)))))
        all (map first nodes) base (map #(node-id 0 %) (range 4))
        top (map #(node-id layers %) (range 4))
        midpoint (map #(node-id (quot layers 2) %) (range 4))
        lines (concat
               ["*HEADING" "Kotoba CAE coupled thermoplastic mesh convergence" "*NODE"]
               (map csv nodes) ["*ELEMENT, TYPE=C3D8, ELSET=SPECIMEN"] (map csv elements)
               ["*NSET, NSET=ALL"] (set-lines all) ["*NSET, NSET=BASE"] (set-lines base)
               ["*NSET, NSET=TOP"] (set-lines top) ["*NSET, NSET=MIDPOINT"] (set-lines midpoint)
               ["*SOLID SECTION, ELSET=SPECIMEN, MATERIAL=STEEL"
                "*MATERIAL, NAME=STEEL" "*DENSITY" "7.85e-9"
                "*CONDUCTIVITY" "0.045, 293.15" "0.035, 773.15"
                "*SPECIFIC HEAT" "4.70e8, 293.15" "6.00e8, 773.15"
                "*ELASTIC" "210000., 0.3, 293.15" "170000., 0.3, 773.15"
                "*EXPANSION, ZERO=293.15" "1.2e-5, 293.15" "1.5e-5, 773.15"
                "*PLASTIC" "250., 0., 293.15" "300., 0.01, 293.15"
                "180., 0., 773.15" "230., 0.01, 773.15"
                "*INITIAL CONDITIONS, TYPE=TEMPERATURE" "ALL, 293.15"
                "*BOUNDARY" "ALL, 1, 2, 0." "BASE, 3, 3, 0."
                "*STEP, NLGEOM, INC=300"
                (if steady-state? "*COUPLED TEMPERATURE-DISPLACEMENT, STEADY STATE"
                    "*COUPLED TEMPERATURE-DISPLACEMENT")
                "0.02, 1., 1.e-6, 0.05" "*BOUNDARY" "BASE, 11, 11, 293.15"
                "TOP, 11, 11, 773.15" "TOP, 3, 3, 0.003"
                "*NODE PRINT, NSET=TOP, TOTALS=YES" "U, RF"
                "*NODE PRINT, NSET=ALL" "NT" "*EL PRINT, ELSET=SPECIMEN"
                "S, E, PEEQ, HFL" "*EL FILE" "S, E, PEEQ, HFL"
                "*NODE FILE" "U, NT" "*END STEP"])]
    {:input (str (str/join "\n" lines) "\n") :layers layers :steady-state? steady-state?
     :nodes (* 4 (inc layers)) :elements layers :midpoint-nodes (vec midpoint)}))
