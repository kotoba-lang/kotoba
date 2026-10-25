/**
 * sumitsubo 墨壺 — Vectorworks published-API-SHAPE adapter (cleanroom).
 * ADR-2606033600 §G1/N1.
 *
 * A VectorScript-shaped façade. It mirrors the PUBLISHED CALL SHAPES of Vectorworks'
 * scripting vocabulary (procedure names/arity as documented for interoperability) and
 * translates them onto the neutral kami kernel. It contains NO Vectorworks SDK code,
 * headers, or trademarked sources — only the public idea of the call shapes. "Vectorworks"
 * is used nominatively (interop), not as endorsement.
 *
 * Coordinates in VectorScript are in document units; here we pass them straight to the
 * kernel (mm). Marionette-style node graphs reduce to the same op sequence.
 */

import { Kernel } from "../geometry/kernel.js";
import { Drawing } from "../geometry/types.js";

/**
 * VectorScript-shaped command surface. Method names follow the documented VS
 * procedures (Rect, Line, Poly, ArcByCenter, Oval≈Circle, Extrude, Move, Layer).
 * They return the created kernel entity id where relevant.
 */
export class VectorScript {
  private k: Kernel;
  private layer = "0";

  constructor(name = "vectorworks-import") {
    this.k = new Kernel(name, "mm");
  }

  /** VS: CreateLayer / NameClass — set the active class/layer for subsequent geometry. */
  Layer(name: string): void {
    this.k.layer(name);
    this.layer = name;
  }

  /** VS: MoveTo+LineTo collapsed — Line(x1,y1,x2,y2). */
  Line(x1: number, y1: number, x2: number, y2: number): string {
    return this.k.line({ x: x1, y: y1, z: 0 }, { x: x2, y: y2, z: 0 }, this.layer).id;
  }

  /** VS: Rect(x1,y1,x2,y2) — rectangle by two opposite corners. */
  Rect(x1: number, y1: number, x2: number, y2: number): string {
    const x = Math.min(x1, x2);
    const y = Math.min(y1, y2);
    return this.k.rect(x, y, Math.abs(x2 - x1), Math.abs(y2 - y1), this.layer).id;
  }

  /** VS: Oval(x1,y1,x2,y2) approximated as a circle (bbox mean radius). */
  Oval(x1: number, y1: number, x2: number, y2: number): string {
    const cx = (x1 + x2) / 2;
    const cy = (y1 + y2) / 2;
    const r = (Math.abs(x2 - x1) + Math.abs(y2 - y1)) / 4;
    return this.k.circle(cx, cy, r, this.layer).id;
  }

  /** VS: ArcByCenter(cx,cy,r,startDeg,sweepDeg). */
  ArcByCenter(cx: number, cy: number, r: number, start: number, sweep: number): string {
    return this.k.arc(cx, cy, r, start, start + sweep, this.layer).id;
  }

  /** VS: Poly(...pts) / ClosePoly — polyline from flat coordinate pairs. */
  Poly(coords: number[], closed = false): string {
    const pts = [];
    for (let i = 0; i + 1 < coords.length; i += 2) pts.push({ x: coords[i], y: coords[i + 1], z: 0 });
    return this.k.polyline(pts, closed, this.layer).id;
  }

  /** VS: Extrude — profile (flat coordinate pairs) extruded by `height`. */
  Extrude(coords: number[], height: number): string {
    const prof: [number, number][] = [];
    for (let i = 0; i + 1 < coords.length; i += 2) prof.push([coords[i], coords[i + 1]]);
    return this.k.extrude(prof, height, this.layer).id;
  }

  /** VS: HMove / Move(h, dx, dy). */
  Move(id: string, dx: number, dy: number, dz = 0): void {
    this.k.move(id, dx, dy, dz);
  }

  /** Finalize and return the neutral Drawing. */
  document(): Drawing {
    return this.k.drawing;
  }
}
