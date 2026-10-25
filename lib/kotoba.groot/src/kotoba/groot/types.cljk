(ns kotoba.groot.types
  "GR00T-shaped observation / action data — pure data, no network/IO.
  Ported from kami-groot/src/types.rs (Frame / Observation / Action).")

(defn frame
  "A single camera frame feeding the :video modality. `pixels` is RGB8
  row-major bytes and may be empty in headless tests (the shape is what
  the policy binds against; the codec is ours, no NVIDIA decoder)."
  [camera width height & {:keys [pixels]}]
  {:frame/camera camera
   :frame/width  width
   :frame/height height
   :frame/pixels (or pixels [])})

(defn observation
  "GR00T policy input: proprioceptive `state` (`[state-dim]`), zero or
  more camera `video` frames, and an optional `language` instruction."
  [state & {:keys [video language]}]
  {:obs/state    (vec state)
   :obs/video    (or video [])
   :obs/language language})

(defn action
  "GR00T policy output: an action chunk — `horizon` future steps of
  `n-dof` joint targets, row-major `[horizon n-dof]`. `joint-targets` is
  the flat vector."
  [horizon n-dof joint-targets]
  {:action/horizon       horizon
   :action/n-dof         n-dof
   :action/joint-targets (vec joint-targets)})

(defn action-step
  "Joint targets for chunk step `i` (`0..horizon`)."
  [{:action/keys [n-dof joint-targets]} i]
  (subvec joint-targets (* i n-dof) (* (inc i) n-dof)))

(defn action-first
  "The immediately-executed step (`action-step _ 0`) — what a non-chunked
  control loop consumes."
  [a]
  (action-step a 0))
