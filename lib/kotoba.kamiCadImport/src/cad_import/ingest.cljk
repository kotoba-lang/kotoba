(ns cad-import.ingest
  "Source-format ingest adapters.

   Restored from kami-cad-import (kotoba-lang/kami-engine, deleted PR #82,
   \"Remove Rust workspace\"), per ADR-2607010930. Mirrors the original
   `src/ingest.rs` module list.

   Each adapter converts a stream of primitives + annotations into a
   `VehicleAssembly`: `cad-import.ingest.scad`, `cad-import.ingest.gltf`,
   and (partially — see its docstring) `cad-import.ingest.step`."
  (:require [cad-import.ingest.scad]
            [cad-import.ingest.gltf]
            [cad-import.ingest.step]))
