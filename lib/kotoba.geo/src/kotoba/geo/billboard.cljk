(ns kotoba.geo.billboard
  "Billboard definitions for markers, labels, and icons.

  Billboards are screen-space quads that always face the camera. A
  renderer handles the actual GPU pipeline; this namespace defines the
  data only (pure — no GPU calls, matching the Rust source it is ported
  from).

  Ported from kami-engine/kami-geo/src/billboard.rs (Rust, deleted from
  the working tree pre-commit; recovered from git history).

  Not ported: the Rust `#[repr(C)] derive(bytemuck::Pod, Zeroable)` byte-
  layout attributes on `BillboardInstance` (48-byte GPU vertex-buffer
  packing). Those are a wgpu buffer-upload concern with no Clojure
  equivalent; `billboard-def->instance` below produces the same *field
  values* as plain data — a renderer-side adapter is responsible for
  packing them into a GPU buffer if/when one exists.")

(defn billboard-def
  "A billboard instance to be rendered. Mirrors `BillboardDef::default()`
  merged with any overrides."
  ([] (billboard-def {}))
  ([overrides]
   (merge {:position [0.0 0.0 0.0]
           :size [16.0 16.0]
           :anchor [0.0 0.0]
           :color [1.0 1.0 1.0 1.0]
           :atlas-index 0}
          overrides)))

(defn billboard-def->instance
  "GPU-side billboard instance data (field values only — no byte packing).
  Mirrors `impl From<&BillboardDef> for BillboardInstance`."
  [{:keys [position size anchor color atlas-index]}]
  {:position position
   :atlas-index atlas-index
   :size size
   :anchor anchor
   :color color})
