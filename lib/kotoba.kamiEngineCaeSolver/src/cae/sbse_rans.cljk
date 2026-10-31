(ns cae.sbse-rans
  "Auditable OpenFOAM k-omega SST case generation for the NASA SBSE tunnel."
  (:require [kotoba.lang.text :as str]))

(def default-experiment
  {:velocity-m-s 34.59 :pressure-pa 99000.0 :temperature-c 21.3
   :relative-humidity 0.81 :turbulence-intensity 0.0005
   :turbulence-length-scale-m 0.009144})

(defn flow-conditions
  "Derive moist-air and turbulence inlet properties. Humidity uses the Buck
  saturation-pressure equation; dynamic viscosity uses Sutherland dry air."
  [{:keys [velocity-m-s pressure-pa temperature-c relative-humidity
           turbulence-intensity turbulence-length-scale-m] :as input}]
  (when-not (and (pos? velocity-m-s) (pos? pressure-pa)
                 (<= 0.0 relative-humidity 1.0) (pos? turbulence-intensity)
                 (pos? turbulence-length-scale-m))
    (throw (ex-info "valid SBSE flow conditions are required" {:input input})))
  (let [temperature-k (+ temperature-c 273.15)
        saturation-pa (* 611.21 (Math/exp (* (- 18.678 (/ temperature-c 234.5))
                                               (/ temperature-c (+ 257.14 temperature-c)))))
        vapor-pa (* relative-humidity saturation-pa)
        dry-pa (- pressure-pa vapor-pa)
        density (+ (/ dry-pa (* 287.058 temperature-k))
                   (/ vapor-pa (* 461.495 temperature-k)))
        dynamic-viscosity (* 1.458e-6 (/ (Math/pow temperature-k 1.5)
                                           (+ temperature-k 110.4)))
        nu (/ dynamic-viscosity density)
        k (* 1.5 (Math/pow (* velocity-m-s turbulence-intensity) 2.0))
        omega (/ (Math/sqrt k) (* (Math/pow 0.09 0.25) turbulence-length-scale-m))]
    (merge input {:temperature-k temperature-k :saturation-vapor-pressure-pa saturation-pa
                  :vapor-pressure-pa vapor-pa :density-kg-m3 density
                  :dynamic-viscosity-pa-s dynamic-viscosity :kinematic-viscosity-m2-s nu
                  :turbulent-kinetic-energy-m2-s2 k :specific-dissipation-rate-s-1 omega
                  :reynolds-number-length-0.9144 (/ (* velocity-m-s 0.9144) nu)})))

(defn- header [class object]
  (format "FoamFile\n{\n    format ascii;\n    class %s;\n    object %s;\n}\n" class object))
