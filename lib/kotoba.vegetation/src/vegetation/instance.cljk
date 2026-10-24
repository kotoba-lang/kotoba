(ns vegetation.instance
  "Per-plant instance data (GPU-uploadable).

  Restored from `kami-vegetation/src/instance.rs` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as part of
  the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  The original Rust `InstanceData` is a `#[repr(C)]` Pod/Zeroable struct:
  8 f32 fields (32 bytes, GPU-aligned), uploaded once at scene generation
  and left static (wind animation happens shader-side). Here it is a
  plain CLJC map with the same 8 keys; `instance->floats` produces the
  flat 8-float buffer layout for GPU upload.")

(def stride
  "Bytes per instance (8 x f32 = 32 bytes, GPU-aligned)."
  32)

(defn make-instance
  "Build an InstanceData map.
   :position    — world-space [x y z]
   :scale       — uniform scale (vertical)
   :rotation    — rotation around Y axis (radians)
   :species     — species id, as a float (see vegetation.species/species-id->index)
   :wind-phase  — random wind phase offset [0, 2pi]
   :color-tint  — random color variation [-0.15, +0.15]"
  [{:keys [position scale rotation species wind-phase color-tint]}]
  {:position position
   :scale scale
   :rotation rotation
   :species species
   :wind-phase wind-phase
   :color-tint color-tint})

(defn instance->floats
  "Flatten an instance to the 8-float GPU buffer layout:
   [px py pz scale rotation species wind-phase color-tint]."
  [{:keys [position scale rotation species wind-phase color-tint]}]
  (let [[x y z] position]
    [x y z scale rotation species wind-phase color-tint]))
