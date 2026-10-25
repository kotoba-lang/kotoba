/**
 * @etzhayyim/sumitsubo-cad — cleanroom CAD interop for kami-engine-sdk.
 * ADR-2606033600. 墨壺 — the carpenter's ink-line marking instrument.
 *
 * Apache-2.0 + etzhayyim Charter Compliance Rider v2.0 (ADR-2605192200).
 *
 * Re-export target for kami-engine-sdk:
 *   export * from '@etzhayyim/sumitsubo-cad';
 *
 * Surfaces:
 *   - geometry model + modeling kernel (neutral ModelOp vocabulary)
 *   - exporters: dxf / svg / obj / gltf / ifc(subset) / step(subset) / dwg(fallback)
 *   - importer: dxf(subset)
 *   - published-API-shape adapters: VectorScript (Vectorworks) / AcadDatabase (AutoCAD)
 *   - kotoba EAVT Datom bridge (canonical state)
 *
 * Cleanroom invariant (G1/N1): no vendor SDK headers, no decompilation, no trademarked
 * code — open format specs (DXF/IFC/STEP/glTF/OBJ) + published API shapes only.
 */

// geometry + kernel
export * from "./geometry/types.js";
export { Kernel, buildDrawing, resetIds } from "./geometry/kernel.js";

// exporters
export {
  exportDrawing,
  exportDxf,
  exportSvg,
  exportObj,
  exportGltf,
  exportIfc,
  exportStep,
  exportDwg,
  EXPORT_FIDELITY,
} from "./exporters/index.js";
export type { ExportFormat, ExportResult, DwgFallback } from "./exporters/index.js";

// importer
export { importDxf } from "./importers/dxf.js";

// adapters
export { VectorScript } from "./adapters/vectorworks.js";
export { AcadDatabase, BlockTableRecord } from "./adapters/autocad.js";

// kotoba bridge
export { drawingToDatoms, datomsToTxEdn } from "./kotoba/datom.js";
export type { Datom } from "./kotoba/datom.js";

/** SDK metadata (G1 cleanroom posture is part of the public contract). */
export const SUMITSUBO_CAD = {
  adr: "2606033600",
  glyph: "墨壺",
  cleanroom: true,
  license: "Apache-2.0 + Charter-Rider-v2.0",
  formats: ["dxf", "svg", "obj", "gltf", "ifc", "step", "dwg"] as const,
  adapters: ["vectorworks", "autocad"] as const,
} as const;
