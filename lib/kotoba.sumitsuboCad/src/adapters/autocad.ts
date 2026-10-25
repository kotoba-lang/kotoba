/**
 * sumitsubo 墨壺 — Autodesk AutoCAD published-API-SHAPE adapter (cleanroom).
 * ADR-2606033600 §G1/N1.
 *
 * Two façades mirroring AutoCAD's PUBLISHED interfaces, translated onto the kami kernel:
 *  - `AcadDatabase` / `BlockTableRecord` — the ObjectARX / AutoCAD .NET (Autodesk.AutoCAD
 *    .DatabaseServices) object shapes (AddLine/AddCircle/AddArc/AddPolyline/AddExtrudedSolid).
 *  - `command()` — an AutoLISP/command-line-shaped helper ("LINE", "CIRCLE", "PLINE", …).
 *
 * NO Autodesk SDK code/headers/trademarked sources — only the public call shapes. DWG (the
 * native format) is NOT produced here; export via the DWG fallback (proprietary, G5). "AutoCAD"
 * / "Autodesk" are used nominatively (interop), not as endorsement.
 */

import { Kernel } from "../geometry/kernel.js";
import { Drawing } from "../geometry/types.js";

/** ObjectARX/.NET-shaped block record. Coordinates are AutoCAD WCS (passed as mm). */
export class BlockTableRecord {
  constructor(
    private k: Kernel,
    private layer = "0",
  ) {}

  setLayer(name: string): void {
    this.k.layer(name);
    this.layer = name;
  }

  /** .NET: AddLine via new Line(p1,p2). */
  AddLine(p1: [number, number, number?], p2: [number, number, number?]): string {
    return this.k.line(
      { x: p1[0], y: p1[1], z: p1[2] ?? 0 },
      { x: p2[0], y: p2[1], z: p2[2] ?? 0 },
      this.layer,
    ).id;
  }

  /** .NET: new Circle(center, normal, radius). */
  AddCircle(center: [number, number, number?], radius: number): string {
    return this.k.circle(center[0], center[1], radius, this.layer).id;
  }

  /** .NET: new Arc(center, radius, startAngleRad, endAngleRad). Angles in RADIANS (ARX). */
  AddArc(center: [number, number], radius: number, startRad: number, endRad: number): string {
    const deg = (r: number) => (r * 180) / Math.PI;
    return this.k.arc(center[0], center[1], radius, deg(startRad), deg(endRad), this.layer).id;
  }

  /** .NET: Polyline.AddVertexAt(...) collapsed to a single call. */
  AddPolyline(points: [number, number][], closed = false): string {
    return this.k.polyline(
      points.map(([x, y]) => ({ x, y, z: 0 })),
      closed,
      this.layer,
    ).id;
  }

  /** .NET: Solid3d.CreateExtrudedSolid(region, height, taper). taper ignored in R0. */
  AddExtrudedSolid(profile: [number, number][], height: number): string {
    return this.k.extrude(profile, height, this.layer).id;
  }
}

/** ObjectARX/.NET-shaped database (single model-space block record in R0). */
export class AcadDatabase {
  readonly modelSpace: BlockTableRecord;
  private k: Kernel;

  constructor(name = "autocad-import") {
    this.k = new Kernel(name, "mm");
    this.modelSpace = new BlockTableRecord(this.k);
  }

  /**
   * AutoLISP / command-line-shaped helper. Mirrors the documented command tokens.
   * Returns the created entity id (or undefined for layer/no-geometry commands).
   */
  command(cmd: string, ...args: number[] | string[]): string | undefined {
    const c = String(cmd).toUpperCase().replace(/^[._]/, "");
    const n = (i: number) => Number(args[i]);
    switch (c) {
      case "LINE":
        return this.modelSpace.AddLine([n(0), n(1)], [n(2), n(3)]);
      case "CIRCLE":
        return this.modelSpace.AddCircle([n(0), n(1)], n(2));
      case "ARC":
        // command form here: cx cy r startDeg endDeg
        return this.k.arc(n(0), n(1), n(2), n(3), n(4)).id;
      case "POINT":
        return this.k.point(n(0), n(1)).id;
      case "RECTANG":
      case "RECTANGLE": {
        const x = Math.min(n(0), n(2));
        const y = Math.min(n(1), n(3));
        return this.k.rect(x, y, Math.abs(n(2) - n(0)), Math.abs(n(3) - n(1))).id;
      }
      case "PLINE":
      case "POLYLINE": {
        const pts: [number, number][] = [];
        for (let i = 0; i + 1 < args.length; i += 2) pts.push([Number(args[i]), Number(args[i + 1])]);
        return this.modelSpace.AddPolyline(pts, false);
      }
      case "LAYER":
        this.modelSpace.setLayer(String(args[0]));
        return undefined;
      default:
        throw new Error(`autocad.command: unsupported token ${c}`);
    }
  }

  document(): Drawing {
    return this.k.drawing;
  }
}
