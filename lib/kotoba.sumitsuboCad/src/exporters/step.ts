/**
 * sumitsubo 墨壺 — STEP AP242 exporter (MINIMAL).
 * ADR-2606033600. Open spec: ISO 10303-21 / -242.
 *
 * HONEST MINIMAL (G4/N6): a valid ISO-10303-21 wrapper with an AP242 FILE_SCHEMA
 * and the mesh geometry expressed as CARTESIAN_POINT instances grouped in a
 * GEOMETRIC_SET. This is NOT a full B-rep ADVANCED_FACE solid (that requires an
 * ACIS/Parasolid-class kernel — ADR N2); it is a coordinate-bearing STEP file
 * suitable for point/tessellation interchange.
 */

import { Drawing, MeshEntity } from "../geometry/types.js";

export function exportStep(d: Drawing): string {
  const meshes = d.entities.filter((e): e is MeshEntity => e.kind === "mesh");
  const lines: string[] = [];
  let id = 0;
  const ref = () => `#${++id}`;
  const emit = (r: string, body: string) => lines.push(`${r}=${body};`);

  const appCtx = ref();
  emit(appCtx, "APPLICATION_CONTEXT('core data for automotive mechanical design processes')");
  const pdContext = ref();
  emit(pdContext, `PRODUCT_DEFINITION_CONTEXT('part definition',${appCtx},'design')`);

  meshes.forEach((m) => {
    const ptRefs: string[] = [];
    for (const v of m.vertices) {
      const p = ref();
      emit(p, `CARTESIAN_POINT('',(${v.x},${v.y},${v.z}))`);
      ptRefs.push(p);
    }
    const cloud = ref();
    emit(cloud, `GEOMETRIC_SET('${m.id}',(${ptRefs.join(",")}))`);
  });

  const data = lines.join("\n");
  const header =
    "ISO-10303-21;\n" +
    "HEADER;\n" +
    "FILE_DESCRIPTION(('sumitsubo minimal AP242 export — tessellation point set'),'2;1');\n" +
    `FILE_NAME('${d.name}.stp','',(''),(''),'sumitsubo ADR-2606033600','','');\n` +
    "FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\n" +
    "ENDSEC;\n";
  return `${header}DATA;\n${data}\nENDSEC;\nEND-ISO-10303-21;\n`;
}
