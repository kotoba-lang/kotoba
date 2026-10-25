/**
 * sumitsubo 墨壺 — exporter registry + format dispatcher.
 * ADR-2606033600.
 */

import { Drawing } from "../geometry/types.js";
import { exportDxf } from "./dxf.js";
import { exportSvg } from "./svg.js";
import { exportObj } from "./obj.js";
import { exportGltf } from "./gltf.js";
import { exportIfc } from "./ifc.js";
import { exportStep } from "./step.js";
import { DwgFallback, exportDwg } from "./dwg.js";

export { exportDxf, exportSvg, exportObj, exportGltf, exportIfc, exportStep, exportDwg };
export type { DwgFallback };

export type ExportFormat = "dxf" | "svg" | "obj" | "gltf" | "ifc" | "step" | "dwg";

/** Per-format honesty metadata (G4): which formats are full vs subset. */
export const EXPORT_FIDELITY: Record<ExportFormat, "full" | "subset" | "fallback"> = {
  dxf: "full", // R12 ASCII subset of entities, but a complete writer
  svg: "full",
  obj: "full",
  gltf: "full",
  ifc: "subset", // IFC4 tessellation subset (N6)
  step: "subset", // AP242 point-set minimal (N2/N6)
  dwg: "fallback", // proprietary → DXF advisory (N1/G5)
};

export interface ExportResult {
  format: ExportFormat;
  fidelity: "full" | "subset" | "fallback";
  /** Text payload for text formats; for dwg, the DXF fallback payload. */
  text?: string;
  dwg?: DwgFallback;
}

export function exportDrawing(d: Drawing, format: ExportFormat): ExportResult {
  const fidelity = EXPORT_FIDELITY[format];
  switch (format) {
    case "dxf":
      return { format, fidelity, text: exportDxf(d) };
    case "svg":
      return { format, fidelity, text: exportSvg(d) };
    case "obj":
      return { format, fidelity, text: exportObj(d) };
    case "gltf":
      return { format, fidelity, text: exportGltf(d) };
    case "ifc":
      return { format, fidelity, text: exportIfc(d) };
    case "step":
      return { format, fidelity, text: exportStep(d) };
    case "dwg": {
      const dwg = exportDwg(d);
      return { format, fidelity, dwg, text: dwg.dxf };
    }
  }
}
