(ns cae.sbse-geometry
  "NASA/Boeing Smooth-Body Separation Experiment parametric surface."
  (:require [kotoba.lang.text :as str]))

(def parameters
  {:L-m 0.9144 :x0-over-L 0.195 :z0-over-L 0.06 :h-over-L 0.085
   :source "NASA TMR SBSE parametric representation"})

(defn- erf
  "Portable Abramowitz-Stegun 7.1.26 approximation (max error ~1.5e-7)."
  [x]
  (let [sign (if (neg? x) -1.0 1.0) x (abs (double x))
        t (/ 1.0 (+ 1.0 (* 0.3275911 x)))
        poly (* t (+ 0.254829592 (* t (+ -0.284496736 (* t (+ 1.421413741
                 (* t (+ -1.453152027 (* t 1.061405429))))))))) ]
    (* sign (- 1.0 (* poly (#?(:clj Math/exp :cljs js/Math.exp) (- (* x x))))))))

(defn height-m
  "Return the ideal bump height at streamwise/spanwise coordinates in metres.
  x=0 is the apex and z=0 is tunnel centerline."
  ([x z] (height-m parameters x z))
  ([{:keys [L-m x0-over-L z0-over-L h-over-L]} x z]
   (let [x0 (* L-m x0-over-L) z0 (* L-m z0-over-L) h (* L-m h-over-L)
         shoulder (/ (+ 1.0 (erf (/ (- (/ L-m 2.0) (* 2.0 z0) (abs (double z))) z0))) 2.0)
         gaussian (#?(:clj Math/exp :cljs js/Math.exp) (- (let [q (/ (double x) x0)] (* q q))))]
     (* h shoulder gaussian))))

(defn surface-grid
  "Sample the ideal surface and return vertices plus consistently oriented triangles."
  [{:keys [nx nz x-min-m x-max-m z-min-m z-max-m]
    :or {nx 81 nz 81 x-min-m -0.9144 x-max-m 0.9144
         z-min-m -0.4572 z-max-m 0.4572}}]
  (when-not (and (> nx 1) (> nz 1) (< x-min-m x-max-m) (< z-min-m z-max-m))
    (throw (ex-info "valid SBSE surface-grid dimensions and bounds are required" {})))
  (let [vertex (fn [i j]
                 (let [x (+ x-min-m (* i (/ (- x-max-m x-min-m) (dec nx))))
                       z (+ z-min-m (* j (/ (- z-max-m z-min-m) (dec nz))))]
                   [x (height-m x z) z]))
        vertices (vec (for [i (range nx) j (range nz)] (vertex i j)))
        id (fn [i j] (+ (* i nz) j))
        triangles (vec (mapcat (fn [[i j]]
                                 [[(id i j) (id (inc i) j) (id (inc i) (inc j))]
                                  [(id i j) (id (inc i) (inc j)) (id i (inc j))]])
                               (for [i (range (dec nx)) j (range (dec nz))] [i j])))]
    {:format :sbse-parametric-surface-v1 :parameters parameters :nx nx :nz nz
     :vertices vertices :triangles triangles :vertex-count (count vertices)
     :triangle-count (count triangles)}))

(defn ascii-stl [surface]
  (let [v (:vertices surface)
        facet (fn [[a b c]]
                (str "  facet normal 0 0 0\n    outer loop\n"
                     (str/join "" (map #(str "      vertex " (str/join " " (map double (v %))) "\n") [a b c]))
                     "    endloop\n  endfacet\n"))]
    (str "solid nasa_sbse_ideal_bump\n" (str/join "" (map facet (:triangles surface)))
         "endsolid nasa_sbse_ideal_bump\n")))

(defn iges-summary
  "Audit the global header of the pinned as-designed MADCAP IGES halves."
  [text]
  (let [lines (str/split-lines text)
        global (str/join "" (filter #(re-find #"G\s*\d+$" %) (take 20 lines)))
        entity-128 (count (filter #(str/starts-with? (str/trim %) "128,") lines))]
    {:format :iges-header-summary-v1
     :madcap? (str/includes? global "MADCAP")
     :unit :inch :inch-unit-declared? (str/includes? global "4HINCH")
     :rational-b-spline-surface-records entity-128
     :line-count (count lines)}))
