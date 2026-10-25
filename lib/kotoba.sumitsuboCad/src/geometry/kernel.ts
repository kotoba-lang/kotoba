/**
 * sumitsubo 墨壺 — modeling kernel (cleanroom).
 * ADR-2606033600.
 *
 * A small, mesh-first modeling kernel that materialises the neutral ModelOp
 * vocabulary into Drawing entities. Mesh-first + light prismatic CSG only — exact
 * B-rep/ACIS-class solid modeling is an explicit non-goal (ADR N2). The kernel is
 * the TS half of the shared op vocabulary; the python generative cell emits the
 * identical ops.
 */

import {
  Color,
  DEFAULT_LAYER,
  Drawing,
  Entity,
  Layer,
  MeshEntity,
  ModelOp,
  Unit,
  Vec3,
  WHITE,
  v3,
} from "./types.js";

let _seq = 0;
/** Deterministic-ish id; callers may override via opts for reproducible tests. */
function nextId(prefix: string): string {
  _seq += 1;
  return `${prefix}${_seq}`;
}

/** Reset the entity-id counter (test determinism). */
export function resetIds(): void {
  _seq = 0;
}

export class Kernel {
  readonly drawing: Drawing;

  constructor(name = "untitled", unit: Unit = "mm") {
    this.drawing = {
      name,
      unit,
      layers: [{ name: DEFAULT_LAYER, color: WHITE, visible: true }],
      entities: [],
      sourcing: "representative",
    };
  }

  layer(name: string, color: Color = WHITE): Layer {
    let l = this.drawing.layers.find((x) => x.name === name);
    if (!l) {
      l = { name, color, visible: true };
      this.drawing.layers.push(l);
    } else {
      l.color = color;
    }
    return l;
  }

  private resolveLayer(name?: string): string {
    const n = name ?? DEFAULT_LAYER;
    if (!this.drawing.layers.some((l) => l.name === n)) this.layer(n);
    return n;
  }

  private push<E extends Entity>(e: E): E {
    this.drawing.entities.push(e);
    return e;
  }

  point(x: number, y: number, z = 0, layer?: string) {
    return this.push({
      id: nextId("p"),
      kind: "point",
      layer: this.resolveLayer(layer),
      at: v3(x, y, z),
    });
  }

  line(a: Vec3, b: Vec3, layer?: string) {
    return this.push({
      id: nextId("l"),
      kind: "line",
      layer: this.resolveLayer(layer),
      a,
      b,
    });
  }

  polyline(points: Vec3[], closed = false, layer?: string) {
    return this.push({
      id: nextId("pl"),
      kind: "polyline",
      layer: this.resolveLayer(layer),
      points,
      closed,
    });
  }

  rect(x: number, y: number, w: number, h: number, layer?: string) {
    const pts = [v3(x, y), v3(x + w, y), v3(x + w, y + h), v3(x, y + h)];
    return this.polyline(pts, true, layer);
  }

  circle(cx: number, cy: number, r: number, layer?: string) {
    return this.push({
      id: nextId("c"),
      kind: "circle",
      layer: this.resolveLayer(layer),
      center: v3(cx, cy),
      radius: r,
    });
  }

  arc(
    cx: number,
    cy: number,
    r: number,
    start: number,
    end: number,
    layer?: string,
  ) {
    return this.push({
      id: nextId("a"),
      kind: "arc",
      layer: this.resolveLayer(layer),
      center: v3(cx, cy),
      radius: r,
      startAngle: start,
      endAngle: end,
    });
  }

  /** Axis-aligned box as a closed triangle mesh (12 tris). */
  box(
    x: number,
    y: number,
    z: number,
    w: number,
    d: number,
    h: number,
    layer?: string,
  ): MeshEntity {
    const verts: Vec3[] = [
      v3(x, y, z),
      v3(x + w, y, z),
      v3(x + w, y + d, z),
      v3(x, y + d, z),
      v3(x, y, z + h),
      v3(x + w, y, z + h),
      v3(x + w, y + d, z + h),
      v3(x, y + d, z + h),
    ];
    const tris: [number, number, number][] = [
      [0, 1, 2],
      [0, 2, 3], // bottom
      [4, 6, 5],
      [4, 7, 6], // top
      [0, 4, 5],
      [0, 5, 1], // front
      [1, 5, 6],
      [1, 6, 2], // right
      [2, 6, 7],
      [2, 7, 3], // back
      [3, 7, 4],
      [3, 4, 0], // left
    ];
    return this.push({
      id: nextId("m"),
      kind: "mesh",
      layer: this.resolveLayer(layer),
      vertices: verts,
      triangles: tris,
    });
  }

