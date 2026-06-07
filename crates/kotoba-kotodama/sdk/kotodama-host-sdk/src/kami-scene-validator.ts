/**
 * KAMI Scene JSON validator — catches schema mismatches between TS scene builders
 * and Rust kami-web WASM at build time, not runtime.
 *
 * Source of truth: kami-game/src/scene.rs (MeshRef, ComponentDef, IslandScene)
 */

/** MeshRef types that kami-web WASM can deserialize (scene.rs MeshRef enum). */
const VALID_MESH_TYPES = new Set([
  "cube", "sphere", "asset", "plane", "voxel", "terrain",
  "gaussianSplat", "cylinder", "scad", "hexPrism", "hexGrid",
  "pipe", "building", "characterModel", "sdfCharacter",
]);

/** MeshRef types that kami-web WASM can actually render (not just parse).
 *  Types in VALID_MESH_TYPES but not here fall back to a cube. */
const RENDERABLE_MESH_TYPES = new Set([
  "cube", "sphere", "asset", "plane", "voxel", "terrain",
  "gaussianSplat", "cylinder", "scad", "hexPrism", "hexGrid",
  "pipe", "building",
]);

/** Valid ComponentDef `type` values (must match kami-game/src/scene.rs ComponentDef enum). */
const VALID_COMPONENT_TYPES = new Set([
  "playerSpawn", "npc", "portal", "item", "physics", "trigger",
]);

export interface SceneValidationError {
  entityId: string;
  field: string;
  value: string;
  message: string;
  /** "error" = WASM will reject (serde fail). "warn" = parseable but renders as fallback cube. */
  severity: "error" | "warn";
}

/** Validate a KAMI IslandScene JSON object against the Rust schema.
 *  Returns errors for any mesh types or component types that kami-web WASM won't accept. */
export function validateKamiScene(scene: Record<string, unknown>): SceneValidationError[] {
  const errors: SceneValidationError[] = [];
  const entities = scene.entities as Array<Record<string, unknown>> | undefined;
  if (!Array.isArray(entities)) return errors;

  for (const entity of entities) {
    const id = String(entity.id ?? "unknown");
    const mesh = entity.mesh as Record<string, unknown> | undefined;
    if (mesh?.type) {
      const mt = String(mesh.type);
      if (!VALID_MESH_TYPES.has(mt)) {
        errors.push({
          entityId: id, field: "mesh.type", value: mt, severity: "error",
          message: `unknown mesh type "${mt}" — WASM will reject. Valid: ${[...VALID_MESH_TYPES].join(", ")}`,
        });
      } else if (!RENDERABLE_MESH_TYPES.has(mt)) {
        errors.push({
          entityId: id, field: "mesh.type", value: mt, severity: "warn",
          message: `mesh type "${mt}" is parseable but renders as fallback cube (not yet implemented in kami-web)`,
        });
      }
    }

    const components = entity.components as Array<Record<string, unknown>> | undefined;
    if (Array.isArray(components)) {
      for (const comp of components) {
        if (comp.type && !VALID_COMPONENT_TYPES.has(String(comp.type))) {
          errors.push({
            entityId: id, field: "component.type", value: String(comp.type), severity: "error",
            message: `unknown component type "${comp.type}" — WASM will reject. Valid: ${[...VALID_COMPONENT_TYPES].join(", ")}. Use {type:"trigger", kind:"${comp.type}", data:JSON.stringify({...})} instead.`,
          });
        }
      }
    }
  }

  return errors;
}

/** Validate and throw on errors, console.warn on warnings. Use in app.ts scene builders. */
export function assertValidKamiScene(scene: Record<string, unknown>): void {
  const results = validateKamiScene(scene);
  const errors = results.filter(e => e.severity === "error");
  const warnings = results.filter(e => e.severity === "warn");
  for (const w of warnings) {
    console.warn(`[kami-scene] entity "${w.entityId}": ${w.message}`);
  }
  if (errors.length > 0) {
    const msg = errors.map(e => `  entity "${e.entityId}": ${e.message}`).join("\n");
    throw new Error(`KAMI scene validation failed:\n${msg}`);
  }
}
