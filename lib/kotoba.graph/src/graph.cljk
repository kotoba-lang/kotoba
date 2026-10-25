(ns graph
  "kami-graph: force-directed graph layout + mesh-instance-data generation for
  wgpu-style rendering.

  Restored from `kami-engine/kami-graph/src/lib.rs` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as zero-dependency
  portable `.cljc`, per ADR-2607010930 (the clj-wgsl migration). Ingests
  haisen/systemofsystem JSON (already parsed into plain maps, see [[graph.data]])
  and produces node positions ([[graph.layout]]) plus renderer-agnostic instance
  data: per-instance 4x4 transforms, per-instance RGBA colors, and interleaved
  line-vertex data for edges. Actual rendering (wgpu PBR pipeline, orthographic
  camera) stays in substrate/native code — this namespace only computes the pure
  numeric payloads.

  `Mat4`/`Vec3` are represented as plain vectors: a 4x4 matrix is 16 floats in
  column-major order (matching `glam::Mat4::to_cols_array`); a vec3 is `[x y z]`.")

;; --- colors ---------------------------------------------------------------

(defn edge-color
  "Edge type color palette (RGBA f32, 0..1) — Nintendo-inspired vivid pastels.
  Ported 1:1 from `edge_color`."
  [edge-type]
  (case edge-type
    "invoke" [0.98 0.34 0.40 1.0]
    "writes" [0.20 0.75 0.95 1.0]
    "reads" [0.40 0.90 0.45 1.0]
    "subscribe" [1.0 0.75 0.20 1.0]
    "follow" [0.70 0.40 0.95 1.0]
    "workers_rpc" [0.20 0.75 0.95 1.0]
    "xrpc" [0.40 0.90 0.45 1.0]
    "subscribe_repos" [1.0 0.75 0.20 1.0]
    "http" [0.65 0.70 0.75 1.0]
    [0.60 0.65 0.70 1.0]))

(def palette
  "Group color palette — Nintendo-inspired bright pastels (Splatoon/Animal
  Crossing). Ported 1:1 from the `PALETTE` const."
  [[0.98 0.34 0.40 1.0]
   [0.20 0.75 0.95 1.0]
   [0.40 0.90 0.45 1.0]
   [1.0 0.75 0.20 1.0]
   [0.70 0.40 0.95 1.0]
   [0.15 0.85 0.70 1.0]
   [1.0 0.55 0.30 1.0]
   [0.95 0.45 0.70 1.0]
   [0.55 0.55 1.0 1.0]
   [0.95 0.85 0.25 1.0]
   [0.30 0.90 0.80 1.0]
   [0.85 0.55 0.95 1.0]
   [0.50 0.95 0.40 1.0]
   [1.0 0.65 0.50 1.0]
   [0.45 0.80 1.0 1.0]
   [0.90 0.40 0.40 1.0]
   [0.40 0.70 0.95 1.0]
   [0.80 0.95 0.40 1.0]
   [0.95 0.60 0.80 1.0]
   [0.70 0.90 0.60 1.0]])

(defn group-color
  "Ported 1:1 from `group_color`."
  [group-index]
  (nth palette (mod group-index (count palette))))

;; --- matrix helpers (glam::Mat4::from_scale_rotation_translation, rotation
;;     always IDENTITY in this crate, so this is scale-then-translate only) ---

(defn mat4-scale-translate
  "Build a 4x4 column-major transform (as 16 floats, matching
  `glam::Mat4::to_cols_array`) that scales by `[sx sy sz]` then translates by
  `[tx ty tz]` (identity rotation)."
  [sx sy sz tx ty tz]
  [sx 0.0 0.0 0.0
   0.0 sy 0.0 0.0
   0.0 0.0 sz 0.0
   tx ty tz 1.0])

;; --- ForceLayout instance data ---------------------------------------------

(defn build-node-instances
  "Build instance transforms for graph nodes (translate to position, scale by
  radius). Ported 1:1 from `build_node_instances`."
  [force-layout]
  (mapv (fn [n]
          (let [s (* (:radius n) 0.1)]
            (mat4-scale-translate s s s (:x n) (:y n) 0.0)))
        (:nodes force-layout)))

(defn build-node-colors
  "Build instance material colors for graph nodes (albedo per instance).
  Ported 1:1 from `build_node_colors`."
  [force-layout]
  (mapv (fn [n] (group-color (:group-index n))) (:nodes force-layout)))

(defn build-edge-lines
  "Build line vertex data for edges: pairs of (pos, color) per endpoint.
  Returns an interleaved `[x y z r g b a]` x2 vector per edge. Ported 1:1 from
  `build_edge_lines`."
  [force-layout]
  (let [nodes (:nodes force-layout)]
    (reduce (fn [verts edge]
              (let [from (nodes (:from-idx edge))
                    to (nodes (:to-idx edge))
                    [r g b a] (edge-color (:edge-type edge))]
                (-> verts
                    (conj (:x from) (:y from) 0.0 r g b a)
                    (conj (:x to) (:y to) 0.0 r g b a))))
            []
            (:edges force-layout))))

;; --- PcbLayout instance data -------------------------------------------

(defn build-node-instances-pcb
  "Build instance transforms for PCB layout nodes. Ported 1:1 from
  `build_node_instances_pcb` (note the PCB layout is drawn in the XZ plane:
  world `y` is always 0, layout `y` maps to world `z`)."
  [pcb-layout]
  (mapv (fn [n]
          (let [s (* (:radius n) 0.1)]
            (mat4-scale-translate s s s (:x n) 0.0 (:y n))))
        (:nodes pcb-layout)))

(defn build-node-colors-pcb
  "Build node colors for PCB layout. Ported 1:1 from `build_node_colors_pcb`."
  [pcb-layout]
  (mapv (fn [n] (group-color (:group-index n))) (:nodes pcb-layout)))

;; --- camera extents ---------------------------------------------------

(defn graph-camera-extent
  "Camera extent (width, height, center) for an orthographic projection
  covering a force-directed graph. Ported 1:1 from `graph_camera_extent`."
  [force-layout padding]
  (let [nodes (:nodes force-layout)
        min-x (reduce min ##Inf (map :x nodes))
        min-y (reduce min ##Inf (map :y nodes))
        max-x (reduce max ##-Inf (map :x nodes))
        max-y (reduce max ##-Inf (map :y nodes))
        cx (* (+ min-x max-x) 0.5)
        cy (* (+ min-y max-y) 0.5)
        w (+ (- max-x min-x) padding)
        h (+ (- max-y min-y) padding)]
    [w h [cx cy 0.0]]))

(defn graph-camera-extent-pcb
  "Camera extent for PCB layout (app nodes + bus lines). Ported 1:1 from
  `graph_camera_extent_pcb`: only nodes with `radius > 0` contribute to the
  bounding box (collection nodes, radius 0, are excluded), and bus lines only
  extend the `min-y` bound (matching the original's asymmetric treatment)."
  [pcb-layout padding]
  (let [app-nodes (filter #(pos? (:radius %)) (:nodes pcb-layout))
        min-x (reduce min ##Inf (map :x app-nodes))
        min-y0 (reduce min ##Inf (map :y app-nodes))
        max-x (reduce max ##-Inf (map :x app-nodes))
        max-y (reduce max ##-Inf (map :y app-nodes))
        min-y (reduce min min-y0 (map :y (:buses pcb-layout)))
        cx (* (+ min-x max-x) 0.5)
        cy (* (+ min-y max-y) 0.5)
        w (+ (- max-x min-x) padding)
        h (+ (- max-y min-y) padding)]
    [w h [cx cy 0.0]]))
