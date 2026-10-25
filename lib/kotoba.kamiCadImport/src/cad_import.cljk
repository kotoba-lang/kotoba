(ns cad-import
  "kami-cad-import -- bridge from CAD source to vehicle part graph, JBeam
   topology, and CycloneDX SBOM.

   Restored from kami-cad-import (kotoba-lang/kami-engine, deleted PR #82,
   \"Remove Rust workspace\"), per ADR-2607010930. Ported 1:1 from the
   original `src/lib.rs`, as portable zero-dependency CLJC. See also
   ADR 2605051430 (the original design ADR for this pipeline).

   Pipeline:

   ```text
   STEP / glTF / OpenSCAD source
     |
     v
   cad-import.part/VehicleAssembly
     |-> cad-import.jbeam-emit/emit  -> JBeam data (vehicle.jbeam/load-edn-ready)
     `-> cad-import.sbom/emit        -> CycloneDX 1.5 data -> sbom.etzhayyim.com
   ```

   Unlike the original Rust crate, `jbeam-emit/emit` and `sbom/emit`
   return plain Clojure maps rather than JSON strings — this crate has
   no JSON-library dependency (ADR-2607010930's zero-dependency
   mandate). Callers that need JSON text run the returned map through
   whatever JSON library they already depend on; callers that want to
   load JBeam data straight into a `vehicle.Vehicle` (kotoba-lang/kami-vehicle,
   also restored to CLJC under the same ADR) can pass `jbeam-emit/emit`'s
   result straight to `vehicle.jbeam/load-edn` with no serialisation
   round-trip at all.

   Phase 0/1 PoC scope carried over from the original crate: programmatic
   / OpenSCAD source and glTF ingest are fully ported. STEP/IGES ingest's
   *pure* parts (the FreeCAD console-script builder) are ported; the
   `freecad` CLI shell-out itself is intentionally not, since process
   I/O has no portable CLJC equivalent — see `cad-import.ingest.step`'s
   docstring."
  (:require [cad-import.part]
            [cad-import.jbeam-emit]
            [cad-import.sbom]
            [cad-import.ingest]
            [cad-import.register]
            [cad-import.demos]))
