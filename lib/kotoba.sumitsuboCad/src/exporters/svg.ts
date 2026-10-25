/**
 * sumitsubo 墨壺 — SVG exporter (2D XY projection).
 * ADR-2606033600. Open W3C SVG 1.1. Meshes are drawn as projected wireframe edges.
 */

import { Color, Drawing, Entity, Vec3 } from "../geometry/types.js";

function hex(c: Color): string {
  const h = (n: number) => Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, "0");
  return `#${h(c.r)}${h(c.g)}${h(c.b)}`;
}

interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

function pts(e: Entity): Vec3[] {
  switch (e.kind) {
    case "point":
      return [e.at];
    case "line":
      return [e.a, e.b];
    case "polyline":
      return e.points;
    case "circle":
    case "arc":
      return [
        { x: e.center.x - e.radius, y: e.center.y - e.radius, z: 0 },
        { x: e.center.x + e.radius, y: e.center.y + e.radius, z: 0 },
      ];
    case "mesh":
      return e.vertices;
  }
}

function bounds(d: Drawing): Bounds {
  let b: Bounds = { minX: 0, minY: 0, maxX: 100, maxY: 100 };
  let first = true;
  for (const e of d.entities) {
    for (const p of pts(e)) {
      if (first) {
        b = { minX: p.x, minY: p.y, maxX: p.x, maxY: p.y };
        first = false;
      } else {
        b.minX = Math.min(b.minX, p.x);
        b.minY = Math.min(b.minY, p.y);
        b.maxX = Math.max(b.maxX, p.x);
        b.maxY = Math.max(b.maxY, p.y);
      }
    }
  }
  return b;
}

export function exportSvg(d: Drawing): string {
  const b = bounds(d);
  const w = Math.max(1, b.maxX - b.minX);
  const h = Math.max(1, b.maxY - b.minY);
  const layerColor = new Map(d.layers.map((l) => [l.name, l.color]));
  // SVG y grows downward; flip so model +Y is up.
  const X = (x: number) => x - b.minX;
  const Y = (y: number) => b.maxY - y;

  let body = "";
  for (const e of d.entities) {
    const stroke = hex(layerColor.get(e.layer) ?? { r: 0, g: 0, b: 0 });
    const s = `stroke="${stroke}" fill="none" stroke-width="${Math.max(w, h) / 400}"`;
    switch (e.kind) {
      case "point":
        body += `<circle cx="${X(e.at.x)}" cy="${Y(e.at.y)}" r="${Math.max(w, h) / 200}" fill="${stroke}"/>\n`;
        break;
      case "line":
        body += `<line x1="${X(e.a.x)}" y1="${Y(e.a.y)}" x2="${X(e.b.x)}" y2="${Y(e.b.y)}" ${s}/>\n`;
        break;
      case "polyline": {
        const pl = e.points.map((p) => `${X(p.x)},${Y(p.y)}`).join(" ");
        body += `<poly${e.closed ? "gon" : "line"} points="${pl}" ${s}/>\n`;
        break;
      }
      case "circle":
        body += `<circle cx="${X(e.center.x)}" cy="${Y(e.center.y)}" r="${e.radius}" ${s}/>\n`;
        break;
      case "arc": {
        const a0 = (e.startAngle * Math.PI) / 180;
        const a1 = (e.endAngle * Math.PI) / 180;
        const x0 = e.center.x + e.radius * Math.cos(a0);
        const y0 = e.center.y + e.radius * Math.sin(a0);
        const x1 = e.center.x + e.radius * Math.cos(a1);
        const y1 = e.center.y + e.radius * Math.sin(a1);
        let sweep = e.endAngle - e.startAngle;
        if (sweep < 0) sweep += 360;
        const large = sweep > 180 ? 1 : 0;
        body += `<path d="M ${X(x0)} ${Y(y0)} A ${e.radius} ${e.radius} 0 ${large} 0 ${X(x1)} ${Y(y1)}" ${s}/>\n`;
        break;
      }
      case "mesh":
        for (const [i, j, k] of e.triangles) {
          const a = e.vertices[i];
          const bb = e.vertices[j];
          const c = e.vertices[k];
          body += `<polygon points="${X(a.x)},${Y(a.y)} ${X(bb.x)},${Y(bb.y)} ${X(c.x)},${Y(c.y)}" ${s}/>\n`;
        }
        break;
    }
  }

  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">\n` +
    `<!-- sumitsubo SVG export; model units=${d.unit}; 2D XY projection -->\n` +
    body +
    `</svg>\n`
  );
}
