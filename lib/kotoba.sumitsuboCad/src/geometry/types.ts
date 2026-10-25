/**
 * sumitsubo 墨壺 — canonical drawing model (cleanroom CAD interop).
 * ADR-2606033600.
 *
 * Engine-agnostic geometry + document types. Model units are MILLIMETRES (f64).
 * This model is the single source of truth shared by: the modeling kernel, every
 * exporter/importer, the Vectorworks/AutoCAD published-API-shape adapters, and the
 * kotoba Datom bridge. The kotoba-LangGraph cells (py/) emit the SAME op vocabulary
 * (see ModelOp) so generation and the TS kernel speak one language.
 */

/** A 3D point in model space (millimetres). z defaults to 0 for 2D drafting. */
export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export function v3(x: number, y: number, z = 0): Vec3 {
  return { x, y, z };
}

/** Supported model units. Internal storage is always mm; units annotate intent + export. */
export type Unit = "mm" | "cm" | "m" | "in" | "ft";

/** Conversion factor: how many millimetres in one of `unit`. */
export const MM_PER_UNIT: Record<Unit, number> = {
  mm: 1,
  cm: 10,
  m: 1000,
  in: 25.4,
  ft: 304.8,
};

/** An ARGB-free simple RGB colour (0..255), or a named DXF ACI index fallback. */
export interface Color {
  r: number;
  g: number;
  b: number;
}

export type EntityKind =
  | "point"
  | "line"
  | "polyline"
  | "circle"
  | "arc"
  | "mesh";

/** Discriminated entity union. 2D primitives keep z; meshes carry triangles. */
export interface BaseEntity {
  id: string;
  kind: EntityKind;
  layer: string;
}

export interface PointEntity extends BaseEntity {
  kind: "point";
  at: Vec3;
}

export interface LineEntity extends BaseEntity {
  kind: "line";
  a: Vec3;
  b: Vec3;
}

export interface PolylineEntity extends BaseEntity {
  kind: "polyline";
  points: Vec3[];
  closed: boolean;
}

export interface CircleEntity extends BaseEntity {
  kind: "circle";
  center: Vec3;
  radius: number;
}

export interface ArcEntity extends BaseEntity {
  kind: "arc";
  center: Vec3;
  radius: number;
  /** Degrees, CCW, DXF convention. */
  startAngle: number;
  endAngle: number;
}

export interface MeshEntity extends BaseEntity {
  kind: "mesh";
  /** Flat vertex list. */
  vertices: Vec3[];
  /** Triangle index triples into `vertices`. */
  triangles: [number, number, number][];
}

export type Entity =
  | PointEntity
  | LineEntity
  | PolylineEntity
  | CircleEntity
  | ArcEntity
  | MeshEntity;

export interface Layer {
  name: string;
  color: Color;
  visible: boolean;
}

/** The canonical drawing. Held in mm; `unit` records authoring intent. */
export interface Drawing {
  name: string;
  unit: Unit;
  layers: Layer[];
  entities: Entity[];
  /** sourcing honesty (G7): authoritative vs representative geometry. */
  sourcing: "authoritative" | "representative";
}

/**
 * Neutral modeling-op vocabulary. The TS kernel applies these; the python
 * generative cell EMITS these. Keep the two in lockstep (ADR §2).
 */
export type ModelOp =
  | { op: "layer"; name: string; color?: Color }
  | { op: "point"; layer?: string; x: number; y: number; z?: number }
  | {
      op: "line";
      layer?: string;
      x1: number;
      y1: number;
      z1?: number;
      x2: number;
      y2: number;
      z2?: number;
    }
  | {
      op: "polyline";
      layer?: string;
      points: [number, number, number?][];
      closed?: boolean;
    }
  | { op: "rect"; layer?: string; x: number; y: number; w: number; h: number }
  | { op: "circle"; layer?: string; cx: number; cy: number; r: number }
  | {
      op: "arc";
      layer?: string;
      cx: number;
      cy: number;
      r: number;
      start: number;
      end: number;
    }
  | {
      op: "box";
      layer?: string;
      x: number;
      y: number;
      z: number;
      w: number;
      d: number;
      h: number;
    }
  | {
      op: "extrude";
      layer?: string;
      profile: [number, number][];
      height: number;
    }
  | { op: "move"; target: string; dx: number; dy: number; dz?: number }
  | { op: "scale"; target: string; factor: number };

export const DEFAULT_LAYER = "0";
export const WHITE: Color = { r: 255, g: 255, b: 255 };
