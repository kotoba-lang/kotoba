/**
 * KAMI Character 3D Gaussian Splatting SDK (案1)
 *
 * .ply/.splat → kami-render/splatPipeline → compute sort + alpha-blend billboard.
 * Photorealistic character rendering from captured splat data.
 *
 * Usage in app.ts:
 *   import { buildSplatCharacterScene } from "@etzhayyim/kotodama-host-sdk/kami-character-splat";
 *   const scene = buildSplatCharacterScene({ splatKey: "sofia-face.ply", ... });
 */

/** 3DGS character configuration. */
export interface SplatCharacterConfig {
  /** R2 CDN blob key for .ply or .splat file. */
  splatKey: string;
  /** Display name. */
  name?: string;
  /** Position offset [x,y,z] (default: [0, 1.3, 0] — head height). */
  position?: [number, number, number];
  /** Scale (default: 1.0). */
  scale?: number;
  /** Rotation quaternion [x,y,z,w] (default: identity). */
  rotation?: [number, number, number, number];
  /** Camera distance (default: 2.0). */
  cameraDistance?: number;
  /** Background color [r,g,b]. */
  backgroundColor?: [number, number, number];
  /** Max render distance for splat culling (default: 50). */
  maxRenderDistance?: number;
}

/** Build KAMI IslandScene JSON for 3DGS character.
 *  Uses MeshRef::GaussianSplat with compute sort + alpha-blend pipeline. */
export function buildSplatCharacterScene(config: SplatCharacterConfig): Record<string, unknown> {
  const bg = config.backgroundColor ?? [0.04, 0.035, 0.05];
  const pos = config.position ?? [0.0, 1.3, 0.0];
  const scl = config.scale ?? 1.0;
  const rot = config.rotation ?? [0.0, 0.0, 0.0, 1.0];

  return {
    "@context": "https://etzhayyim.com/ns/kami/scene",
    "@type": "IslandScene",
    name: config.name ?? "3DGS Character",
    genre: "social",
    maxPlayers: 1,
    cameraMode: "perspective",
    postfxPreset: "baminikuCharacter",
    ambientColor: [bg[0] * 0.8, bg[1] * 0.8, bg[2] * 0.8],
    sunDirection: [-0.5, -1.0, -0.8],
    sunIntensity: 0.5,
    sunColor: [1.0, 0.96, 0.92],
    atmosphere: {
      fogColor: bg,
      fogDensity: 0.002,
      fogHeight: 0.0,
      fogHeightFalloff: 4.0,
      volumetricIntensity: 0.03,
    },
    pointLights: [
      { id: "key", position: [-2.0, 2.5, 2.0], color: [1.0, 0.94, 0.88], intensity: 2.5, range: 10.0, castShadow: false },
      { id: "fill", position: [1.5, 2.0, 1.5], color: [0.8, 0.88, 1.0], intensity: 1.0, range: 8.0, castShadow: false },
      { id: "rim", position: [0.0, 3.0, -2.0], color: [0.9, 0.8, 1.0], intensity: 2.0, range: 8.0, castShadow: false },
    ],
    entities: [
      // 3DGS character
      {
        id: "character-splat",
        position: pos,
        rotation: rot,
        scale: [scl, scl, scl],
        mesh: {
          type: "gaussianSplat",
          splatKey: config.splatKey,
        },
        components: [
          {
            type: "trigger",
            kind: "splatController",
            data: JSON.stringify({
              maxRenderDistance: config.maxRenderDistance ?? 50,
              sortIntervalMs: 16, // 60fps sort
              cameraDistance: config.cameraDistance ?? 2.0,
            }),
          },
        ],
      },
      // Floor (subtle reflection surface)
      {
        id: "floor",
        position: [0.0, -0.01, 0.0],
        rotation: [0.0, 0.0, 0.0, 1.0],
        scale: [6.0, 0.02, 6.0],
        mesh: { type: "cube", color: [0.1, 0.09, 0.12, 1.0] },
        components: [],
      },
    ],
    characters: [],
  };
}

/** Generate CDN URL for a splat blob. */
export function splatCdnUrl(splatKey: string): string {
  return `https://cdn.etzhayyim.com/${splatKey}`;
}
