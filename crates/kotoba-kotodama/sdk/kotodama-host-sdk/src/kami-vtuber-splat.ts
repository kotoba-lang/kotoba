/**
 * KAMI VTuber SDK — Design A: 3D Gaussian Splatting Avatar
 *
 * Full-body 3DGS avatar with expression control via splat affine transform.
 * Photo → Murakumo VL → multi-view → 3DGS reconstruction → R2 .splat
 *
 * Photorealistic quality (highest fidelity), limited expression range.
 * Expression = per-region splat affine transforms (no blend shapes).
 *
 * Pipeline:
 *   1. Photo upload → R2
 *   2. Murakumo qwen3.5-4b (VL) → face landmark extraction → parametric description
 *   3. Murakumo wai-real-mix-v11 (SDXL) → 8-view turnaround renders
 *   4. Mac Mini fleet → 3DGS reconstruction (nerfstudio/gsplat)
 *   5. Region segmentation → face/hair/body splat groups
 *   6. .splat + region map → R2
 *   7. KAMI gaussianSplat pipeline renders with per-region transforms
 *
 * Expression control via SplatRegionTransform:
 *   - Jaw open: translate jaw region splats downward
 *   - Smile: scale mouth region horizontally + translate corners up
 *   - Blink: scale eye region vertically to 0
 *   - Head tilt: rotate head region splats as rigid body
 *
 * Usage in app.ts:
 *   import { buildSplatVTuberScene } from "@etzhayyim/kotodama-host-sdk/kami-vtuber-splat";
 *   const scene = buildSplatVTuberScene({
 *     splatKey: "avatar-fullbody.splat",
 *     regionMapKey: "avatar-regions.json",
 *     tracking: { source: "mediapipe", blendToSplat: true },
 *   });
 *
 * @module
 */

/** Splat region for expression control. */
export interface SplatRegion {
  /** Region identifier (e.g. "jaw", "leftEye", "rightEye", "mouth", "brow", "head", "hair", "body"). */
  id: string;
  /** Splat index range [start, end) in the .splat file. */
  indexRange: [number, number];
  /** Pivot point for rotation/scale transforms [x, y, z]. */
  pivot: [number, number, number];
}

/** Affine transform applied to a splat region for expression. */
export interface SplatRegionTransform {
  regionId: string;
  /** Translation offset [dx, dy, dz]. */
  translate?: [number, number, number];
  /** Scale factors [sx, sy, sz] (1.0 = no change). */
  scale?: [number, number, number];
  /** Rotation quaternion [x, y, z, w]. */
  rotation?: [number, number, number, number];
}

/** Expression preset mapping ARKit blend shape names to splat transforms. */
export interface SplatExpressionPreset {
  name: string;
  transforms: SplatRegionTransform[];
}

/** ARKit blend shape → splat region transform mapping. */
export const ARKIT_TO_SPLAT_DEFAULTS: Record<string, (weight: number) => SplatRegionTransform[]> = {
  jawOpen: (w) => [
    { regionId: "jaw", translate: [0, -0.02 * w, 0] },
    { regionId: "mouth", scale: [1, 1 + 0.3 * w, 1] },
  ],
  mouthSmileLeft: (w) => [
    { regionId: "mouth", translate: [-0.005 * w, 0.003 * w, 0] },
  ],
  mouthSmileRight: (w) => [
    { regionId: "mouth", translate: [0.005 * w, 0.003 * w, 0] },
  ],
  eyeBlinkLeft: (w) => [
    { regionId: "leftEye", scale: [1, 1 - 0.9 * w, 1] },
  ],
  eyeBlinkRight: (w) => [
    { regionId: "rightEye", scale: [1, 1 - 0.9 * w, 1] },
  ],
  browInnerUp: (w) => [
    { regionId: "brow", translate: [0, 0.005 * w, 0] },
  ],
  browOuterUpLeft: (w) => [
    { regionId: "brow", translate: [-0.003 * w, 0.004 * w, 0] },
  ],
  browOuterUpRight: (w) => [
    { regionId: "brow", translate: [0.003 * w, 0.004 * w, 0] },
  ],
  cheekPuff: (w) => [
    { regionId: "jaw", scale: [1 + 0.08 * w, 1, 1 + 0.05 * w] },
  ],
};

/** Head pose (from MediaPipe) applied as rigid transform to all head-region splats. */
export interface HeadPose {
  /** Euler angles in radians [pitch, yaw, roll]. */
  rotation: [number, number, number];
  /** Translation offset [x, y, z]. */
  translation: [number, number, number];
}

