/**
 * sumitsubo 墨壺 — kotoba EAVT Datom bridge.
 * ADR-2606033600 §G2. Serialize a Drawing to kotoba Datoms (the canonical state home,
 * ADR-2605262130 / 2605312345). Entities live under the `:dwg.*` attribute namespace.
 *
 * A Datom is [entity, attribute, value] (transaction + op are stamped by kotoba on
 * assert). We emit assertion tuples; the host (py ingest or kotoba-server) transacts.
 */

import { Drawing } from "../geometry/types.js";

export type Datom = [string, string, string | number | boolean];

export function drawingToDatoms(d: Drawing, drawingId: string): Datom[] {
  const out: Datom[] = [];
  out.push([drawingId, ":dwg/id", drawingId]);
  out.push([drawingId, ":dwg/name", d.name]);
  out.push([drawingId, ":dwg/unit", d.unit]);
  out.push([drawingId, ":dwg/sourcing", d.sourcing]);

  for (const l of d.layers) {
    const lid = `${drawingId}.layer.${l.name}`;
    out.push([lid, ":dwg.layer/id", lid]);
    out.push([lid, ":dwg.layer/name", l.name]);
    out.push([lid, ":dwg.layer/of", drawingId]);
    out.push([lid, ":dwg.layer/color", `${l.color.r},${l.color.g},${l.color.b}`]);
  }

  for (const e of d.entities) {
    const id = `${drawingId}.${e.id}`;
    out.push([id, ":dwg.entity/id", id]);
    out.push([id, ":dwg.entity/of", drawingId]);
    out.push([id, ":dwg.entity/kind", e.kind]);
    out.push([id, ":dwg.entity/layer", e.layer]);
    // geometry encoded compactly as a coordinate string (kotoba value)
    switch (e.kind) {
      case "point":
        out.push([id, ":dwg.entity/geom", `${e.at.x} ${e.at.y} ${e.at.z}`]);
        break;
      case "line":
        out.push([id, ":dwg.entity/geom", `${e.a.x} ${e.a.y} ${e.a.z} -> ${e.b.x} ${e.b.y} ${e.b.z}`]);
        break;
      case "polyline":
        out.push([id, ":dwg.entity/geom", e.points.map((p) => `${p.x} ${p.y} ${p.z}`).join(" | ")]);
        out.push([id, ":dwg.entity/closed", e.closed]);
        break;
      case "circle":
        out.push([id, ":dwg.entity/geom", `c=${e.center.x} ${e.center.y} ${e.center.z} r=${e.radius}`]);
        break;
      case "arc":
        out.push([id, ":dwg.entity/geom", `c=${e.center.x} ${e.center.y} r=${e.radius} ${e.startAngle}..${e.endAngle}`]);
        break;
      case "mesh":
        out.push([id, ":dwg.entity/verts", e.vertices.length]);
        out.push([id, ":dwg.entity/tris", e.triangles.length]);
        break;
    }
  }
  return out;
}

/** Render Datoms as kotoba transaction EDN (`[:db/add e a v]` form). */
export function datomsToTxEdn(datoms: Datom[]): string {
  const v = (x: string | number | boolean) =>
    typeof x === "string" ? JSON.stringify(x) : String(x);
  const body = datoms.map(([e, a, val]) => `  [:db/add ${JSON.stringify(e)} ${a} ${v(val)}]`).join("\n");
  return `[\n${body}\n]\n`;
}
