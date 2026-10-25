/**
 * sumitsubo 墨壺 — DXF R12 (AC1009) ASCII exporter.
 * ADR-2606033600.
 *
 * Cleanroom: implemented against the OPENLY PUBLISHED DXF group-code reference
 * (no vendor SDK/headers). R12-compatible: LINE / CIRCLE / ARC / POINT / old-style
 * POLYLINE + 3DFACE for meshes — the broadly-importable subset (G4 fidelity honesty).
 */

import { Drawing, Entity, Vec3 } from "../geometry/types.js";

function g(code: number, value: string | number): string {
  return `${code}\n${value}\n`;
}

function header(): string {
  return (
    g(0, "SECTION") +
    g(2, "HEADER") +
    g(9, "$ACADVER") +
    g(1, "AC1009") +
    g(9, "$INSUNITS") +
    g(70, 4) + // 4 = millimetres
    g(0, "ENDSEC")
  );
}

function tables(d: Drawing): string {
  let s = g(0, "SECTION") + g(2, "TABLES") + g(0, "TABLE") + g(2, "LAYER") + g(70, d.layers.length);
  for (const l of d.layers) {
    s += g(0, "LAYER") + g(2, l.name) + g(70, 0) + g(62, 7) + g(6, "CONTINUOUS");
  }
  s += g(0, "ENDTAB") + g(0, "ENDSEC");
  return s;
}

function pt(prefix: number, p: Vec3): string {
  return g(prefix, p.x) + g(prefix + 10, p.y) + g(prefix + 20, p.z);
}

function entityDxf(e: Entity): string {
  switch (e.kind) {
    case "point":
      return g(0, "POINT") + g(8, e.layer) + pt(10, e.at);
    case "line":
      return g(0, "LINE") + g(8, e.layer) + pt(10, e.a) + pt(11, e.b);
    case "circle":
      return g(0, "CIRCLE") + g(8, e.layer) + pt(10, e.center) + g(40, e.radius);
    case "arc":
      return (
        g(0, "ARC") +
        g(8, e.layer) +
        pt(10, e.center) +
        g(40, e.radius) +
        g(50, e.startAngle) +
        g(51, e.endAngle)
      );
    case "polyline": {
      let s = g(0, "POLYLINE") + g(8, e.layer) + g(66, 1) + g(70, e.closed ? 1 : 0);
      for (const p of e.points) {
        s += g(0, "VERTEX") + g(8, e.layer) + pt(10, p);
      }
      s += g(0, "SEQEND") + g(8, e.layer);
      return s;
    }
    case "mesh": {
      let s = "";
      for (const [i, j, k] of e.triangles) {
        const a = e.vertices[i];
        const b = e.vertices[j];
        const c = e.vertices[k];
        s +=
          g(0, "3DFACE") +
          g(8, e.layer) +
          pt(10, a) +
          pt(11, b) +
          pt(12, c) +
          pt(13, c); // 4th == 3rd → triangular face
      }
      return s;
    }
  }
}

export function exportDxf(d: Drawing): string {
  let body = g(0, "SECTION") + g(2, "ENTITIES");
  for (const e of d.entities) body += entityDxf(e);
  body += g(0, "ENDSEC");
  return header() + tables(d) + body + g(0, "EOF");
}
