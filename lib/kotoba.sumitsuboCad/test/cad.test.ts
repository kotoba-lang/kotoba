/**
 * sumitsubo 墨壺 — cleanroom CAD interop tests. ADR-2606033600.
 */
import { describe, it, expect, beforeEach } from "vitest";
import {
  Kernel,
  buildDrawing,
  resetIds,
  exportDrawing,
  exportDxf,
  exportObj,
  exportGltf,
  exportIfc,
  exportStep,
  exportDwg,
  EXPORT_FIDELITY,
  importDxf,
  VectorScript,
  AcadDatabase,
  drawingToDatoms,
  datomsToTxEdn,
  type ModelOp,
} from "../src/index.js";

beforeEach(() => resetIds());

describe("kernel", () => {
  it("builds primitives and a box mesh", () => {
    const k = new Kernel("t", "mm");
    k.line({ x: 0, y: 0, z: 0 }, { x: 10, y: 0, z: 0 });
    k.circle(5, 5, 2);
    const box = k.box(0, 0, 0, 10, 20, 30);
    expect(k.drawing.entities).toHaveLength(3);
    expect(box.vertices).toHaveLength(8);
    expect(box.triangles).toHaveLength(12);
  });

  it("extrudes a profile into a closed prism", () => {
    const k = new Kernel();
    const m = k.extrude(
      [
        [0, 0],
        [10, 0],
        [10, 10],
        [0, 10],
      ],
      5,
    );
    expect(m.vertices).toHaveLength(8); // 4 bottom + 4 top
    // caps (2*(n-2)=4) + walls (2*n=8) = 12 triangles
    expect(m.triangles).toHaveLength(12);
  });

  it("applies the neutral ModelOp vocabulary (shared with the py generative cell)", () => {
    const ops: ModelOp[] = [
      { op: "layer", name: "walls" },
      { op: "rect", layer: "walls", x: 0, y: 0, w: 100, h: 50 },
      { op: "circle", layer: "walls", cx: 50, cy: 25, r: 10 },
      { op: "box", x: 0, y: 0, z: 0, w: 10, d: 10, h: 10 },
    ];
    const d = buildDrawing(ops, "ops", "mm");
    expect(d.layers.map((l) => l.name)).toContain("walls");
    expect(d.entities).toHaveLength(3);
  });

  it("move and scale transform entities in place", () => {
    const k = new Kernel();
    const c = k.circle(0, 0, 5);
    k.move(c.id, 10, 20);
    k.scale(c.id, 2);
    const e = k.get(c.id);
    expect(e).toMatchObject({ kind: "circle", radius: 10 });
    if (e && e.kind === "circle") {
      expect(e.center.x).toBe(20);
      expect(e.center.y).toBe(40);
    }
  });
});

describe("exporters", () => {
  const k = new Kernel("doc", "mm");
  k.layer("a");
  k.line({ x: 0, y: 0, z: 0 }, { x: 100, y: 0, z: 0 }, "a");
  k.circle(50, 50, 25, "a");
  k.arc(0, 0, 10, 0, 90, "a");
  k.rect(0, 0, 40, 20, "a");
  k.box(0, 0, 0, 10, 10, 10, "a");
  const d = k.drawing;

  it("DXF is a well-formed group-code stream with the entities", () => {
    const dxf = exportDxf(d);
    expect(dxf.startsWith("0\nSECTION")).toBe(true);
    expect(dxf.trimEnd().endsWith("EOF")).toBe(true);
    expect(dxf).toContain("AC1009");
    expect(dxf).toContain("LINE");
    expect(dxf).toContain("CIRCLE");
    expect(dxf).toContain("ARC");
    expect(dxf).toContain("POLYLINE");
    expect(dxf).toContain("3DFACE"); // mesh
  });

  it("OBJ emits vertices and faces for the mesh", () => {
    const obj = exportObj(d);
    expect(obj).toContain("v 0 0 0");
    expect(obj).toMatch(/f \d+ \d+ \d+/);
  });

  it("glTF is valid JSON with one mesh and an embedded buffer", () => {
    const g = JSON.parse(exportGltf(d));
    expect(g.asset.version).toBe("2.0");
    expect(g.meshes).toHaveLength(1);
    expect(g.buffers[0].uri).toMatch(/^data:application\/octet-stream;base64,/);
    expect(g.accessors.length).toBeGreaterThanOrEqual(2);
  });

  it("IFC is an ISO-10303-21 file with IFC4 schema and a proxy per mesh", () => {
    const ifc = exportIfc(d);
    expect(ifc).toContain("ISO-10303-21;");
    expect(ifc).toContain("FILE_SCHEMA(('IFC4'))");
    expect(ifc).toContain("IFCPROJECT");
    expect(ifc).toContain("IFCTRIANGULATEDFACESET");
    expect(ifc).toContain("IFCBUILDINGELEMENTPROXY");
    expect(ifc.trimEnd().endsWith("END-ISO-10303-21;")).toBe(true);
  });

  it("STEP is a minimal AP242 file with cartesian points", () => {
    const stp = exportStep(d);
    expect(stp).toContain("AP242");
    expect(stp).toContain("CARTESIAN_POINT");
  });

  it("DWG export is the proprietary fallback (DXF + advisory)", () => {
    const dwg = exportDwg(d);
    expect(dwg.native).toBe(false);
    expect(dwg.advisory).toBe("DWG_PROPRIETARY");
    expect(dwg.dxf).toContain("SECTION");
    expect(EXPORT_FIDELITY.dwg).toBe("fallback");
  });

  it("exportDrawing dispatches and reports fidelity honestly (G4)", () => {
    expect(exportDrawing(d, "dxf").fidelity).toBe("full");
    expect(exportDrawing(d, "ifc").fidelity).toBe("subset");
    expect(exportDrawing(d, "dwg").fidelity).toBe("fallback");
    expect(exportDrawing(d, "svg").text).toContain("<svg");
  });
});

