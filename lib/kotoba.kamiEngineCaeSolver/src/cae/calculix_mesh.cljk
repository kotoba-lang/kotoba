(ns cae.calculix-mesh
  "Clean-room structured C3D8 CalculiX mesh/case generation for convergence studies."
  (:require [kotoba.lang.text :as str]))

(defn node-id [ny nz i j k]
  (inc (+ (* i (inc ny) (inc nz)) (* j (inc nz)) k)))

(defn structured-c3d8
  [{:keys [nx ny nz length width height]}]
  (when-not (every? pos? [nx ny nz length width height])
    (throw (ex-info "positive mesh counts and dimensions required"
                    {:nx nx :ny ny :nz nz :length length :width width :height height})))
  (let [nodes (vec (for [i (range (inc nx)) j (range (inc ny)) k (range (inc nz))]
                     [(node-id ny nz i j k)
                      (* length (/ i nx)) (- (* width (/ j ny)) (/ width 2.0))
                      (- (* height (/ k nz)) (/ height 2.0))]))
        elements (vec
                  (for [i (range nx) j (range ny) k (range nz)]
                    [(inc (+ (* i ny nz) (* j nz) k))
                     (node-id ny nz i j k) (node-id ny nz (inc i) j k)
                     (node-id ny nz (inc i) (inc j) k) (node-id ny nz i (inc j) k)
                     (node-id ny nz i j (inc k)) (node-id ny nz (inc i) j (inc k))
                     (node-id ny nz (inc i) (inc j) (inc k)) (node-id ny nz i (inc j) (inc k))]))
        fixed (mapv #(node-id ny nz 0 (first %) (second %))
                    (for [j (range (inc ny)) k (range (inc nz))] [j k]))
        tip (mapv #(node-id ny nz nx (first %) (second %))
                  (for [j (range (inc ny)) k (range (inc nz))] [j k]))]
    {:nodes nodes :elements elements :fixed-nodes fixed :tip-nodes tip
     :element-count (* nx ny nz) :node-count (* (inc nx) (inc ny) (inc nz))
     :characteristic-h (/ width ny)}))

(defn- csv [values] (str/join ", " values))
(defn- set-lines [values] (map csv (partition-all 16 values)))

(defn cantilever-input
  [{:keys [nx ny nz length width height youngs-modulus poisson-ratio total-load]
    :or {length 10.0 width 1.0 height 1.0 youngs-modulus 210000.0
         poisson-ratio 0.3 total-load -100.0}}]
  (let [{:keys [nodes elements fixed-nodes tip-nodes] :as mesh}
        (structured-c3d8 {:nx nx :ny ny :nz nz :length length :width width :height height})
        load-per-node (/ total-load (count tip-nodes))
        lines (concat
               ["*HEADING" "Kotoba CAE C3D8 finite-deformation cantilever mesh convergence" "*NODE"]
               (map csv nodes)
               ["*ELEMENT, TYPE=C3D8, ELSET=BEAM"]
               (map csv elements)
               ["*NSET, NSET=FIXED"]
               (set-lines fixed-nodes)
               ["*NSET, NSET=TIP"]
               (set-lines tip-nodes)
               ["*SOLID SECTION, ELSET=BEAM, MATERIAL=ELASTIC"
                "*MATERIAL, NAME=ELASTIC" "*ELASTIC"
                (csv [youngs-modulus poisson-ratio])
                "*BOUNDARY" "FIXED, 1, 3, 0."
                "*STEP, NLGEOM=YES, INC=200" "*STATIC" "0.02, 1., 1.e-6, 0.05"
                "*CLOAD"]
               (map #(csv [% 3 load-per-node]) tip-nodes)
               ["*NODE PRINT, NSET=TIP" "U"
                "*NODE FILE" "U" "*END STEP"])]
    (assoc mesh :input (str (str/join "\n" lines) "\n")
           :total-load total-load :load-per-node load-per-node)))