(def walls ["floorBump" "ceiling" "sideA" "sideB"])
(defn- wall-fields [body] (str/join "\n" (map #(format "    %s { %s }" % body) walls)))

(defn fields [conditions]
  (let [u (:velocity-m-s conditions) k (:turbulent-kinetic-energy-m2-s2 conditions)
        omega (:specific-dissipation-rate-s-1 conditions)]
    {"U" (str (header "volVectorField" "U")
               "dimensions [0 1 -1 0 0 0 0];\ninternalField uniform (" u " 0 0);\nboundaryField\n{\n"
               "    inlet { type fixedValue; value uniform (" u " 0 0); }\n"
               "    outlet { type inletOutlet; inletValue uniform (0 0 0); value uniform (" u " 0 0); }\n"
               (wall-fields "type noSlip;") "\n}\n")
     "p" (str (header "volScalarField" "p")
               "dimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\nboundaryField\n{\n"
               "    inlet { type zeroGradient; }\n    outlet { type fixedValue; value uniform 0; }\n"
               (wall-fields "type zeroGradient;") "\n}\n")
     "k" (str (header "volScalarField" "k")
               "dimensions [0 2 -2 0 0 0 0];\ninternalField uniform " k ";\nboundaryField\n{\n"
               "    inlet { type fixedValue; value uniform " k "; }\n"
               "    outlet { type inletOutlet; inletValue uniform " k "; value uniform " k "; }\n"
               (wall-fields "type kqRWallFunction; value uniform 0;") "\n}\n")
     "omega" (str (header "volScalarField" "omega")
                   "dimensions [0 0 -1 0 0 0 0];\ninternalField uniform " omega ";\nboundaryField\n{\n"
                   "    inlet { type fixedValue; value uniform " omega "; }\n"
                   "    outlet { type inletOutlet; inletValue uniform " omega "; value uniform " omega "; }\n"
                   (wall-fields "type omegaWallFunction; value uniform 1;") "\n}\n")
     "nut" (str (header "volScalarField" "nut")
                 "dimensions [0 2 -1 0 0 0 0];\ninternalField uniform 0;\nboundaryField\n{\n"
                 "    inlet { type calculated; value uniform 0; }\n"
                 "    outlet { type calculated; value uniform 0; }\n"
                 (wall-fields (str "type " (if (= :low-re (:wall-treatment conditions))
                                              "nutLowReWallFunction" "nutkWallFunction")
                                   "; value uniform 0;")) "\n}\n")}))

(defn dictionaries [conditions]
  {"constant/transportProperties"
   (str (header "dictionary" "transportProperties") "transportModel Newtonian;\nnu [0 2 -1 0 0 0 0] "
        (:kinematic-viscosity-m2-s conditions) ";\n")
   "constant/turbulenceProperties"
   (str (header "dictionary" "turbulenceProperties")
        "simulationType RAS;\nRAS { RASModel kOmegaSST; turbulence on; printCoeffs on; }\n")
   "system/controlDict"
   (str (header "dictionary" "controlDict")
        "application simpleFoam;\nstartFrom startTime;\nstartTime 0;\nstopAt endTime;\nendTime 5000;\ndeltaT 1;\nwriteControl timeStep;\nwriteInterval 250;\npurgeWrite 2;\nwriteFormat ascii;\nrunTimeModifiable false;\nfunctions\n{\n"
        "  wallShear { type wallShearStress; libs (fieldFunctionObjects); patches (floorBump); writeControl timeStep; writeInterval 250; }\n"
        "  yPlusField { type yPlus; libs (fieldFunctionObjects); writeControl timeStep; writeInterval 250; }\n}\n")
   "system/fvSchemes"
   (str (header "dictionary" "fvSchemes")
        "ddtSchemes { default steadyState; }\ngradSchemes { default cellLimited Gauss linear 1; }\n"
        "divSchemes { default none; div(phi,U) bounded Gauss "
        (if (= :low-re (:wall-treatment conditions)) "upwind" "linearUpwind grad(U)")
        "; div(phi,k) bounded Gauss upwind; div(phi,omega) bounded Gauss upwind; div((nuEff*dev2(T(grad(U))))) Gauss linear; }\n"
        "laplacianSchemes { default Gauss linear limited 0.5; }\ninterpolationSchemes { default linear; }\nsnGradSchemes { default limited 0.5; }\nwallDist { method meshWave; }\n")
   "system/fvSolution"
   (str (header "dictionary" "fvSolution")
        "solvers\n{\n  p { solver GAMG; tolerance 1e-8; relTol 0.05; smoother GaussSeidel; }\n"
        "  Phi { solver GAMG; tolerance 1e-8; relTol 0; smoother GaussSeidel; }\n"
        "  \"(U|k|omega)\" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0.05; }\n}\n"
        "SIMPLE\n{\n  nNonOrthogonalCorrectors 1;\n  consistent yes"
        ";\n  residualControl { p 1e-5; U 1e-5; k 1e-5; omega 1e-5; }\n}\n"
        "relaxationFactors { fields { p 0.3; } equations { U 0.7; k 0.7; omega 0.7; } }\n")})

(defn case-files [experiment]
  (let [conditions (flow-conditions experiment)]
    {:conditions conditions :files (merge (into {} (map (fn [[n v]] [(str "0/" n) v]) (fields conditions)))
                                          (dictionaries conditions))}))

(defn skin-friction-coefficient [wall-shear-x velocity-m-s]
  (/ (* 2.0 wall-shear-x) (* velocity-m-s velocity-m-s)))

(defn experimental-x->mesh-m [x-mm] (- (/ x-mm 1000.0) 0.9144))

(defn parse-ofi
  "Parse the seven numeric columns X,Y,Z,dX,dZ,Cf,e_Cf from a NASA OFI file."
  [text]
  (->> (str/split-lines text)
       (keep (fn [line]
               (let [columns (str/split (str/trim line) #"\s+")]
                 (when (and (= 7 (count columns)) (re-matches #"[-+0-9.]+" (first columns)))
                   (let [[x y z dx dz cf uncertainty] (mapv #(Double/parseDouble %) columns)]
                     {:x-mm x :y-mm y :z-mm z :dx-mm dx :dz-mm dz
                      :cf cf :cf-uncertainty uncertainty})))))
       vec))

(defn patch-values
  "Read a scalar or vector nonuniform boundary list from an ASCII OpenFOAM field."
  [text patch-name]
  (let [block (some-> (re-find (re-pattern (str "(?s)\\n\\s*" (java.util.regex.Pattern/quote patch-name)
                                                "\\s*\\{(.*?)\\n\\s*\\}")) text) second)
        [_ declared body] (when block (re-find #"(?s)nonuniform List<(?:scalar|vector)>\s+(\d+)\s*\((.*?)\)\s*;" block))
        rows (when body (->> (str/split-lines body) (map str/trim) (remove str/blank?)))]
    (when-not (= (some-> declared Long/parseLong) (count rows))
      (throw (ex-info "OpenFOAM boundary list count mismatch" {:patch patch-name :declared declared :actual (count rows)})))
    (mapv (fn [row]
            (if (str/starts-with? row "(")
              (mapv #(Double/parseDouble %) (str/split (subs row 1 (dec (count row))) #"\s+"))
              (Double/parseDouble row))) rows)))

(defn correlate-ofi
  "Nearest wall-face comparison. The metric is intentionally fail-closed and
  reports uncertainty coverage; it does not qualify a coarse grid by itself."
  [ofi-points faces velocity-m-s]
  (let [matches (mapv (fn [{:keys [x-mm z-mm cf cf-uncertainty] :as point}]
                        (let [x (experimental-x->mesh-m x-mm) z (/ z-mm 1000.0)
                              face (apply min-key (fn [{fx :x fz :z}]
                                                    (+ (Math/pow (- fx x) 2) (Math/pow (- fz z) 2))) faces)
                              predicted (skin-friction-coefficient (:shear-x face) velocity-m-s)
                              error (- predicted cf)]
                          (assoc point :mesh-x-m x :mesh-z-m z :predicted-cf predicted :error error
                                 :normalized-error (/ (Math/abs error) cf-uncertainty)
                                 :face-distance-m (Math/sqrt (+ (Math/pow (- (:x face) x) 2)
                                                                 (Math/pow (- (:z face) z) 2))))))
                      ofi-points)
        n (count matches)
        rmse (Math/sqrt (/ (reduce + (map #(Math/pow (:error %) 2) matches)) n))
        covered (count (filter #(<= (:normalized-error %) 1.0) matches))]
    {:sample-count n :rmse-cf rmse :within-experimental-uncertainty-fraction (/ covered (double n))
     :maximum-face-distance-m (apply max (map :face-distance-m matches)) :matches matches}))
