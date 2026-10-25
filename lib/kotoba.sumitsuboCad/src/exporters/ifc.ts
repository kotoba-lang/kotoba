/**
 * sumitsubo 墨壺 — IFC4 STEP-Physical-File exporter (SUBSET).
 * ADR-2606033600. Open spec: ISO 16739 (IFC4) + ISO 10303-21 (STEP physical file).
 *
 * HONEST SUBSET (G4/N6): emits IfcProject + units + a geometric context, and one
 * IfcBuildingElementProxy per mesh entity carrying an IfcTriangulatedFaceSet
 * tessellation. Curves/2D primitives are NOT exported here (use DXF/SVG). This is a
 * valid-but-minimal IFC; full IFC schema conformance/certification is out of R0.
 */

import { Drawing, MeshEntity } from "../geometry/types.js";

function guid(seed: number): string {
  // Deterministic 22-char IFC GlobalId-shaped token (not a true compressed UUID).
  const base = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$";
  let n = seed * 2654435761 + 1;
  let s = "";
  for (let i = 0; i < 22; i++) {
    n = (n * 1103515245 + 12345) & 0x7fffffff;
    s += base[n % 64];
  }
  return s;
}

export function exportIfc(d: Drawing): string {
  const meshes = d.entities.filter((e): e is MeshEntity => e.kind === "mesh");
  const lines: string[] = [];
  let id = 0;
  const ref = () => `#${++id}`;
  const emit = (r: string, body: string) => lines.push(`${r}=${body};`);

  // --- shared infrastructure ---
  const pOrigin = ref();
  emit(pOrigin, "IFCCARTESIANPOINT((0.,0.,0.))");
  const dZ = ref();
  emit(dZ, "IFCDIRECTION((0.,0.,1.))");
  const dX = ref();
  emit(dX, "IFCDIRECTION((1.,0.,0.))");
  const axis = ref();
  emit(axis, `IFCAXIS2PLACEMENT3D(${pOrigin},${dZ},${dX})`);
  const placement = ref();
  emit(placement, `IFCLOCALPLACEMENT($,${axis})`);
  const ctx = ref();
  emit(ctx, `IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,${axis},$)`);
  const lenUnit = ref();
  emit(lenUnit, "IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.)");
  const units = ref();
  emit(units, `IFCUNITASSIGNMENT((${lenUnit}))`);
  const project = ref();
  emit(project, `IFCPROJECT('${guid(0)}',$,'${d.name}',$,$,$,$,(${ctx}),${units})`);

  // --- per-mesh proxies ---
  meshes.forEach((m, mi) => {
    const coords = m.vertices.map((v) => `(${v.x},${v.y},${v.z})`).join(",");
    const pointList = ref();
    emit(pointList, `IFCCARTESIANPOINTLIST3D((${coords}))`);
    const idx = m.triangles.map((t) => `(${t[0] + 1},${t[1] + 1},${t[2] + 1})`).join(",");
    const faceSet = ref();
    emit(faceSet, `IFCTRIANGULATEDFACESET(${pointList},$,.F.,(${idx}),$)`);
    const shapeRep = ref();
    emit(shapeRep, `IFCSHAPEREPRESENTATION(${ctx},'Body','Tessellation',(${faceSet}))`);
    const prodDef = ref();
    emit(prodDef, `IFCPRODUCTDEFINITIONSHAPE($,$,(${shapeRep}))`);
    const proxy = ref();
    emit(
      proxy,
      `IFCBUILDINGELEMENTPROXY('${guid(mi + 1)}',$,'${m.id}',$,$,${placement},${prodDef},$,$)`,
    );
  });

  const data = lines.join("\n");
  const header =
    "ISO-10303-21;\n" +
    "HEADER;\n" +
    "FILE_DESCRIPTION(('ViewDefinition [ReferenceView]'),'2;1');\n" +
    `FILE_NAME('${d.name}.ifc','',(''),(''),'sumitsubo ADR-2606033600','','');\n` +
    "FILE_SCHEMA(('IFC4'));\n" +
    "ENDSEC;\n";
  return `${header}DATA;\n${data}\nENDSEC;\nEND-ISO-10303-21;\n`;
}
