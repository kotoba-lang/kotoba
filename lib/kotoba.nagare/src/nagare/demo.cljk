(ns nagare.demo
  "Lid-driven cavity — the canonical incompressible CFD verification (icoFoam).

  A unit square of fluid, three no-slip walls and a **lid** sliding at `U=(1,0)`.
  The shear from the lid drives a primary recirculating vortex; at Reynolds number
  100 the vortex centre sits slightly above and right of centre, and the
  **u-velocity along the vertical centreline x=0.5** is the textbook signature:
  it falls from `+1` at the lid, crosses zero near mid-height, dips to about
  `-0.21` in the lower half (the returning underflow), and approaches `0` at the
  floor. Ghia, Ghia & Shin (1982) tabulated this profile; it is the standard a CFD
  code is held to, and what `-main` prints so it can be eyeballed.

  `nu = U L / Re = 1 * 1 / 100 = 0.01`. We run it on a modest grid to a near-steady
  state with the PISO loop in `nagare.solver`."
  (:require [nagare.mesh :as mesh]
            [nagare.field :as field]
            [nagare.solver :as solver]))

(defn cavity-case
  "Build the lid-driven-cavity initial state and parameters for an `n`x`n` grid at
  Reynolds number `re`. Returns `{:mesh :init :params}`."
  [{:keys [n re dt n-correctors] :or {n 20 re 100 n-correctors 2}}]
  (let [m   (mesh/block-mesh {:nx n :ny n :lx 1.0 :ly 1.0})
        nu  (/ 1.0 (double re))                         ; U=1, L=1
        dt  (or dt (* 0.4 (/ 1.0 n)))                   ; CFL ~ 0.4 at U=1
        U   (field/vol-vector m [0.0 0.0]
                              {:top    {:type :fixed-value :value [1.0 0.0]}
                               :left   {:type :no-slip}
                               :right  {:type :no-slip}
                               :bottom {:type :no-slip}})
        p   (field/vol-scalar m 0.0
                              {:top    {:type :fixed-flux-pressure}
                               :left   {:type :fixed-flux-pressure}
                               :right  {:type :fixed-flux-pressure}
                               :bottom {:type :fixed-flux-pressure}})]
    {:mesh m
     :init {:U U :p p :phi nil}
     :params {:nu nu :dt dt :n-correctors n-correctors :ref-cell 0
              :p-tol 1e-7 :u-tol 1e-6 :max-iter 400}}))

(defn centreline-u
  "Sample the u-velocity along the vertical centreline x=0.5 from a solved state.
  For an even grid x=0.5 lies between columns `n/2-1` and `n/2`, so we average the
  two. Returns a vector of `[y u]` ordered floor->lid."
  [m U]
  (let [nx (:nx m) ny (:ny m) dy (:dy m)
        vals (:values U)
        cidx (fn [i j] (+ (* j nx) i))
        il (dec (quot nx 2)) ir (quot nx 2)
        interior (mapv (fn [j]
                         (let [ul (double (nth (nth vals (cidx il j)) 0))
                               ur (double (nth (nth vals (cidx ir j)) 0))]
                           [(* (+ j 0.5) dy) (* 0.5 (+ ul ur))]))
                       (range ny))]
    ;; bracket with the wall boundary values: floor no-slip (u=0), lid (u=1)
    (into [[0.0 0.0]] (conj interior [1.0 1.0]))))

(defn run
  "Solve the cavity and return `{:mesh :state :profile :min-u :steps-run}`."
  [opts]
  (let [{:keys [mesh init params]} (cavity-case opts)
        st (solver/advance mesh params init
                           {:steps (:steps opts 4000)
                            :steady-tol (:steady-tol opts 2e-5)})
        prof (centreline-u mesh (:U st))
        min-u (reduce min (map second prof))]
    {:mesh mesh :state st :profile prof :min-u min-u
     :steps-run (:steps-run st) :converged (:converged st)}))

(defn- parse-int [s]
  #?(:clj (Integer/parseInt s) :cljs (js/parseInt s 10)))

(defn- fmt4 [n]
  #?(:clj (format "%.4f" (double n)) :cljs (.toFixed n 4)))

(defn- fmt5-signed
  "Fixed 5-decimal formatting with a leading space for non-negative values
  (mirrors Java format's ' ' flag, used here to align the sign column for
  a printed centreline u-profile that straddles 0; .toFixed has no
  native equivalent for it on cljs)."
  [n]
  (let [s #?(:clj (format "%.5f" (double n)) :cljs (.toFixed n 5))]
    (if (neg? n) s (str " " s))))

(defn -main [& args]
  (let [n (if (seq args) (parse-int (first args)) 32)
        _ (println (str "nagare-clj — lid-driven cavity, Re=100, " n "x" n " grid"))
        {:keys [profile min-u steps-run converged]} (run {:n n :re 100})]
    (println (str "PISO steps run: " steps-run (when converged " (steady)")))
    (println (str "min centreline u: " (fmt4 min-u) "  (Ghia Re=100 ~ -0.21)"))
    (println "  y        u(x=0.5)")
    (doseq [[y u] profile]
      (println (str (fmt4 y) "   " (fmt5-signed u))))
    (flush)))
