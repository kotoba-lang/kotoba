(ns kotoba.groot.embodiment
  "The embodiment-head seat: GR00T's 'new-embodiment head' idea as data — a
  small adapter mapping the shared policy latent to a specific robot's
  action space. Swapping the head (`:head/kind`) is how the same surface
  serves the native policy or a caller-supplied out-of-tree backend.
  Ported from kami-groot/src/embodiment.rs."
  (:require [kotoba.groot.native :as native]))

(defn native-head-zeros
  "A zero-initialized native head (`state-dim -> n-dof`). The shipped
  default backend: an affine `LinearPolicy` (`a = W*obs + b`) — charter
  clean, no foundation-model weights."
  [state-dim n-dof]
  {:head/kind   :native
   :head/policy (native/linear-policy-zeros state-dim n-dof)
   :head/n-dof  n-dof})

(defn native-head-from-policy
  "Wrap an already-built / already-trained affine policy (see
  `kotoba.groot.native/linear-policy-zeros`)."
  [policy]
  {:head/kind   :native
   :head/policy policy
   :head/n-dof  (:policy/act-dim policy)})

(defmulti act
  "Normalized one-step action (`[-1,1]^n-dof`, the standard Isaac/GR00T
  squashed-action convention; `kotoba.groot.policy/get-action` rescales to
  joint limits downstream) for `obs-state` (`[state-dim]`), dispatched on
  `:head/kind`. Only `:native` ships in-tree; an out-of-tree checkpoint
  backend is a `defmethod` extension point, not implemented here (host-
  adapter concern, see README)."
  (fn [head _obs-state] (:head/kind head)))

(defmethod act :native
  [{:head/keys [policy]} obs-state]
  (mapv #(max -1.0 (min 1.0 %)) (native/linear-policy-act policy obs-state)))

(defn n-dof
  "Actuated DOF count (length of the returned action)."
  [head]
  (:head/n-dof head))
