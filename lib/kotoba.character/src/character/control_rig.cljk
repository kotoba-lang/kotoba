(ns character.control-rig
  "Control Rig: procedural rigging system for MetaHuman face/body
  animation. Maps high-level controls (FACS AUs, look-at, head pose)
  to bone transforms via a directed acyclic graph of rig nodes.
  Restored from the legacy kami-engine/kami-character Rust crate's
  `control_rig.rs` (deleted in kotoba-lang/kami-engine PR #82) as part
  of the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root)."
  (:require [character.math :as m]))

(defn default-bone-transform [] {:position m/vec3-zero :rotation m/quat-identity :scale m/vec3-one})

(defn- add-au-bone
  "Append 3 nodes (control-input, multiply, rotation-axis) for one FACS
  AU -> bone mapping. Returns `[nodes' next-idx]`."
  [nodes idx au-name bone-idx axis max-angle]
  (let [control-idx idx
        nodes (conj nodes {:name (str "ctrl_" au-name)
                            :node-type {:type :control-input :control-name au-name}
                            :inputs [] :target-bone nil})
        idx (inc idx)
        mul-idx idx
        nodes (conj nodes {:name (str "mul_" au-name)
                            :node-type {:type :multiply :factor max-angle}
                            :inputs [[control-idx 0]] :target-bone nil})
        idx (inc idx)
        nodes (conj nodes {:name (str "rot_" au-name)
                            :node-type {:type :rotation-axis :axis axis}
                            :inputs [[mul-idx 0]] :target-bone bone-idx})
        idx (inc idx)]
    [nodes idx]))

(defn metahuman-face-rig
  "Create a MetaHuman face control rig with FACS AU -> bone mappings."
  []
  (let [au-specs
        [["AU43_L" 13 [1.0 0.0 0.0] -0.5] ["AU43_R" 15 [1.0 0.0 0.0] -0.5]
         ["AU7_L" 14 [1.0 0.0 0.0] 0.3] ["AU7_R" 16 [1.0 0.0 0.0] 0.3]
         ["AU1" 17 [1.0 0.0 0.0] 0.3] ["AU2_L" 19 [1.0 0.0 0.0] 0.25]
         ["AU2_R" 22 [1.0 0.0 0.0] 0.25] ["AU4" 18 [1.0 0.0 0.0] -0.2]
         ["AU26" 8 [1.0 0.0 0.0] 0.4] ["AU30" 8 [0.0 1.0 0.0] 0.15]
         ["AU12_L" 34 [0.0 0.0 1.0] 0.3] ["AU12_R" 35 [0.0 0.0 1.0] 0.3]
         ["AU15_L" 34 [0.0 0.0 1.0] -0.2] ["AU15_R" 35 [0.0 0.0 1.0] -0.2]
         ["AU38_L" 25 [1.0 0.0 0.0] 0.15] ["AU38_R" 26 [1.0 0.0 0.0] 0.15]
         ["AU6_L" 36 [1.0 0.0 0.0] 0.2] ["AU6_R" 37 [1.0 0.0 0.0] 0.2]
         ["AU19" 44 [1.0 0.0 0.0] 0.5]]
        [nodes _idx]
        (reduce (fn [[nodes idx] [au-name bone-idx axis max-angle]]
                  (add-au-bone nodes idx au-name bone-idx axis max-angle))
                [[] 0] au-specs)]
    {:nodes nodes :eval-order (vec (range (count nodes)))
     :controls {} :bone-outputs {}}))

(defn set-control [rig name value] (assoc-in rig [:controls name] value))

(defn- node-input-avg [node-values node]
  (let [inputs (:inputs node)]
    (if (seq inputs)
      (/ (reduce + (map (fn [[src _]] (nth node-values src)) inputs)) (count inputs))
      0.0)))

(defn evaluate
  "Evaluate the rig graph and compute bone transforms. Returns the rig
  with `:bone-outputs` populated."
  [{:keys [nodes eval-order controls] :as rig}]
  (loop [order eval-order
         node-values (vec (repeat (count nodes) 0.0))
         bone-outputs {}]
    (if (empty? order)
      (assoc rig :bone-outputs bone-outputs)
      (let [ni (first order)
            node (nth nodes ni)
            input-val (node-input-avg node-values node)
            {:keys [type] :as nt} (:node-type node)
            [output bone-outputs]
            (case type
              :control-input [(get controls (:control-name nt) 0.0) bone-outputs]
              :multiply [(* input-val (:factor nt)) bone-outputs]
              :clamp [(m/clamp input-val (:min nt) (:max nt)) bone-outputs]
              :remap (let [{:keys [in-min in-max out-min out-max]} nt
                           t (m/clamp (/ (- input-val in-min) (- in-max in-min)) 0.0 1.0)]
                       [(+ out-min (* t (- out-max out-min))) bone-outputs])
              :blend [(reduce + (map (fn [[src _] w] (* (nth node-values src) w)) (:inputs node) (:weights nt))) bone-outputs]
              :rotation-axis
              (if-let [bone-idx (:target-bone node)]
                (let [axis-vec (m/vec3-normalize-or-zero (:axis nt))
                      rot (m/quat-from-axis-angle axis-vec input-val)
                      entry (get bone-outputs bone-idx (default-bone-transform))
                      entry (update entry :rotation #(m/quat-mul % rot))]
                  [input-val (assoc bone-outputs bone-idx entry)])
                [input-val bone-outputs])
              :translation-axis
              (if-let [bone-idx (:target-bone node)]
                (let [axis-vec (:axis nt)
                      entry (get bone-outputs bone-idx (default-bone-transform))
                      entry (update entry :position #(m/vec3+ % (m/vec3-scale axis-vec input-val)))]
                  [input-val (assoc bone-outputs bone-idx entry)])
                [input-val bone-outputs])
              :corrective
              (let [all-above (every? (fn [[[src _] th]] (>= (nth node-values src) th))
                                      (map vector (:inputs node) (:thresholds nt)))]
                [(if all-above 1.0 0.0) bone-outputs])
              [input-val bone-outputs])]
        (recur (rest order) (assoc node-values ni output) bone-outputs)))))

(defn apply-to-skeleton
  "Apply rig outputs to `skeleton`'s already-evaluated `world` joint
  matrices (a vector of Mat4, one per bone). Returns a vector of joint
  matrices (`world[i] * inverse-bind[i]`, with rig bone overrides
  composed in first)."
  [{:keys [bone-outputs]} skeleton world]
  (let [world (reduce
               (fn [world [bone-idx {:keys [position rotation scale]}]]
                 (if (< bone-idx (count world))
                   (let [rig-mat (m/mat4-from-scale-rotation-translation scale rotation position)]
                     (update world bone-idx #(m/mat4-mul % rig-mat)))
                   world))
               (vec world) bone-outputs)]
    (mapv (fn [i bone]
            (let [inv-bind (:inverse-bind bone)]
              (m/mat4-mul (nth world i) inv-bind)))
          (range (count (:bones skeleton))) (:bones skeleton))))