describe("round-trip DXF import", () => {
  it("re-reads exported LINE/CIRCLE/ARC/POLYLINE", () => {
    const k = new Kernel("rt", "mm");
    k.line({ x: 1, y: 2, z: 0 }, { x: 3, y: 4, z: 0 });
    k.circle(5, 6, 7);
    k.arc(0, 0, 9, 10, 80);
    k.rect(0, 0, 10, 10);
    const dxf = exportDxf(k.drawing);
    const back = importDxf(dxf);
    const kinds = back.entities.map((e) => e.kind).sort();
    expect(kinds).toEqual(["arc", "circle", "line", "polyline"]);
    const circle = back.entities.find((e) => e.kind === "circle");
    expect(circle && circle.kind === "circle" && circle.radius).toBe(7);
  });
});

describe("published-API-shape adapters (cleanroom)", () => {
  it("VectorScript shapes drive the kernel", () => {
    const vs = new VectorScript("vw");
    vs.Layer("design");
    vs.Rect(0, 0, 100, 50);
    vs.Oval(0, 0, 20, 20);
    vs.ArcByCenter(10, 10, 5, 0, 90);
    vs.Poly([0, 0, 10, 0, 10, 10], true);
    vs.Extrude([0, 0, 10, 0, 10, 10, 0, 10], 5);
    const d = vs.document();
    expect(d.layers.some((l) => l.name === "design")).toBe(true);
    expect(d.entities.filter((e) => e.kind === "mesh")).toHaveLength(1); // the extrude
    expect(d.entities.length).toBe(5);
  });

  it("AutoCAD .NET-shaped database + command tokens drive the kernel", () => {
    const db = new AcadDatabase("acad");
    db.modelSpace.setLayer("0");
    db.modelSpace.AddLine([0, 0], [10, 0]);
    db.modelSpace.AddCircle([5, 5], 2);
    db.modelSpace.AddExtrudedSolid(
      [
        [0, 0],
        [10, 0],
        [10, 10],
        [0, 10],
      ],
      4,
    );
    db.command("CIRCLE", 1, 1, 3);
    expect(() => db.command("BOGUS")).toThrow();
    const d = db.document();
    expect(d.entities.filter((e) => e.kind === "mesh")).toHaveLength(1);
    expect(d.entities.filter((e) => e.kind === "circle")).toHaveLength(2);
  });
});

describe("kotoba Datom bridge (G2)", () => {
  it("serializes a drawing to EAVT datoms + tx-edn", () => {
    const k = new Kernel("kg", "mm");
    k.layer("walls");
    k.line({ x: 0, y: 0, z: 0 }, { x: 10, y: 0, z: 0 }, "walls");
    const datoms = drawingToDatoms(k.drawing, "drawing-1");
    expect(datoms.some(([, a]) => a === ":dwg/name")).toBe(true);
    expect(datoms.some(([, a]) => a === ":dwg.layer/name")).toBe(true);
    expect(datoms.some(([, a]) => a === ":dwg.entity/kind")).toBe(true);
    const edn = datomsToTxEdn(datoms);
    expect(edn).toContain("[:db/add");
    expect(edn).toContain(":dwg/name");
  });
});
