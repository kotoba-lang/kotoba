(ns kotoba.lang.kami-nv-compat.assets.franka-panda
  "Franka Emika Panda asset wrapper — JVM port of src/assets/franka-panda.ts.
  7-DoF arm + 2-finger gripper (9 DoF). Specs from the public Franka Robotics
  FCI documentation + the publicly-distributed Franka URDF (Apache 2.0); no
  proprietary content (no meshes, no Isaac Sim USD refs) — a minimal
  kinematic-chain reproduction with real per-link inertials so the wrapper is
  self-contained and substrate-publishable. Trademark: 'Franka Emika'/'Panda'
  are trademarks of Franka Robotics GmbH; this is API-namespace localization
  only (matching the public FCI spec). Wave 6 of ADR-2607020130.

  The URDF is hand-emitted (not via build-serial-chain-urdf) so it can embed
  real per-link inertials instead of unit-mass placeholders."
  (:require [kotoba.lang.text :as str]))

(defn- num-str [n]
  (let [s (str n)]
    (if (str/ends-with? s ".0") (subs s 0 (- (count s) 2)) s)))

;; Joint specs from public Franka FCI documentation.
(def ^:private panda-arm-joints
  [{:name "panda_joint1" :lower -2.8973 :upper 2.8973 :velocity 2.1750 :effort 87}
   {:name "panda_joint2" :lower -1.7628 :upper 1.7628 :velocity 2.1750 :effort 87}
   {:name "panda_joint3" :lower -2.8973 :upper 2.8973 :velocity 2.1750 :effort 87}
   {:name "panda_joint4" :lower -3.0718 :upper -0.0698 :velocity 2.1750 :effort 87}
   {:name "panda_joint5" :lower -2.8973 :upper 2.8973 :velocity 2.6100 :effort 12}
   {:name "panda_joint6" :lower -0.0175 :upper 3.7525 :velocity 2.6100 :effort 12}
   {:name "panda_joint7" :lower -2.8973 :upper 2.8973 :velocity 2.6100 :effort 12}])

(def ^:private panda-finger-joints
  [{:name "panda_finger_joint1" :lower 0 :upper 0.04 :velocity 0.2 :effort 20}
   {:name "panda_finger_joint2" :lower 0 :upper 0.04 :velocity 0.2 :effort 20}])

;; Real Franka FCI joint origins (modified-DH frame rotations) per the public
;; franka_description URDF (Apache 2.0).
(def ^:private half-pi (/ Math/PI 2))

(def ^:private panda-arm-origins
  [{:xyz [0 0 0.333]     :rpy [0 0 0]}
   {:xyz [0 0 0]         :rpy [(- half-pi) 0 0]}
   {:xyz [0 -0.316 0]    :rpy [half-pi 0 0]}
   {:xyz [0.0825 0 0]    :rpy [half-pi 0 0]}
   {:xyz [-0.0825 0.384 0] :rpy [(- half-pi) 0 0]}
   {:xyz [0 0 0]         :rpy [half-pi 0 0]}
   {:xyz [0.088 0 0]     :rpy [half-pi 0 0]}])

;; Real Franka link inertial parameters per franka_description URDF.
(def ^:private panda-arm-inertials
  [{:mass 2.74 :com [0.003875 0.002081 -0.04762]   :ixx 0.0180 :iyy 0.0184 :izz 0.0089}
   {:mass 2.74 :com [-0.003141 -0.02872 0.003495]  :ixx 0.0184 :iyy 0.0089 :izz 0.0180}
   {:mass 2.38 :com [0.02785 0.03094 -0.0961]      :ixx 0.0089 :iyy 0.0125 :izz 0.0049}
   {:mass 2.38 :com [-0.05317 0.1046 0.02711]      :ixx 0.0125 :iyy 0.0049 :izz 0.0089}
   {:mass 2.74 :com [-0.01121 0.04123 -0.03825]    :ixx 0.0125 :iyy 0.0089 :izz 0.0049}
   {:mass 1.55 :com [0.065 -0.016 -0.020]          :ixx 0.0049 :iyy 0.0049 :izz 0.0017}
   {:mass 0.54 :com [0.010 0.010 0.045]            :ixx 0.0010 :iyy 0.0010 :izz 0.0010}])

(def ^:private finger-mass 0.015)

(defn- inertial-block [mass com ixx iyy izz]
  (str "<inertial>"
       "<origin xyz=\"" (num-str (nth com 0)) " " (num-str (nth com 1)) " " (num-str (nth com 2)) "\" rpy=\"0 0 0\"/>"
       "<mass value=\"" (num-str mass) "\"/>"
       "<inertia ixx=\"" (num-str ixx) "\" ixy=\"0\" ixz=\"0\" iyy=\"" (num-str iyy)
       "\" iyz=\"0\" izz=\"" (num-str izz) "\"/>"
       "</inertial>"))

