(ns cae.openfoam-bump
  "Static, auditable generation of the NASA TMR 2D bump spline for OpenFOAM."
  (:require [kotoba.lang.text :as str]))

(defn bump-height [x]
  (if (<= 0.3 x 1.2)
    (let [s (Math/sin (- (/ (* Math/PI x) 0.9) (/ Math/PI 3.0)))]
      (* 0.05 s s s s))
    0.0))

(defn spline-points
  ([] (spline-points 100))
  ([point-count]
   (when (< point-count 2) (throw (ex-info "bump spline requires at least two points" {:point-count point-count})))
   (mapv (fn [i]
           (let [x (+ 0.3 (* i (/ 0.9 (dec point-count))))]
             [x (bump-height x)]))
         (range point-count))))

(defn static-block-mesh-dict
  "Replace the tutorial's dynamic `#codeStream` edge generator with explicit
  spline coordinates. The rest of the digest-pinned tutorial is unchanged."
  [tutorial-dict]
  (let [points (spline-points)
        point-lines (fn [z] (str/join "\n" (map (fn [[x y]] (format "        (%.12f %.12f %s)" x y z)) points)))
        static (str "edges\n(\n    spline 2 3\n    (\n" (point-lines "1")
                    "\n    )\n    spline 14 15\n    (\n" (point-lines "-1") "\n    )\n);\n\n")
        replaced (str/replace tutorial-dict #"(?s)edges #codeStream\s*\{.*?\n\};\s*\n\n" static)]
    (when (= tutorial-dict replaced)
      (throw (ex-info "tutorial blockMeshDict did not contain the expected codeStream" {})))
    replaced))
