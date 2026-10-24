(ns kotoba.groot.policy
  "`gr00t-policy` — the clean-room mirror of GR00T's policy lifecycle
  (`from_pretrained` / `reset` / `get_action`). Ported from
  kami-groot/src/policy.rs."
  (:require [kotoba.groot.embodiment :as ehead]
            [kotoba.groot.native :as native]
            [kotoba.groot.types :as types]))

(defn from-pretrained
  "Mirror `Gr00tPolicy.from_pretrained(path, embodiment)`. With no weights
  at `path` (the only charter-clean case — this port never reads `path`),
  instantiate the KAMI-native default backend, so the surface is
  exercisable with zero NVIDIA assets. Loading an actual checkpoint is an
  optional out-of-tree backend via `with-backend` — a host-adapter
  concern, not ported here (see README)."
  [path embodiment]
  (let [state-dim (get-in embodiment [:embodiment/modality :modality/state-dim])
        head      (ehead/native-head-zeros state-dim (count (:embodiment/dof-names embodiment)))]
    {:gr00t/embodiment embodiment
     :gr00t/backend     head
     :gr00t/checkpoint  nil
     :gr00t/from-path   path}))

(defn native
  "Explicit native seat (`from-pretrained` with an empty path)."
  [embodiment]
  (from-pretrained "" embodiment))

(defn with-backend
  "Install a caller-supplied backend (e.g. a trained native head, or an
  out-of-tree checkpoint adapter). `checkpoint` is recorded for
  provenance."
  [embodiment backend checkpoint]
  {:gr00t/embodiment embodiment
   :gr00t/backend     backend
   :gr00t/checkpoint  checkpoint})

(defn reset
  "Reset per-episode policy state. The native backend is stateless, so
  this is a no-op (returns `policy` unchanged); the function exists to
  mirror the GR00T surface."
  [policy]
  policy)

(defn get-action
  "Mirror `policy.get_action(obs)`. Runs the backend on the proprioceptive
  state, rescales the normalized `[-1,1]` action to the embodiment's joint
  limits, and tiles it across the action horizon as a constant chunk (the
  native backend is myopic; the `[horizon n-dof]` shape is preserved so a
  real checkpoint can emit a genuine plan)."
  [{:gr00t/keys [embodiment backend]} obs]
  (let [n-dof      (count (:embodiment/dof-names embodiment))
        horizon    (max 1 (:embodiment/action-horizon embodiment))
        normalized (ehead/act backend (:obs/state obs))
        one        (native/rescale-to-limits normalized (:embodiment/dof-limits embodiment))]
    (types/action horizon n-dof (vec (apply concat (repeat horizon one))))))

(defn checkpoint
  "The provenance of the loaded checkpoint, or `nil` for the native seat."
  [policy]
  (:gr00t/checkpoint policy))