  /**
   * Extrude a 2D profile (XY polygon, CCW) by `height` along +Z into a prism mesh.
   * The profile must be simple (non-self-intersecting); triangulated by fan (convex)
   * — concave profiles are accepted but fan-triangulation may be approximate (G4).
   */
  extrude(
    profile: [number, number][],
    height: number,
    layer?: string,
  ): MeshEntity {
    const n = profile.length;
    if (n < 3) throw new Error("extrude: profile needs >= 3 points");
    const verts: Vec3[] = [];
    for (const [px, py] of profile) verts.push(v3(px, py, 0));
    for (const [px, py] of profile) verts.push(v3(px, py, height));
    const tris: [number, number, number][] = [];
    // bottom + top caps (fan)
    for (let i = 1; i < n - 1; i++) {
      tris.push([0, i, i + 1]);
      tris.push([n, n + i + 1, n + i]);
    }
    // side walls
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n;
      tris.push([i, j, n + j]);
      tris.push([i, n + j, n + i]);
    }
    return this.push({
      id: nextId("m"),
      kind: "mesh",
      layer: this.resolveLayer(layer),
      vertices: verts,
      triangles: tris,
    });
  }

  /** Find an entity by id. */
  get(id: string): Entity | undefined {
    return this.drawing.entities.find((e) => e.id === id);
  }

  /** Translate an entity in place. */
  move(id: string, dx: number, dy: number, dz = 0): void {
    const e = this.get(id);
    if (!e) throw new Error(`move: no entity ${id}`);
    const t = (p: Vec3) => ((p.x += dx), (p.y += dy), (p.z += dz));
    switch (e.kind) {
      case "point":
        t(e.at);
        break;
      case "line":
        t(e.a);
        t(e.b);
        break;
      case "polyline":
        e.points.forEach(t);
        break;
      case "circle":
      case "arc":
        t(e.center);
        break;
      case "mesh":
        e.vertices.forEach(t);
        break;
    }
  }

  /** Uniform scale about the origin. */
  scale(id: string, factor: number): void {
    const e = this.get(id);
    if (!e) throw new Error(`scale: no entity ${id}`);
    const s = (p: Vec3) => ((p.x *= factor), (p.y *= factor), (p.z *= factor));
    switch (e.kind) {
      case "point":
        s(e.at);
        break;
      case "line":
        s(e.a);
        s(e.b);
        break;
      case "polyline":
        e.points.forEach(s);
        break;
      case "circle":
        s(e.center);
        e.radius *= factor;
        break;
      case "arc":
        s(e.center);
        e.radius *= factor;
        break;
      case "mesh":
        e.vertices.forEach(s);
        break;
    }
  }

  /** Apply one neutral ModelOp. Returns the created entity id (if any). */
  apply(op: ModelOp): string | undefined {
    switch (op.op) {
      case "layer":
        this.layer(op.name, op.color);
        return undefined;
      case "point":
        return this.point(op.x, op.y, op.z ?? 0, op.layer).id;
      case "line":
        return this.line(
          v3(op.x1, op.y1, op.z1 ?? 0),
          v3(op.x2, op.y2, op.z2 ?? 0),
          op.layer,
        ).id;
      case "polyline":
        return this.polyline(
          op.points.map(([x, y, z]) => v3(x, y, z ?? 0)),
          op.closed ?? false,
          op.layer,
        ).id;
      case "rect":
        return this.rect(op.x, op.y, op.w, op.h, op.layer).id;
      case "circle":
        return this.circle(op.cx, op.cy, op.r, op.layer).id;
      case "arc":
        return this.arc(op.cx, op.cy, op.r, op.start, op.end, op.layer).id;
      case "box":
        return this.box(op.x, op.y, op.z, op.w, op.d, op.h, op.layer).id;
      case "extrude":
        return this.extrude(op.profile, op.height, op.layer).id;
      case "move":
        this.move(op.target, op.dx, op.dy, op.dz ?? 0);
        return op.target;
      case "scale":
        this.scale(op.target, op.factor);
        return op.target;
    }
  }

  /** Apply a whole op program; returns the final Drawing. */
  run(ops: ModelOp[]): Drawing {
    for (const op of ops) this.apply(op);
    return this.drawing;
  }
}

/** Convenience: build a Drawing straight from an op program. */
export function buildDrawing(
  ops: ModelOp[],
  name = "untitled",
  unit: Unit = "mm",
): Drawing {
  return new Kernel(name, unit).run(ops);
}
