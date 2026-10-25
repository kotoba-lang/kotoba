/**
 * sumitsubo 墨壺 — DWG export boundary (PROPRIETARY — cleanroom fallback).
 * ADR-2606033600 §G5 / N1.
 *
 * Autodesk DWG is an undocumented proprietary binary format. We do NOT reverse-engineer
 * or natively write it (cleanroom invariant). Instead we return the equivalent DXF
 * payload plus an honest advisory: convert DXF→DWG with an external Open Design Alliance
 * (ODA) / LibreDWG round-trip outside this SDK. This keeps interop useful without
 * touching proprietary internals.
 */

import { Drawing } from "../geometry/types.js";
import { exportDxf } from "./dxf.js";

export interface DwgFallback {
  format: "dwg";
  native: false;
  advisory: "DWG_PROPRIETARY";
  /** DXF payload to feed an external DXF→DWG converter (ODA File Converter / LibreDWG). */
  dxf: string;
  message: string;
}

export function exportDwg(d: Drawing): DwgFallback {
  return {
    format: "dwg",
    native: false,
    advisory: "DWG_PROPRIETARY",
    dxf: exportDxf(d),
    message:
      "DWG is proprietary (Autodesk) and is not written natively by sumitsubo (cleanroom, ADR-2606033600 N1). " +
      "Use the returned DXF with an external DXF→DWG converter (ODA File Converter or LibreDWG).",
  };
}
