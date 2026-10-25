(ns kotoba.lang.kami-nv-compat.assets.anymal-c
  "ANYmal C asset wrapper — JVM port of src/assets/anymal-c.ts. 12-DoF
  quadruped (4 legs × 3 joints: HAA hip ab/adduction, HFE hip flex/extend,
  KFE knee flex/extend). Specs from the publicly-distributed ANYbotics ANYmal
  C URDF (BSD-3) + Hwangbo et al. 2019; minimal kinematic-tree reproduction.
  Trademark: 'ANYmal' is a trademark of ANYbotics AG; API-namespace
  localization only. Wave 7 of ADR-2607020130."
  (:require [kotoba.lang.text :as str]
            [kotoba.lang.kami-nv-compat.assets.urdf-builder :as ub]))

(def leg-names ["LF" "LH" "RF" "RH"])

;; Per-leg HAA base attachment in body frame (anymal_c_simple_description, BSD-3).
(def ^:private anymal-haa-base-offset
  {"LF" [0.277  0.116 0.0]
   "LH" [-0.277 0.116 0.0]
   "RF" [0.277 -0.116 0.0]
   "RH" [-0.277 -0.116 0.0]})

(def ^:private leg-joints
  [{:suffix "HAA" :axis [1 0 0] :lower -0.611 :upper 0.611 :velocity 7.5 :effort 80}
   {:suffix "HFE" :axis [0 1 0] :lower -9.42  :upper 9.42  :velocity 7.5 :effort 80}
   {:suffix "KFE" :axis [0 1 0] :lower -9.42  :upper 9.42  :velocity 7.5 :effort 80}])

(defn- build-anymal-urdf []
  (let [branches (vec (for [leg leg-names
                            :let [haa-xyz (get anymal-haa-base-offset leg)]]
                        [{:name (str leg "_HAA") :type "revolute" :axis [1 0 0]
                          :lower -0.611 :upper 0.611 :velocity 7.5 :effort 80
                          :origin-xyz haa-xyz}
                         {:name (str leg "_HFE") :type "revolute" :axis [0 1 0]
                          :lower -9.42 :upper 9.42 :velocity 7.5 :effort 80
                          :origin-xyz [0 0.0635 0]}
                         {:name (str leg "_KFE") :type "revolute" :axis [0 1 0]
                          :lower -9.42 :upper 9.42 :velocity 7.5 :effort 80
                          :origin-xyz [0 0.041 -0.317]}]))
        prefixes (mapv #(str % "_link") leg-names)]
    (ub/build-branched-urdf "anymal_c" "base" branches prefixes)))

;; Standing pose: HAA=0 (vertical), HFE=±0.4 (front +, hind −), KFE=∓0.8.
(def standing-pose
  [0  0.4 -0.8
   0 -0.4  0.8
   0  0.4 -0.8
   0 -0.4  0.8])

(defn- make-joint-names []
  (vec (for [leg leg-names j leg-joints] (str leg "_" (:suffix j)))))

(defn make-anymal-c
  "ANYmal C 12-DoF quadruped asset. opts: {:prim-path :name}. Returns a map
  with :urdf-text, :joint-names (12), limits, :leg-indices/:haa-indices/... fns."
  ([]
   (make-anymal-c nil))
  ([{:keys [prim-path name] :or {prim-path "/World/Anymal" name "anymal_c"}}]
   {:prim-path               prim-path
    :name                    name
    :urdf-text               (build-anymal-urdf)
    :joint-names             (make-joint-names)
    :dof-count               12
    :default-joint-positions standing-pose
    :default-joint-velocities (vec (repeat 12 0))
    :joint-lower-limits      (vec (mapcat (fn [_] [-0.611 -9.42 -9.42]) leg-names))
    :joint-upper-limits      (vec (mapcat (fn [_] [0.611 9.42 9.42]) leg-names))
    :joint-velocity-limits   (vec (repeat 12 7.5))
    :effort-limits           (vec (repeat 12 80))
    :foot-link-names         ["LF_foot" "LH_foot" "RF_foot" "RH_foot"]
    :base-link-name          "base"
    :leg-names               leg-names
    :joints-per-leg          3
    :leg-indices (fn [leg]
                   (let [idx (first (keep-indexed #(when (= %2 leg) %1) leg-names))]
                     (when (nil? idx)
                       (throw (ex-info (str "AnymalC.leg-indices: leg must be one of "
                                            (str/join "," leg-names))
                                       {:leg leg})))
                     (let [start (* idx 3)] [start (inc start) (+ start 2)])))
    :haa-indices (fn [] [0 3 6 9])
    :hfe-indices (fn [] [1 4 7 10])
    :kfe-indices (fn [] [2 5 8 11])}))
