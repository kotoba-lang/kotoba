(ns cae.sbse-urans
  "Transient PIMPLE/URANS dictionaries and statistical gates for NASA SBSE."
  (:require [cae.sbse-rans :as rans]))

(def domain-length-m 2.7432)
(def maximum-turbulence-stable-dt-s 2.0e-5)
(def minimum-warmup-flow-throughs 3.0)
(def minimum-average-flow-throughs 5.0)

(defn flow-through-time-s [velocity-m-s] (/ domain-length-m velocity-m-s))

(defn temporal-coverage
  "Assess whether transient removal and averaging span enough domain flow-throughs.
  This is independent of statistical stationarity: both gates must pass."
  ([run velocity-m-s]
   (temporal-coverage run velocity-m-s
                      {:minimum-warmup-flow-throughs minimum-warmup-flow-throughs
                       :minimum-average-flow-throughs minimum-average-flow-throughs}))
  ([{:keys [end-time-s average-start-s]}
    velocity-m-s
    {:keys [minimum-warmup-flow-throughs minimum-average-flow-throughs]}]
   (when-not (and (pos? velocity-m-s) (pos? minimum-warmup-flow-throughs)
                  (pos? minimum-average-flow-throughs))
     (throw (ex-info "invalid SBSE URANS temporal coverage controls"
                     {:velocity-m-s velocity-m-s
                      :minimum-warmup-flow-throughs minimum-warmup-flow-throughs
                      :minimum-average-flow-throughs minimum-average-flow-throughs})))
   (let [flow-through-s (flow-through-time-s velocity-m-s)
         warmup (/ average-start-s flow-through-s)
         averaging (/ (- end-time-s average-start-s) flow-through-s)]
     {:flow-through-time-s flow-through-s
      :warmup-flow-throughs warmup
      :average-flow-throughs averaging
      :limits {:minimum-warmup-flow-throughs minimum-warmup-flow-throughs
               :minimum-average-flow-throughs minimum-average-flow-throughs}
      :passed? (and (>= warmup minimum-warmup-flow-throughs)
                    (>= averaging minimum-average-flow-throughs))})))

(def default-run
  {:end-time-s 1.2 :average-start-s 0.4 :initial-delta-t-s 1.0e-6
   :maximum-delta-t-s maximum-turbulence-stable-dt-s :maximum-courant 0.5 :write-interval-s 0.05
   :start-from :start-time})

(defn- header [object]
  (str "FoamFile\n{\n    format ascii;\n    class dictionary;\n    object " object ";\n}\n"))

