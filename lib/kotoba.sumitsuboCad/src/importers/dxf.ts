/**
 * sumitsubo 墨壺 — DXF importer (SUBSET).
 * ADR-2606033600. Reads the openly-published DXF group-code stream: LINE, CIRCLE,
 * ARC, POINT, LWPOLYLINE and old-style POLYLINE/VERTEX, plus LAYER table colours.
 * Other entity types are skipped (G4 honesty). Cleanroom: no vendor code.
 */

import { Drawing, Entity, Layer, Unit, WHITE, v3 } from "../geometry/types.js";

interface Pair {
  code: number;
  value: string;
}

function tokenize(text: string): Pair[] {
  const lines = text.split(/\r?\n/);
  const pairs: Pair[] = [];
  for (let i = 0; i + 1 < lines.length; i += 2) {
    const code = parseInt(lines[i].trim(), 10);
    if (Number.isNaN(code)) continue;
    pairs.push({ code, value: lines[i + 1] });
  }
  return pairs;
}

export function importDxf(text: string, name = "imported", unit: Unit = "mm"): Drawing {
  const pairs = tokenize(text);
  const layers: Layer[] = [{ name: "0", color: WHITE, visible: true }];
  const entities: Entity[] = [];
  let i = 0;
  let n = 0;
  const id = (p: string) => `${p}${++n}`;

  // walk to ENTITIES section
  while (i < pairs.length && !(pairs[i].code === 2 && pairs[i].value.trim() === "ENTITIES")) i++;
  i++;

  const collect = (): Map<number, string[]> => {
    const map = new Map<number, string[]>();
    i++; // skip the 0/<TYPE> already read by caller
    while (i < pairs.length && pairs[i].code !== 0) {
      const { code, value } = pairs[i];
      if (!map.has(code)) map.set(code, []);
      map.get(code)!.push(value);
      i++;
    }
    return map;
  };
  const num = (m: Map<number, string[]>, code: number, idx = 0, def = 0): number => {
    const a = m.get(code);
    return a && a[idx] !== undefined ? parseFloat(a[idx]) : def;
  };
  const str = (m: Map<number, string[]>, code: number, def = "0"): string =>
    m.get(code)?.[0]?.trim() ?? def;

  while (i < pairs.length) {
    if (pairs[i].code !== 0) {
      i++;
      continue;
    }
    const type = pairs[i].value.trim();
    if (type === "ENDSEC" || type === "EOF") break;

    if (type === "LINE") {
      const m = collect();
      entities.push({
        id: id("l"),
        kind: "line",
        layer: str(m, 8),
        a: v3(num(m, 10), num(m, 20), num(m, 30)),
        b: v3(num(m, 11), num(m, 21), num(m, 31)),
      });
    } else if (type === "CIRCLE") {
      const m = collect();
      entities.push({
        id: id("c"),
        kind: "circle",
        layer: str(m, 8),
        center: v3(num(m, 10), num(m, 20), num(m, 30)),
        radius: num(m, 40),
      });
    } else if (type === "ARC") {
      const m = collect();
      entities.push({
        id: id("a"),
        kind: "arc",
        layer: str(m, 8),
        center: v3(num(m, 10), num(m, 20), num(m, 30)),
        radius: num(m, 40),
        startAngle: num(m, 50),
        endAngle: num(m, 51),
      });
    } else if (type === "POINT") {
      const m = collect();
      entities.push({
        id: id("p"),
        kind: "point",
        layer: str(m, 8),
        at: v3(num(m, 10), num(m, 20), num(m, 30)),
      });
    } else if (type === "LWPOLYLINE") {
      const m = collect();
      const xs = m.get(10) ?? [];
      const ys = m.get(20) ?? [];
      const pts = xs.map((x, k) => v3(parseFloat(x), parseFloat(ys[k] ?? "0")));
      const flag = num(m, 70);
      entities.push({
        id: id("pl"),
        kind: "polyline",
        layer: str(m, 8),
        points: pts,
        closed: (flag & 1) === 1,
      });
    } else if (type === "POLYLINE") {
      // old-style: header then VERTEX* then SEQEND
      const m = collect();
      const closed = (num(m, 70) & 1) === 1;
      const layer = str(m, 8);
      const pts = [];
      while (i < pairs.length && pairs[i].code === 0 && pairs[i].value.trim() === "VERTEX") {
        const vm = collect();
        pts.push(v3(num(vm, 10), num(vm, 20), num(vm, 30)));
      }
      if (i < pairs.length && pairs[i].code === 0 && pairs[i].value.trim() === "SEQEND") collect();
      entities.push({ id: id("pl"), kind: "polyline", layer, points: pts, closed });
    } else {
      collect(); // skip unknown entity
    }

    // ensure layers exist
    for (const e of entities) {
      if (!layers.some((l) => l.name === e.layer)) {
        layers.push({ name: e.layer, color: WHITE, visible: true });
      }
    }
  }

  return { name, unit, layers, entities, sourcing: "authoritative" };
}
