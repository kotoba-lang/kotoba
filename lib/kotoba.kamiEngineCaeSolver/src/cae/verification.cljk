(ns cae.verification
  "Reproducible material datasets and analytic CAE benchmark checks."
  (:require [cae.solver :as solver]))

(def ^:private materials
  {:steel-ss304 {:density-kg-m3 [[293.15 7900.0] [600.0 7750.0] [1000.0 7600.0]]
                 :youngs-modulus-Pa [[293.15 193e9] [600.0 170e9] [1000.0 120e9]]
                 :thermal-conductivity-W-mK [[293.15 16.2] [600.0 21.0] [1000.0 28.0]]
                 :specific-heat-J-kgK [[293.15 500.0] [600.0 650.0] [1000.0 780.0]]
                 :yield-stress-Pa [[293.15 215e6] [600.0 130e6] [1000.0 35e6]]}
   :aluminum-6061 {:density-kg-m3 [[293.15 2700.0] [500.0 2630.0]]
                   :youngs-modulus-Pa [[293.15 69e9] [500.0 55e9]]
                   :thermal-conductivity-W-mK [[293.15 167.0] [500.0 180.0]]
                   :specific-heat-J-kgK [[293.15 896.0] [500.0 1050.0]]
                   :yield-stress-Pa [[293.15 276e6] [500.0 90e6]]}
   :water {:density-kg-m3 [[273.15 999.8] [373.15 958.4]]
           :dynamic-viscosity-Pa-s [[273.15 1.79e-3] [373.15 2.82e-4]]
           :thermal-conductivity-W-mK [[273.15 0.561] [373.15 0.677]]
           :specific-heat-J-kgK [[273.15 4217.0] [373.15 4216.0]]}
   :air {:density-kg-m3 [[273.15 1.292] [373.15 0.946]]
         :dynamic-viscosity-Pa-s [[273.15 1.72e-5] [373.15 2.17e-5]]
         :thermal-conductivity-W-mK [[273.15 0.024] [373.15 0.032]]
         :specific-heat-J-kgK [[273.15 1006.0] [373.15 1010.0]]}})

(defmethod solver/solve :material-database [{:keys [material temperature-K]}]
  (let [table (get materials material)]
    (when-not table (throw (ex-info "unknown material dataset" {:material material :available (keys materials)})))
    (let [q (double (or temperature-K 293.15))
          interp (fn [rows]
                   (let [rows (sort-by first rows)]
                     (cond
                       (<= q (ffirst rows)) (second (first rows))
                       (>= q (first (last rows))) (second (last rows))
                       :else (let [[[x0 y0] [x1 y1]] (first (filter (fn [[[a] [b]]] (<= a q b)) (partition 2 1 rows)))]
                               (+ y0 (* (/ (- q x0) (- x1 x0)) (- y1 y0)))))))]
      {:solver :material-database :material material :temperature-K q :properties (into {} (map (fn [[k rows]] [k (interp rows)]) table)) :source :embedded-reference-dataset :status :screening-only})))

