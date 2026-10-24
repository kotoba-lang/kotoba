(ns eng-web.cam
  "CAM job-input synthesis, restored from `kami-eng-web/src/lib.rs`
  (`cam_generate_gcode` wasm entry point), part of the legacy `kami-engine`
  Rust workspace deleted in kotoba-lang/kami-engine PR #82.
  See ADR-2607010930 (`com-junkawasaki/root`).

  Portable: the fixed-default `Tool`/`Stock`/pocket-`CamOperation`/
  `GcodeConfig` construction the original builds from the wasm entry
  point's simple numeric params before handing off to `kami_cam`.
  Excluded: the actual `CamJob::generate_toolpath`/`gcode::generate_gcode`
  synthesis, which lives in the unported `kami-cam` crate.")

(defn tool-defaults
  "Build the End Mill `Tool` used by `cam_generate_gcode`: fixed id/name/
  type/flute-count/material/coating, with flute/overall length derived from
  `depth` (2x / 4x), mirroring the original Rust struct literal."
  [tool-diameter depth]
  {:id 1
   :name "End Mill"
   :tool-type :end-mill
   :diameter tool-diameter
   :flute-length (* depth 2.0)
   :overall-length (* depth 4.0)
   :flute-count 4
   :corner-radius 0.0
   :material :carbide
   :coating "TiAlN"})

(defn stock-defaults
  "Build the `Stock` block used by `cam_generate_gcode`: `width`/`height`
  as given, with a 1.5x `depth` margin, and aluminum-6061 material."
  [width height depth]
  {:shape {:type :block :width width :height height :depth (* depth 1.5)}
   :material :aluminum-6061})

(defn pocket-operation
  "Build the single zigzag `Pocket` `CamOperation` used by
  `cam_generate_gcode`, with a 5.0-unit margin on each side and stepover
  fixed at 0.4x tool diameter, mirroring the original Rust struct literal."
  [width height depth tool-diameter feed-rate spindle-rpm]
  {:type :pocket
   :depth depth
   :stepover (* tool-diameter 0.4)
   :strategy :zigzag
   :feed-rate feed-rate
   :spindle-rpm spindle-rpm
   :pocket-min [5.0 5.0 0.0]
   :pocket-max [(- width 5.0) (- height 5.0) 0.0]})

(defn gcode-config
  "The fixed `GcodeConfig` used by `cam_generate_gcode`: 3-axis mill, Fanuc
  post-processor, millimeters, G54, program 1, coolant on."
  []
  {:machine-type :mill-3axis
   :post-processor :fanuc
   :units :millimeters
   :safe-height 25.0
   :coordinate-system :g54
   :program-number 1
   :coolant true})
