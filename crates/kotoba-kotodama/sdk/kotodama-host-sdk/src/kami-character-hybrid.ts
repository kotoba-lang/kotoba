/**
 * KAMI Character Hybrid SDK (案5)
 *
 * Face: 3D Gaussian Splatting (photorealistic)
 * Body/Clothing: SDF smooth union → marching cubes (procedural)
 * Hair: SDF capsule strands (anisotropic Marschner shading)
 *
 * Two-pass render: PBR pass (SDF body) + Splat pass (3DGS face).
 *
 * Usage in app.ts:
 *   import { buildHybridCharacterScene } from "@etzhayyim/kotodama-host-sdk/kami-character-hybrid";
 *   const scene = buildHybridCharacterScene({ faceSplatKey: "sofia-face.ply", ... });
 */

// SdfBodyPartConfig is defined locally below (intentional re-definition for hybrid variant)

/** Hybrid character configuration. */
export interface HybridCharacterConfig {
  /** R2 CDN blob key for face .ply/.splat. */
  faceSplatKey: string;
  /** Face position offset [x,y,z] (default: [0, 1.62, 0.02]). */
  facePosition?: [number, number, number];
  /** Face scale (default: 1.0). */
  faceScale?: number;
  /** SDF body parts (torso, arms, hands, legs — excludes face). */
  bodyParts?: SdfBodyPartConfig[];
  /** SDF hair strands. */
  hairParts?: SdfBodyPartConfig[];
  /** Display name. */
  name?: string;
  /** Background color [r,g,b]. */
  backgroundColor?: [number, number, number];
  /** SDF marching cubes resolution (default: 128). */
  sdfResolution?: number;
}

/** Predefined SDF body part for Sofia's body. */
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

/** Default Sofia body (no face — face is 3DGS). */
export function defaultSofiaBody(): SdfBodyPartConfig[] {
  return [
    // Neck
    { primitive: "capsule", position: [0, 1.48, 0], radius: 0.045, height: 0.1, materialPreset: "skin", materialParams: { tone: 0.92 }, blendRadius: 0.06 },
    // Torso upper (white tank top)
    { primitive: "capsule", position: [0, 1.3, 0], radius: 0.13, height: 0.22, scale: [1, 1, 0.7], materialPreset: "fabric", materialParams: { color: [0.95, 0.95, 0.95, 1] }, blendRadius: 0.05 },
    // Torso lower (skin)
    { primitive: "capsule", position: [0, 1.05, 0], radius: 0.11, height: 0.2, scale: [0.95, 1, 0.65], materialPreset: "skin", materialParams: { tone: 0.92 }, blendRadius: 0.06 },
    // Shoulders
    { primitive: "sphere", position: [-0.16, 1.38, 0], radius: 0.055, scale: [1, 0.8, 0.8], materialPreset: "skin", materialParams: { tone: 0.92 }, blendRadius: 0.05 },
    { primitive: "sphere", position: [0.16, 1.38, 0], radius: 0.055, scale: [1, 0.8, 0.8], materialPreset: "skin", materialParams: { tone: 0.92 }, blendRadius: 0.05 },
    // Upper arms
    { primitive: "capsule", position: [-0.22, 1.28, 0], rotation: [0, 0, 0.25, 0.97], radius: 0.038, height: 0.2, materialPreset: "skin", materialParams: { tone: 0.92 }, blendRadius: 0.04 },
    { primitive: "capsule", position: [0.22, 1.28, 0], rotation: [0, 0, -0.25, 0.97], radius: 0.038, height: 0.2, materialPreset: "skin", materialParams: { tone: 0.92 }, blendRadius: 0.04 },
    // Forearms
    { primitive: "capsule", position: [-0.34, 1.12, 0.04], rotation: [0.08, 0, 0.45, 0.89], radius: 0.03, height: 0.2, materialPreset: "skin", materialParams: { tone: 0.92 }, blendRadius: 0.03 },
    { primitive: "capsule", position: [0.34, 1.12, 0.04], rotation: [-0.08, 0, -0.45, 0.89], radius: 0.03, height: 0.2, materialPreset: "skin", materialParams: { tone: 0.92 }, blendRadius: 0.03 },
  ];
}

/** Default Sofia hair strands (blonde, long). */
export function defaultSofiaHair(): SdfBodyPartConfig[] {
  return [
    // Hair volume (back)
    { primitive: "capsule", position: [0, 1.65, -0.06], radius: 0.12, height: 0.4, scale: [0.85, 1, 0.55], materialPreset: "hair", materialParams: { hue: 0.1, lightness: 0.85 }, blendRadius: 0.06 },
    // Side strands (left)
    { primitive: "capsule", position: [-0.08, 1.55, 0.01], rotation: [0, 0, 0.12, 0.99], radius: 0.04, height: 0.35, materialPreset: "hair", materialParams: { hue: 0.1, lightness: 0.85 }, blendRadius: 0.04 },
    // Side strands (right)
    { primitive: "capsule", position: [0.08, 1.55, 0.01], rotation: [0, 0, -0.12, 0.99], radius: 0.04, height: 0.35, materialPreset: "hair", materialParams: { hue: 0.1, lightness: 0.85 }, blendRadius: 0.04 },
    // Bangs
    { primitive: "sphere", position: [0, 1.72, 0.06], radius: 0.11, scale: [1.1, 0.35, 0.45], materialPreset: "hair", materialParams: { hue: 0.1, lightness: 0.88 }, blendRadius: 0.04 },
    // Hair crown
    { primitive: "sphere", position: [0, 1.75, -0.02], radius: 0.1, scale: [1, 0.3, 0.8], materialPreset: "hair", materialParams: { hue: 0.1, lightness: 0.86 }, blendRadius: 0.05 },
  ];
}

