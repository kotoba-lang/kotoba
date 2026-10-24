(ns kotoba.groot.modality
  "Embodiment + modality configuration — binds a robot's DOF order, camera
  streams, and language slot onto the policy's typed I/O heads (a la
  GR00T's `ModalityConfig` / embodiment data-config). Ported from
  kami-groot/src/modality.rs.")

(def modalities
  "The four GR00T modality channels."
  #{:state :action :video :language})

(defn modality-config
  "Which modalities the policy consumes/produces and at what width."
  [& {:keys [state-dim action-dim cameras language?]}]
  {:modality/state-dim  (or state-dim 0)
   :modality/action-dim (or action-dim 0)
   :modality/cameras    (vec (or cameras []))
   :modality/language?  (boolean language?)})

(defn embodiment-config
  "Maps a concrete robot onto the GR00T I/O heads. Built from URDF-derived
  actuated-joint names + limits (e.g. kami-genesis `dof-names` /
  `get-dof-limits`) plus the sensor-rig camera list — not hardcoded.

  `state-dim` defaults to the DOF count (joint-position proprioception);
  callers wanting pos+vel can `assoc-in [:embodiment/modality
  :modality/state-dim]` afterwards. `dof-limits` is `[n-dof]` of
  `[lower upper]`, one per `dof-names` entry."
  [name dof-names dof-limits cameras action-horizon]
  (let [n-dof (count dof-names)]
    (assert (= (count dof-limits) n-dof) "dof-limits must be [n-dof]")
    {:embodiment/name           name
     :embodiment/dof-names      (vec dof-names)
     :embodiment/dof-limits     (vec dof-limits)
     :embodiment/cameras        (vec cameras)
     :embodiment/action-horizon (max 1 action-horizon)
     :embodiment/modality       (modality-config :state-dim n-dof
                                                   :action-dim n-dof
                                                   :cameras cameras
                                                   :language? true)}))

(defn n-dof
  "Number of actuated DOFs."
  [embodiment]
  (count (:embodiment/dof-names embodiment)))