(defn- build-franka-urdf
  "Hand-build the URDF with real per-link inertials inline."
  []
  (let [arm (map-indexed (fn [i j]
                           (let [origin (nth panda-arm-origins i)
                                 inert  (nth panda-arm-inertials i)
                                 {:keys [xyz rpy]} origin]
                             (str "<joint name=\"" (:name j) "\" type=\"revolute\">"
                                  "<origin xyz=\"" (num-str (nth xyz 0)) " " (num-str (nth xyz 1)) " " (num-str (nth xyz 2))
                                  "\" rpy=\"" (num-str (nth rpy 0)) " " (num-str (nth rpy 1)) " " (num-str (nth rpy 2)) "\"/>"
                                  "<parent link=\"panda_link" i "\"/>"
                                  "<child link=\"panda_link" (inc i) "\"/>"
                                  "<axis xyz=\"0 0 1\"/>"
                                  "<limit lower=\"" (num-str (:lower j)) "\" upper=\"" (num-str (:upper j))
                                  "\" velocity=\"" (num-str (:velocity j)) "\" effort=\"" (num-str (:effort j)) "\"/>"
                                  "</joint>"
                                  "<link name=\"panda_link" (inc i) "\">"
                                  (inertial-block (:mass inert) (:com inert) (:ixx inert) (:iyy inert) (:izz inert))
                                  "</link>")))
                         panda-arm-joints)
        fingers (map-indexed (fn [i j]
                               (let [axis (if (zero? i) "0 1 0" "0 -1 0")]
                                 (str "<joint name=\"" (:name j) "\" type=\"prismatic\">"
                                      "<origin xyz=\"0 0 0.107\" rpy=\"0 0 0\"/>"
                                      "<parent link=\"panda_link7\"/>"
                                      "<child link=\"panda_link" (+ 8 i) "\"/>"
                                      "<axis xyz=\"" axis "\"/>"
                                      "<limit lower=\"" (num-str (:lower j)) "\" upper=\"" (num-str (:upper j))
                                      "\" velocity=\"" (num-str (:velocity j)) "\" effort=\"" (num-str (:effort j)) "\"/>"
                                      "</joint>"
                                      "<link name=\"panda_link" (+ 8 i) "\">"
                                      (inertial-block finger-mass [0 0 0] 1e-5 1e-5 1e-5)
                                      "</link>")))
                             panda-finger-joints)]
    (str "<?xml version=\"1.0\"?>"
         "<robot name=\"panda\">"
         "<link name=\"panda_link0\">" (inertial-block 0 [0 0 0] 0 0 0) "</link>"
         (str/join "" arm)
         (str/join "" fingers)
         "</robot>")))

(defn make-franka-panda
  "Franka Panda 9-DoF asset. opts: {:prim-path :name}. Returns a map with
  :urdf-text, :joint-names (9), :arm-joint-names (7), :finger-joint-names (2),
  :dof-count 9, limits, :home-pose/:arm-indices/:finger-indices (fns)."
  ([]
   (make-franka-panda nil))
  ([{:keys [prim-path name] :or {prim-path "/World/Franka" name "franka_panda"}}]
   (let [arm-joint-names     (mapv :name panda-arm-joints)
         finger-joint-names  (mapv :name panda-finger-joints)
         joint-names-all     (vec (concat arm-joint-names finger-joint-names))
         default-positions   [0 -0.7854 0 -2.3562 0 1.5708 0.7854 0.04 0.04]
         lower-limits        (vec (concat (map :lower panda-arm-joints) (map :lower panda-finger-joints)))
         upper-limits        (vec (concat (map :upper panda-arm-joints) (map :upper panda-finger-joints)))
         velocity-limits     (vec (concat (map :velocity panda-arm-joints) (map :velocity panda-finger-joints)))
         effort-limits       (vec (concat (map :effort panda-arm-joints) (map :effort panda-finger-joints)))]
     {:prim-path               prim-path
      :name                    name
      :urdf-text               (build-franka-urdf)
      :joint-names             joint-names-all
      :arm-joint-names         arm-joint-names
      :finger-joint-names      finger-joint-names
      :dof-count               9
      :arm-dof-count           7
      :finger-dof-count        2
      :default-joint-positions default-positions
      :default-joint-velocities (vec (repeat 9 0))
      :joint-lower-limits      lower-limits
      :joint-upper-limits      upper-limits
      :joint-velocity-limits   velocity-limits
      :effort-limits           effort-limits
      :gripper-open-command    [0.04 0.04]
      :gripper-close-command   [0 0]
      :ee-link-name            "panda_hand"
      :home-pose               (fn [] default-positions)
      :arm-indices             (fn [] [0 1 2 3 4 5 6])
      :finger-indices          (fn [] [7 8])})))