/** Build KAMI IslandScene for hybrid character (3DGS face + SDF body + SDF hair).
 *  kami-web renders in two passes: PBR (SDF entities) + Splat (face). */
export function buildHybridCharacterScene(config: HybridCharacterConfig): Record<string, unknown> {
  const bg = config.backgroundColor ?? [0.05, 0.04, 0.07];
  const bodyParts = config.bodyParts ?? defaultSofiaBody();
  const hairParts = config.hairParts ?? defaultSofiaHair();
  const facePos = config.facePosition ?? [0.0, 1.62, 0.02];
  const faceScl = config.faceScale ?? 0.2;
  const res = config.sdfResolution ?? 128;

  // Convert SdfBodyPartConfig[] to scene.rs SdfBodyPartDef format
  const toSceneParts = (parts: SdfBodyPartConfig[]) =>
    parts.map(p => ({
      primitive: p.primitive,
      position: p.position,
      rotation: p.rotation ?? [0, 0, 0, 1],
      scale: p.scale ?? [1, 1, 1],
      radius: p.radius ?? 0.05,
      height: p.height ?? 0.1,
      materialPreset: p.materialPreset,
      materialParams: p.materialParams ?? {},
      blendRadius: p.blendRadius ?? 0.05,
    }));

  return {
    "@context": "https://etzhayyim.com/ns/kami/scene",
    "@type": "IslandScene",
    name: config.name ?? "Hybrid Character",
    genre: "social",
    maxPlayers: 1,
    cameraMode: "perspective",
    postfxPreset: "baminikuCharacter",
    ambientColor: [bg[0] * 0.7, bg[1] * 0.7, bg[2] * 0.7],
    sunDirection: [-0.4, -1.0, -0.7],
    sunIntensity: 0.6,
    sunColor: [1.0, 0.95, 0.9],
    atmosphere: {
      fogColor: bg,
      fogDensity: 0.004,
      fogHeight: 0.0,
      fogHeightFalloff: 3.0,
      volumetricIntensity: 0.06,
    },
    shadow: { resolution: 2048, cascades: 2, softness: 2.0, bias: 0.004 },
    pointLights: [
      { id: "key", position: [-2.0, 2.5, 2.0], color: [1.0, 0.94, 0.88], intensity: 3.2, range: 12.0, castShadow: true },
      { id: "fill", position: [1.5, 2.0, 1.5], color: [0.75, 0.85, 1.0], intensity: 1.3, range: 10.0, castShadow: false },
      { id: "rim", position: [0.0, 3.0, -1.5], color: [0.9, 0.8, 1.0], intensity: 2.5, range: 8.0, castShadow: false },
      { id: "hair-light", position: [-0.3, 3.5, -0.5], color: [1.0, 0.95, 0.85], intensity: 1.8, range: 5.0, castShadow: false },
      { id: "bounce", position: [0.0, 0.1, 1.5], color: [0.9, 0.85, 0.75], intensity: 0.5, range: 4.0, castShadow: false },
    ],
    entities: [
      // Face: 3D Gaussian Splatting (photorealistic)
      {
        id: "face-splat",
        position: facePos,
        rotation: [0, 0, 0, 1],
        scale: [faceScl, faceScl, faceScl],
        mesh: {
          type: "gaussianSplat",
          splatKey: config.faceSplatKey,
        },
        components: [
          {
            type: "trigger",
            kind: "splatFace",
            data: JSON.stringify({ sortIntervalMs: 16 }),
          },
        ],
      },
      // Body: SDF smooth union → marching cubes
      {
        id: "body-sdf",
        position: [0, 0, 0],
        rotation: [0, 0, 0, 1],
        scale: [1, 1, 1],
        mesh: {
          type: "sdfCharacter",
          resolution: res,
          bodyParts: toSceneParts(bodyParts),
        },
        components: [],
      },
      // Hair: SDF capsule strands (separate mesh for anisotropic material)
      {
        id: "hair-sdf",
        position: [0, 0, 0],
        rotation: [0, 0, 0, 1],
        scale: [1, 1, 1],
        mesh: {
          type: "sdfCharacter",
          resolution: Math.max(64, res - 32),
          bodyParts: toSceneParts(hairParts),
        },
        components: [],
      },
      // Floor
      {
        id: "floor",
        position: [0, -0.01, 0],
        rotation: [0, 0, 0, 1],
        scale: [6, 0.02, 6],
        mesh: { type: "cube", color: [bg[0] * 2, bg[1] * 2, bg[2] * 2, 1] },
        components: [],
      },
    ],
    characters: [],
  };
}