(defn validate-run! [{:keys [end-time-s average-start-s initial-delta-t-s maximum-delta-t-s
                             maximum-courant write-interval-s start-from] :as run}]
  (when-not (and (every? pos? [end-time-s initial-delta-t-s maximum-delta-t-s
                                maximum-courant write-interval-s])
                 (<= 0.0 average-start-s) (< average-start-s end-time-s)
                 (<= initial-delta-t-s maximum-delta-t-s)
                 (<= maximum-delta-t-s maximum-turbulence-stable-dt-s)
                 (#{:start-time :latest-time} start-from))
    (throw (ex-info "invalid SBSE URANS time controls" {:run run})))
  run)

(defn dictionaries [_conditions run]
  (let [{:keys [end-time-s average-start-s initial-delta-t-s maximum-delta-t-s
                maximum-courant write-interval-s start-from]} (validate-run! run)]
    {"system/controlDict"
     (str (header "controlDict")
          "application pimpleFoam;\nstartFrom " (if (= :latest-time start-from) "latestTime" "startTime")
          ";\nstartTime 0;\nstopAt endTime;\nendTime " end-time-s
          ";\ndeltaT " initial-delta-t-s ";\nadjustTimeStep yes;\nmaxCo " maximum-courant
          ";\nmaxDeltaT " maximum-delta-t-s ";\nwriteControl adjustableRunTime;\nwriteInterval " write-interval-s
          ";\npurgeWrite 3;\nwriteFormat ascii;\nrunTimeModifiable false;\nfunctions\n{\n"
          "  wallShear { type wallShearStress; libs (fieldFunctionObjects); patches (floorBump); executeControl timeStep; executeInterval 1; writeControl adjustableRunTime; writeInterval " write-interval-s "; }\n"
          "  floorShearSeries { type surfaceFieldValue; libs (fieldFunctionObjects); regionType patch; name floorBump; operation areaAverage; writeFields false; fields (wallShearStress); executeControl timeStep; executeInterval 1; writeControl timeStep; writeInterval 5; }\n"
          "  yPlusField { type yPlus; libs (fieldFunctionObjects); executeControl timeStep; executeInterval 10; writeControl adjustableRunTime; writeInterval " write-interval-s "; }\n"
          "  shearAverage { type fieldAverage; libs (fieldFunctionObjects); timeStart " average-start-s
          "; writeControl adjustableRunTime; writeInterval " write-interval-s
          "; fields (wallShearStress { mean on; prime2Mean off; base time; }); }\n}\n")
     "system/fvSchemes"
     (str (header "fvSchemes")
          "ddtSchemes { default Euler; }\ngradSchemes { default cellLimited Gauss linear 1; }\n"
          "divSchemes { default none; div(phi,U) bounded Gauss upwind; div(phi,k) bounded Gauss upwind; div(phi,omega) bounded Gauss upwind; div((nuEff*dev2(T(grad(U))))) Gauss linear; }\n"
          "laplacianSchemes { default Gauss linear limited 0.5; }\ninterpolationSchemes { default linear; }\nsnGradSchemes { default limited 0.5; }\nwallDist { method meshWave; }\n")
     "system/decomposeParDict"
     (str (header "decomposeParDict") "numberOfSubdomains 4;\nmethod scotch;\n")
     "system/fvSolution"
     (str (header "fvSolution")
          "solvers\n{\n  p { solver GAMG; smoother DICGaussSeidel; tolerance 1e-7; relTol 0.05; minIter 1; maxIter 20; }\n"
          "  pFinal { $p; relTol 0; maxIter 50; }\n  Phi { solver GAMG; smoother GaussSeidel; tolerance 1e-8; relTol 0; }\n"
          "  \"(U|k|omega)\" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-7; relTol 0.1; }\n"
          "  \"(U|k|omega)Final\" { $U; relTol 0; }\n}\n"
          "PIMPLE { nOuterCorrectors 2; nCorrectors 1; nNonOrthogonalCorrectors 0; momentumPredictor yes; finalOnLastPimpleIterOnly true; turbOnFinalIterOnly false; }\n"
          "relaxationFactors { fields { p 0.3; } equations { U 0.7; k 0.3; omega 0.3; } }\n")}))

(defn case-files
  ([experiment] (case-files experiment default-run))
  ([experiment run]
   (let [experiment (assoc experiment :wall-treatment :low-re)
         base (rans/case-files experiment)]
     {:conditions (:conditions base) :run (validate-run! run)
      :files (merge (:files base) (dictionaries (:conditions base) run))})))

(defn stationarity
  "Compare equal first/second halves of the averaging window. Passes only when
  the mean drift and least-squares normalized slope are both within limits."
  [samples {:keys [maximum-relative-mean-drift maximum-normalized-slope]
            :or {maximum-relative-mean-drift 0.02 maximum-normalized-slope 0.02}}]
  (let [samples (vec samples) n (count samples)]
    (when-not (and (>= n 20) (even? n) (every? #(and (number? (:time %)) (number? (:value %))) samples))
      (throw (ex-info "stationarity needs an even series of at least 20 finite samples" {:count n})))
    (let [half (/ n 2) a (subvec samples 0 half) b (subvec samples half)
          mean (fn [xs] (/ (reduce + (map :value xs)) (count xs)))
          ma (mean a) mb (mean b) scale (max (Math/abs mb) 1.0e-12)
          drift (/ (Math/abs (- mb ma)) scale)
          mt (/ (reduce + (map :time b)) half)
          slope (/ (reduce + (map (fn [{:keys [time value]}] (* (- time mt) (- value mb))) b))
                   (max 1.0e-30 (reduce + (map (fn [{:keys [time]}] (Math/pow (- time mt) 2.0)) b))))
          duration (- (:time (peek b)) (:time (first b))) normalized-slope (/ (* (Math/abs slope) duration) scale)
          passed? (and (<= drift maximum-relative-mean-drift)
                       (<= normalized-slope maximum-normalized-slope))]
      {:samples n :first-half-mean ma :second-half-mean mb :relative-mean-drift drift
       :normalized-slope normalized-slope :limits {:maximum-relative-mean-drift maximum-relative-mean-drift
                                                    :maximum-normalized-slope maximum-normalized-slope}
       :passed? passed?})))
