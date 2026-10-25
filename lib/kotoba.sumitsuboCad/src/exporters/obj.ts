/**
 * sumitsubo 墨壺 — Wavefront OBJ exporter (open de-facto spec).
 * ADR-2606033600. Meshes → v/f; line + polyline → v/l. Points/circles/arcs omitted
 * (OBJ has no curve primitives in this subset; G4 fidelity honesty).
 */

import { Drawing } from "../geometry/types.js";

export function exportObj(d: Drawing): string {
  let s = `# sumitsubo OBJ export — units=${d.unit}\n`;
  let vbase = 0;
  for (const e of d.entities) {
    if (e.kind === "mesh") {
      s += `o ${e.id}\n`;
      for (const v of e.vertices) s += `v ${v.x} ${v.y} ${v.z}\n`;
      for (const [i, j, k] of e.triangles) {
        s += `f ${vbase + i + 1} ${vbase + j + 1} ${vbase + k + 1}\n`;
      }
      vbase += e.vertices.length;
    } else if (e.kind === "line") {
      s += `o ${e.id}\n`;
      s += `v ${e.a.x} ${e.a.y} ${e.a.z}\nv ${e.b.x} ${e.b.y} ${e.b.z}\n`;
      s += `l ${vbase + 1} ${vbase + 2}\n`;
      vbase += 2;
    } else if (e.kind === "polyline") {
      s += `o ${e.id}\n`;
      for (const v of e.points) s += `v ${v.x} ${v.y} ${v.z}\n`;
      const idx = e.points.map((_, n) => vbase + n + 1);
      if (e.closed) idx.push(vbase + 1);
      s += `l ${idx.join(" ")}\n`;
      vbase += e.points.length;
    }
  }
  return s;
}