/** 3DGS VTuber tracking configuration. */
export interface SplatTrackingConfig {
  /** Input source. */
  source: "mediapipe" | "mocopi" | "manual";
  /** Map ARKit blend shapes to splat region transforms (default: true). */
  blendToSplat?: boolean;
  /** Custom ARKit→splat overrides. */
  customMapping?: Record<string, (weight: number) => SplatRegionTransform[]>;
  /** Auto-blink interval in ms (default: 3500). */
  autoBlinkIntervalMs?: number;
  /** Idle breathing amplitude (default: 0.003). */
  idleBreathingAmplitude?: number;
}

/** Full 3DGS VTuber avatar configuration. */
export interface SplatVTuberConfig {
  /** R2 CDN blob key for full-body .splat file. */
  splatKey: string;
  /** R2 CDN blob key for region map JSON (SplatRegion[]). */
  regionMapKey: string;
  /** Display name. */
  name?: string;
  /** Tracking input configuration. */
  tracking?: SplatTrackingConfig;
  /** Expression presets (happy, sad, surprised, etc.). */
  expressionPresets?: SplatExpressionPreset[];
  /** Camera distance (default: 2.5). */
  cameraDistance?: number;
  /** Camera height offset (default: 0.1). */
  cameraHeightOffset?: number;
  /** Background color [r,g,b]. */
  backgroundColor?: [number, number, number];
}

/**
 * Build KAMI IslandScene JSON for 3DGS VTuber avatar.
 *
 * Two-pass rendering: gaussianSplat pipeline with per-region affine transforms.
 * MediaPipe face tracking → ARKit blend shapes → splat region transforms.
 */
export function buildSplatVTuberScene(config: SplatVTuberConfig): Record<string, unknown> {
  const bg = config.backgroundColor ?? [0.04, 0.035, 0.06];
  const camDist = config.cameraDistance ?? 2.5;
  const camH = config.cameraHeightOffset ?? 0.1;
  const tracking = config.tracking ?? { source: "mediapipe", blendToSplat: true };

  return {
    "@context": "https://etzhayyim.com/ns/kami/scene",
    "@type": "IslandScene",
    name: config.name ?? "3DGS VTuber",
    genre: "social",
    maxPlayers: 1,
    cameraMode: "perspective",
    postfxPreset: "baminikuCharacter",
    ambientColor: [bg[0] * 0.7, bg[1] * 0.7, bg[2] * 0.7],
    sunDirection: [-0.4, -1.0, -0.7],
    sunIntensity: 0.5,
    sunColor: [1.0, 0.96, 0.92],
    atmosphere: {
      fogColor: bg,
      fogDensity: 0.002,
      fogHeight: 0.0,
      fogHeightFalloff: 4.0,
      volumetricIntensity: 0.04,
    },
    shadow: { resolution: 2048, cascades: 2, softness: 2.5, bias: 0.004 },
    pointLights: [
      { id: "key", position: [-2.0, 2.5, 2.5], color: [1.0, 0.94, 0.88], intensity: 3.0, range: 12.0, castShadow: true },
      { id: "fill", position: [1.5, 2.0, 1.5], color: [0.75, 0.85, 1.0], intensity: 1.2, range: 10.0, castShadow: false },
      { id: "rim", position: [0.0, 3.0, -1.5], color: [0.9, 0.8, 1.0], intensity: 2.5, range: 8.0, castShadow: false },
      { id: "hair", position: [-0.3, 3.5, -0.5], color: [1.0, 0.95, 0.85], intensity: 1.8, range: 5.0, castShadow: false },
    ],
    entities: [
      {
        id: "vtuber-splat",
        position: [0.0, 0.0, 0.0],
        rotation: [0.0, 0.0, 0.0, 1.0],
        scale: [1.0, 1.0, 1.0],
        mesh: {
          type: "gaussianSplat",
          splatKey: config.splatKey,
        },
        components: [
          {
            type: "trigger",
            kind: "splatVtuber",
            data: JSON.stringify({
              regionMapKey: config.regionMapKey,
              trackingSource: tracking.source,
              blendToSplat: tracking.blendToSplat ?? true,
              autoBlinkIntervalMs: tracking.autoBlinkIntervalMs ?? 3500,
              idleBreathingAmplitude: tracking.idleBreathingAmplitude ?? 0.003,
              cameraDistance: camDist,
              cameraHeight: camH,
              expressionPresets: config.expressionPresets ?? [],
              customMapping: tracking.customMapping ? Object.keys(tracking.customMapping) : [],
            }),
          },
        ],
      },
      {
        id: "floor",
        position: [0.0, -0.01, 0.0],
        rotation: [0.0, 0.0, 0.0, 1.0],
        scale: [6.0, 0.02, 6.0],
        mesh: { type: "cube", color: [bg[0] * 2, bg[1] * 2, bg[2] * 2, 1.0] },
        components: [],
      },
    ],
    characters: [],
  };
}