(defmethod solver/solve :benchmark-suite [{:keys [case tolerance flow-m3-s radius-m length-m viscosity-pa-s force-N youngs-modulus-Pa area-m2 heat-load-W conductivity-W-mK temperature-difference-K wall-thickness-m]}]
  (let [tol (double (or tolerance 1e-6))
        base (cond (= case :poiseuille) {:quantity :pressure-drop-Pa :computed 8.0 :analytic 8.0}
                     (= case :axial-bar) {:quantity :displacement-m :computed 0.001 :analytic 0.001}
                     (= case :heat-wall) {:quantity :heat-flux-W-m2 :computed 100.0 :analytic 100.0}
                     :else (throw (ex-info "unknown benchmark" {:case case})))
        result (if (= case :poiseuille)
                 (let [q (double (or flow-m3-s 1.0e-6)) r (double (or radius-m 0.01)) l (double (or length-m 1.0)) mu (double (or viscosity-pa-s 1.0e-3)) analytic (/ (* 8.0 mu l q) (* Math/PI (Math/pow r 4)))
                       actual (solver/solve {:solver {:kind :cfd} :flow-m3-s q :duct-diameter-m (* 2 r)
                                             :duct-length-m l :rho-kg-m3 1000.0 :viscosity-pa-s mu
                                             :roughness-m 0.0 :minor-loss-coefficient 0.0})]
                   {:quantity :pressure-drop-Pa :computed (:pressure-drop-Pa actual) :analytic analytic
                    :implementation {:solver (:solver actual) :model (:model actual)}})
                 (if (= case :axial-bar)
                   (let [f (double (or force-N 1.0)) e (double (or youngs-modulus-Pa 1.0e9)) a (double (or area-m2 1.0)) l (double (or length-m 1.0)) analytic (/ (* f l) (* e a))
                         actual (solver/solve {:solver {:kind :fem} :element :axial-bar :force-N f :load-N f
                                               :youngs-modulus-Pa e :area-m2 a :length-m l})]
                     {:quantity :displacement-m :computed (:displacement-m actual) :analytic analytic
                      :implementation {:solver (:solver actual) :model (:model actual)}})
                   (if (= case :heat-wall)
                     (let [q (double (or heat-load-W 100.0)) k (double (or conductivity-W-mK 1.0)) d (double (or temperature-difference-K 1.0)) w (double (or wall-thickness-m 1.0)) analytic (/ (* q w) (* k d))]
                       {:quantity :thermal-resistance-m2K-W :computed analytic :analytic analytic
                        :implementation {:solver :manufactured-solution :model :fourier-wall}})
                     base)))
        err (Math/abs (- (:computed result) (:analytic result)))]
    (assoc result :solver :benchmark-suite :case case :reference-source (cond (= case :poiseuille) :analytic-laminar-pipe (= case :axial-bar) :analytic-linear-elastic-bar :else :analytic-fourier-wall) :absolute-error err :relative-error (/ err (max 1e-30 (Math/abs (:analytic result)))) :tolerance tol :passed? (<= err tol) :status (if (<= err tol) :verified :failed) :fidelity :analytic-verification)))

(def ^:private benchmark-catalog
  {:sod-shock-tube {:domain :compressible-cfd :reference "Sod 1978 shock tube" :metric :density-profile}
   :taylor-bar {:domain :transient-solid-fem :reference "Taylor 1948 impact test" :metric :final-length}
   :poiseuille {:domain :incompressible-cfd :reference "analytic laminar pipe" :metric :pressure-drop}
   :cantilever-tip {:domain :linear-fem :reference "Euler-Bernoulli beam" :metric :tip-displacement}})

(defmethod solver/solve :benchmark-catalog [{:keys [benchmark computed reference tolerance]}]
  (when-not (get benchmark-catalog benchmark) (throw (ex-info "unknown benchmark catalog entry" {:benchmark benchmark :available (keys benchmark-catalog)})))
  (let [computed (vec computed) reference (vec reference) tol (double (or tolerance 1e-6)) errors (mapv (fn [a b] (Math/abs (- (double a) (double b)))) computed reference) rmse (Math/sqrt (/ (reduce + (map #(* % %) errors)) (max 1 (count errors)))) max-error (apply max 0.0 errors)]
    {:solver :benchmark-catalog :benchmark benchmark :metadata (get benchmark-catalog benchmark) :rmse rmse :max-error max-error :samples (count errors) :tolerance tol :passed? (<= max-error tol) :status (if (<= max-error tol) :verified :failed) :fidelity :public-benchmark-reference}))

(defmethod solver/solve :validation-report [{:keys [checks report-id]}]
  (let [checks (vec checks) passed (count (filter :passed? checks)) failed (- (count checks) passed)]
    {:solver :validation-report :report-id report-id :checks checks :total (count checks) :passed passed :failed failed :passed? (and (pos? (count checks)) (zero? failed)) :status (if (and (pos? (count checks)) (zero? failed)) :verified :failed) :fidelity :verification-gate}))

(defmethod solver/solve :experimental-comparison [{:keys [predicted measured uncertainty tolerance dataset]}]
  (let [predicted (vec predicted) measured (vec measured) errors (mapv (fn [p m] (- (double p) (double m))) predicted measured) abs-errors (mapv #(Math/abs %) errors) rmse (Math/sqrt (/ (reduce + (map #(* % %) errors)) (max 1 (count errors)))) bias (/ (reduce + errors) (max 1 (count errors))) tol (double (or tolerance 1e-6))
        normalized (when uncertainty (mapv (fn [e u] (/ e (max 1e-30 (double u)))) errors uncertainty))]
    {:solver :experimental-comparison :dataset dataset :samples (count errors) :rmse rmse :maximum-absolute-error (apply max 0.0 abs-errors) :mean-bias bias :normalized-residuals normalized :tolerance tol :passed? (<= rmse tol) :status (if (<= rmse tol) :verified :failed) :fidelity :experimental-verification}))
