/**
 * KAMI Character VRM/GLB SDK (案2)
 *
 * VRM/GLB model → kami-gltf loader → PBR mesh + kami-skeleton blendshapes.
 * VRoid Studio / Ready Player Me 互換。
 *
 * Usage in app.ts:
 *   import { buildVRMCharacterScene } from "@etzhayyim/kotodama-host-sdk/kami-character-vrm";
 *   const scene = buildVRMCharacterScene({ blobKey: "sofia-vrm.glb", ... });
 */

/** VRM character configuration. */
export interface VRMCharacterConfig {
  /** R2 CDN blob key for VRM/GLB file. */
  blobKey: string;
  /** Display name (for loading UI). */
  name?: string;
  /** Material overrides per sub-mesh. */
  materialOverrides?: VRMMaterialOverride[];
  /** Initial blendshape weights (e.g. { blinkLeft: 0, smile: 0.3 }). */
  blendshapes?: Record<string, number>;
  /** Camera distance (default: 2.5). */
  cameraDistance?: number;
  /** Camera height offset from model center (default: 0.1). */
  cameraHeightOffset?: number;
  /** Background color [r,g,b] (default: dark studio). */
  backgroundColor?: [number, number, number];
}

/** Material override for a VRM sub-mesh. */
export interface VRMMaterialOverride {
  meshName: string;
  preset: "skin" | "hair" | "eye" | "lip" | "fabric";
  params?: Record<string, unknown>;
}

/** Build KAMI IslandScene JSON for VRM/GLB character display.
 *  Uses MeshRef::Asset (kami-gltf loader) with PBR materials. */
export function buildVRMCharacterScene(config: VRMCharacterConfig): Record<string, unknown> {
  const bg = config.backgroundColor ?? [0.06, 0.05, 0.08];
  const camDist = config.cameraDistance ?? 2.5;
  const camH = config.cameraHeightOffset ?? 0.1;

  return {
    "@context": "https://etzhayyim.com/ns/kami/scene",
    "@type": "IslandScene",
    name: config.name ?? "VRM Character",
    genre: "social",
    maxPlayers: 1,
    cameraMode: "perspective",
    postfxPreset: "baminikuCharacter",
    ambientColor: [bg[0] * 0.6, bg[1] * 0.6, bg[2] * 0.6],
    sunDirection: [-0.5, -1.2, -0.8],
    sunIntensity: 0.8,
    sunColor: [1.0, 0.95, 0.9],
    atmosphere: {
      fogColor: bg,
      fogDensity: 0.003,
      fogHeight: 0.0,
      fogHeightFalloff: 3.0,
      volumetricIntensity: 0.05,
    },
    shadow: { resolution: 2048, cascades: 2, softness: 2.0, bias: 0.004 },
    pointLights: [
      { id: "key", position: [-2.0, 2.5, 2.0], color: [1.0, 0.94, 0.88], intensity: 3.0, range: 12.0, castShadow: true },
      { id: "fill", position: [1.5, 2.0, 1.5], color: [0.75, 0.85, 1.0], intensity: 1.2, range: 10.0, castShadow: false },
      { id: "rim", position: [0.0, 3.0, -1.5], color: [0.9, 0.8, 1.0], intensity: 2.5, range: 8.0, castShadow: false },
      { id: "hair", position: [-0.3, 3.5, -0.5], color: [1.0, 0.95, 0.85], intensity: 1.8, range: 5.0, castShadow: false },
    ],
    entities: [
      // VRM model
      {
        id: "character",
        position: [0.0, 0.0, 0.0],
        rotation: [0.0, 0.0, 0.0, 1.0],
        scale: [1.0, 1.0, 1.0],
        mesh: {
          type: "asset",
          assetId: config.blobKey,
          blobKey: config.blobKey,
        },
        components: [
          { type: "playerSpawn" },
          {
            type: "trigger",
            kind: "vrmController",
            data: JSON.stringify({
              blendshapes: config.blendshapes ?? {},
              idleAnimation: "breathing",
              blinkIntervalMs: 3500,
              cameraDistance: camDist,
              cameraHeight: camH,
            }),
          },
        ],
      },
      // Floor
      {
        id: "floor",
        position: [0.0, -0.01, 0.0],
        rotation: [0.0, 0.0, 0.0, 1.0],
        scale: [6.0, 0.02, 6.0],
        mesh: { type: "cube", color: [bg[0] * 1.5, bg[1] * 1.5, bg[2] * 1.5, 1.0] },
        components: [],
      },
    ],
    characters: [],
  };
}

/** Generate CDN URL for a VRM blob. */
export function vrmCdnUrl(blobKey: string): string {
  return `https://cdn.etzhayyim.com/${blobKey}`;
}
