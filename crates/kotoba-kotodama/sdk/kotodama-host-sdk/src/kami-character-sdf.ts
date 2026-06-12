/**
 * KAMI Character SDF types — shared by hybrid SDK and standalone SDF.
 */

/** SDF body part configuration (matches scene.rs SdfBodyPartDef). */
export interface SdfBodyPartConfig {
  primitive: "sphere" | "capsule" | "cylinder" | "box";
  position: [number, number, number];
  rotation?: [number, number, number, number];
  scale?: [number, number, number];
  radius?: number;
  height?: number;
  materialPreset: "skin" | "hair" | "eye" | "lip" | "fabric";
  materialParams?: Record<string, unknown>;
  blendRadius?: number;
}
