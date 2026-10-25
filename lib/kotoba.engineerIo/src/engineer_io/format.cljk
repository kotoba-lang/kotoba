(ns engineer-io.format
  "Supported engineering file formats + extension/mime-type/detection.
  Restored from kami-eng-io's `FileFormat` enum (kami-engine/kami-eng-io/
  src/lib.rs, deleted PR #82)."
  (:require [kotoba.lang.text :as str]))

(def formats
  "All supported formats as keywords, grouped by domain in the original enum
  order (CAD / EDA / RTL / CAM)."
  [;; CAD
   :step-ap203 :step-ap214 :iges :stl :stl-binary :obj :gltf-json :glb
   ;; EDA
   :gerber-rs274x :excellon-drill :odb-plus-plus :edif-netlist :spice-netlist
   ;; RTL
   :verilog :vhdl :system-verilog :vcd :liberty-timing :lef-def :sdf
   ;; CAM
   :gcode])

(def ^:private extensions
  {:step-ap203 "step" :step-ap214 "step" :iges "igs" :stl "stl"
   :stl-binary "stl" :obj "obj" :gltf-json "gltf" :glb "glb"
   :gerber-rs274x "gbr" :excellon-drill "drl" :odb-plus-plus "tgz"
   :edif-netlist "edf" :spice-netlist "cir" :verilog "v" :vhdl "vhd"
   :system-verilog "sv" :vcd "vcd" :liberty-timing "lib" :lef-def "lef"
   :sdf "sdf" :gcode "nc"})

(def ^:private mime-types
  {:step-ap203 "model/step" :step-ap214 "model/step" :iges "model/iges"
   :stl "model/stl" :stl-binary "model/stl" :obj "model/obj"
   :gltf-json "model/gltf+json" :glb "model/gltf-binary"
   :gerber-rs274x "application/x-gerber" :excellon-drill "application/x-excellon"})

(def ^:private extension->format
  {"step" :step-ap214 "stp" :step-ap214
   "igs" :iges "iges" :iges
   "stl" :stl
   "obj" :obj
   "gltf" :gltf-json
   "glb" :glb
   "gbr" :gerber-rs274x "gtl" :gerber-rs274x "gbl" :gerber-rs274x
   "gts" :gerber-rs274x "gbs" :gerber-rs274x "gto" :gerber-rs274x "gbo" :gerber-rs274x
   "drl" :excellon-drill "xln" :excellon-drill
   "edf" :edif-netlist "edif" :edif-netlist
   "cir" :spice-netlist "spice" :spice-netlist "sp" :spice-netlist
   "v" :verilog
   "vhd" :vhdl "vhdl" :vhdl
   "sv" :system-verilog
   "vcd" :vcd
   "lib" :liberty-timing
   "lef" :lef-def "def" :lef-def
   "sdf" :sdf
   "nc" :gcode "ngc" :gcode "gcode" :gcode "tap" :gcode})

(defn extension
  "The canonical file extension for `format` (e.g. `:step-ap214` -> \"step\")."
  [format]
  (get extensions format))

(defn mime-type
  "The MIME type for `format`, or \"application/octet-stream\" if unmapped
  (mirrors the original Rust's `_ => \"application/octet-stream\"` fallback)."
  [format]
  (get mime-types format "application/octet-stream"))

(defn from-extension
  "Detect a format keyword from a file extension string (case-insensitive,
  no leading dot). Returns nil if unrecognized."
  [ext]
  (get extension->format (str/lower ext)))
