(ns cad-import.ingest.step
  "STEP / IGES -> VehicleAssembly via FreeCAD CLI shell-out.

   Restored from kami-cad-import (kotoba-lang/kami-engine, deleted PR #82,
   \"Remove Rust workspace\"), per ADR-2607010930. Partial port of the
   original `src/ingest/step.rs`.

   NOT PORTED (by design, per ADR-2607010930's zero-dependency /
   portable-data mandate): `from_step_file` in the original crate
   shelled out to the `freecad`/`freecadcmd` CLI binary
   (`std::process::Command`) to convert STEP/IGES to an intermediate
   glTF file, then fed that through the glTF ingest adapter. That is
   inherently a native, OS-process, filesystem-touching operation with
   no portable CLJC equivalent — it is not a *data transformation* in
   the sense the rest of this crate is. A JVM-hosted caller that needs
   this behaviour can freely shell out itself (e.g. via
   `clojure.java.shell/sh`) using `freecad-script` below to build the
   FreeCAD console script, then hand the resulting glTF JSON to
   `cad-import.ingest.gltf/from-gltf-map`.

   PORTED: the pure, portable parts — the FreeCAD console script
   template (`freecad-script`, a pure string-building function with no
   I/O) and the `StepOptions` default shape, so a native-capable caller
   doesn't have to reimplement the FreeCAD invocation contract."
  (:require [cad-import.ingest.gltf :as gltf]))

(defn freecad-script
  "FreeCAD console script that opens a STEP / IGES file at `input` and
   re-exports the entire document as glTF 2.0 at `output`. Pure string
   template — no I/O. Mirrors the original Rust `freecad_script`.

   Annotation propagation (`extras.*`) requires that the source file
   already encode `gftd_part` / `gftd_vehicle` in its STEP `name`
   field — most STEP exporters drop arbitrary metadata, so the practical
   workflow is:

   1. Run this STEP -> glTF conversion (no annotations preserved).
   2. Open the resulting glTF in Blender / VS Code / a text editor.
   3. Decorate each top-level node with `extras.gftd_part = { ... }`.
   4. Run `cad-import.ingest.gltf/from-gltf-map` on the annotated glTF."
  [input output]
  (str "\n"
       "import FreeCAD, Import, ImportGui\n"
       "doc = FreeCAD.newDocument()\n"
       "Import.insert(r'" input "', doc.Name)\n"
       "objs = [o for o in doc.Objects if o.TypeId.startswith('Part::')]\n"
       "ImportGui.export(objs, r'" output "')\n"
       "FreeCAD.closeDocument(doc.Name)\n"))

(defn default-step-options []
  {:intermediate-gltf nil
   :python-postprocess nil
   :ingest (gltf/default-ingest-options)
   :freecad-bin nil})
