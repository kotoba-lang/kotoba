/**
 * KAMI VTuber SDK — Design C: Hybrid (3DGS Face + VRM Body)
 *
 * Best of both worlds:
 *   - Face: 3D Gaussian Splatting (photorealistic, from photo)
 *   - Body: VRM rigged mesh (skeletal animation, clothing, hand IK)
 *   - Hair: 3DGS (photorealistic strands) or VRM mesh (animated)
 *   - Neck boundary: alpha-blended seam with depth-based compositing
 *
 * Expression pipeline:
 *   - Face 3DGS: per-region splat affine transforms (Design A)
 *   - Body VRM: blend shapes + skeletal FK/IK (Design B)
 *   - Sync: head bone transform drives face splat rigid transform
 *
 * Photo → VTuber pipeline (Murakumo):
 *   1. Photo → R2 upload
 *   2. Murakumo qwen3.5-4b (VL) → face analysis (landmarks, skin tone, eye color, hair)
 *   3. Murakumo wai-real-mix-v11 (SDXL) → 8-view turnaround renders
 *   4. Mac Mini fleet → 3DGS face reconstruction (gsplat)
 *   5. Face region segmentation → eyes/brows/jaw/mouth/cheeks/nose regions
 *   6. VL analysis → VRM body generation (appearance params → VRoid SDK or procedural)
 *   7. Face .splat + region map + body .vrm → R2
 *   8. KAMI hybrid render: PBR pass (body VRM) + Splat pass (face 3DGS)
 *
 * Usage in app.ts:
 *   import { buildHybridVTuberScene } from "@etzhayyim/kotodama-host-sdk/kami-vtuber-hybrid";
 *   const scene = buildHybridVTuberScene({
 *     faceSplatKey: "avatar-face.splat",
 *     faceRegionMapKey: "avatar-face-regions.json",
 *     bodyVRMKey: "avatar-body.vrm",
 *     tracking: { source: "mediapipe", lipSync: true },
 *   });
 *
 * @module
 */

import type { SplatRegion, SplatTrackingConfig, SplatExpressionPreset } from "./kami-vtuber-splat.js";
import type { VRMTrackingConfig, VRMVTuberMaterialOverride, EmotionPreset, ARKitBlendShape } from "./kami-vtuber-vrm.js";
import type { SdfBodyPartConfig } from "./kami-character-sdf.js";

/** Hybrid render mode for the face-body boundary. */
export type BoundaryBlendMode =
  | "depthComposite"    // Depth buffer compositing (sharp boundary)
  | "alphaGradient"     // Alpha gradient at neck seam (smooth blend)
  | "stencilMask";      // Stencil buffer masking (clean separation)

/** Hybrid VTuber face configuration (3DGS). */
export interface HybridFaceConfig {
  /** R2 CDN blob key for face .splat file. */
  splatKey: string;
  /** R2 CDN blob key for face region map JSON (SplatRegion[]). */
  regionMapKey: string;
  /** Face position offset relative to head bone [x, y, z] (default: [0, 0, 0.02]). */
  positionOffset?: [number, number, number];
  /** Face scale (default: auto-calibrated from VRM head bone). */
  scale?: number;
  /** Splat sort interval in ms (default: 16 = 60fps). */
  sortIntervalMs?: number;
}

/** Hybrid VTuber body configuration (VRM mesh). */
export interface HybridBodyConfig {
  /** R2 CDN blob key for body VRM/GLB (headless — face mesh excluded). */
  vrmKey: string;
  /** Material overrides for body sub-meshes. */
  materialOverrides?: VRMVTuberMaterialOverride[];
  /** Enable SSS for skin materials (default: true). */
  skinSSS?: boolean;
  /** Enable anisotropic hair shading (default: true). */
  anisotropicHair?: boolean;
}

/** Hybrid VTuber hair configuration. */
export interface HybridHairConfig {
  /** Hair rendering mode. */
  mode: "splat" | "vrm" | "sdf";
  /** R2 blob key for hair .splat (when mode="splat"). */
  splatKey?: string;
  /** SDF hair strand configs (when mode="sdf"). */
  sdfParts?: SdfBodyPartConfig[];
  /** Hair is part of body VRM (when mode="vrm") — no separate config needed. */
}

/** Unified tracking config for hybrid avatar. */
export interface HybridTrackingConfig {
  /** Face tracking input source. */
  source: "mediapipe" | "mocopi" | "livelink" | "manual";
  /** Enable lip-sync from audio (default: false). */
  lipSync?: boolean;
  /** Lip-sync audio source. */
  lipSyncSource?: "microphone" | "audioElement";
  /** Enable auto-blink (default: true). */
  autoBlink?: boolean;
  /** Auto-blink interval in ms (default: 3500). */
  autoBlinkIntervalMs?: number;
  /** Blend shape smoothing factor 0-1 (default: 0.6). */
  smoothingFactor?: number;
  /** Enable hand tracking (default: false). */
  handTracking?: boolean;
  /** Enable full body pose (default: false). */
  bodyPose?: boolean;
  /**
   * Face-body sync mode:
   *   - "boneDriven": head bone transform drives face splat position (default)
   *   - "independent": face and body track independently
   */
  faceSyncMode?: "boneDriven" | "independent";
}

/** Full hybrid VTuber configuration. */
export interface HybridVTuberConfig {
  /** Face configuration (3DGS). */
  face: HybridFaceConfig;
  /** Body configuration (VRM). */
  body: HybridBodyConfig;
  /** Hair configuration (optional, defaults to VRM hair). */
  hair?: HybridHairConfig;
  /** Display name. */
  name?: string;
  /** Unified tracking configuration. */
  tracking?: HybridTrackingConfig;
  /** Emotion presets. */
  emotionPresets?: EmotionPreset[];
  /** Expression presets for splat face. */
  splatExpressionPresets?: SplatExpressionPreset[];
  /** Face-body boundary blend mode (default: "alphaGradient"). */
  boundaryBlendMode?: BoundaryBlendMode;
  /** Camera distance (default: 2.5). */
  cameraDistance?: number;
  /** Camera height offset (default: 0.1). */
  cameraHeightOffset?: number;
  /** Background color [r,g,b]. */
  backgroundColor?: [number, number, number];
  /** Idle breathing amplitude (default: 0.003). */
  idleBreathingAmplitude?: number;
  /** SDF marching cubes resolution for SDF hair (default: 96). */
  sdfResolution?: number;
}

/**
 * Build KAMI IslandScene JSON for Hybrid VTuber avatar.
 *
 * Three-pass rendering:
 *   Pass 1: PBR (body VRM + optional SDF hair) — depth write + color
 *   Pass 2: Gaussian Splat (face + optional splat hair) — depth read, alpha blend
 *   Pass 3: Boundary composite — alpha gradient seam at neck
 *
 * Tracking data flow:
 *   MediaPipe (JS)
 *     → 52 ARKit blend shape weights
 *     → Split:
 *       → Face splat: ARKit → SplatRegionTransform[] (per-region affine)
 *       → Body VRM: ARKit → blend shape weights (morph targets)
 *     → Head pose (rotation + translation)
 *       → Drive face splat rigid transform (boneDriven sync)
 *       → Drive body VRM head bone
 */
export function buildHybridVTuberScene(config: HybridVTuberConfig): Record<string, unknown> {
  const bg = config.backgroundColor ?? [0.05, 0.04, 0.07];
  const camDist = config.cameraDistance ?? 2.5;
  const camH = config.cameraHeightOffset ?? 0.1;
  const tracking = config.tracking ?? { source: "mediapipe" };
  const hair = config.hair ?? { mode: "vrm" as const };
  const boundaryMode = config.boundaryBlendMode ?? "alphaGradient";

  const entities: Record<string, unknown>[] = [];

  // Entity: Body VRM (PBR pass, depth write)
  entities.push({
    id: "vtuber-body",
    position: [0.0, 0.0, 0.0],
    rotation: [0.0, 0.0, 0.0, 1.0],
    scale: [1.0, 1.0, 1.0],
    mesh: {
      type: "asset",
      assetId: config.body.vrmKey,
      blobKey: config.body.vrmKey,
    },
    components: [
      { type: "playerSpawn" },
      {
        type: "trigger",
        kind: "vrmVtuberBody",
        data: JSON.stringify({
          // Tracking (body portion)
          trackingSource: tracking.source,
          handTracking: tracking.handTracking ?? false,
          bodyPose: tracking.bodyPose ?? false,
          smoothingFactor: tracking.smoothingFactor ?? 0.6,
          // Materials
          skinSss: config.body.skinSSS ?? true,
          anisotropicHair: config.body.anisotropicHair ?? true,
          // Animation
          idleBreathingAmplitude: config.idleBreathingAmplitude ?? 0.003,
          // Boundary
          boundaryBlendMode: boundaryMode,
          // This body provides the head bone transform for face sync
          providesHeadBone: true,
        }),
      },
    ],
  });

  // Entity: Face 3DGS (Splat pass, depth read + alpha blend)
  const faceOffset = config.face.positionOffset ?? [0.0, 0.0, 0.02];
  const faceScale = config.face.scale ?? 0.2;
  entities.push({
    id: "vtuber-face",
    position: faceOffset,
    rotation: [0.0, 0.0, 0.0, 1.0],
    scale: [faceScale, faceScale, faceScale],
    mesh: {
      type: "gaussianSplat",
      splatKey: config.face.splatKey,
    },
    components: [
      {
        type: "trigger",
        kind: "splatVtuberFace",
        data: JSON.stringify({
          regionMapKey: config.face.regionMapKey,
          trackingSource: tracking.source,
          lipSync: tracking.lipSync ?? false,
          lipSyncSource: tracking.lipSyncSource ?? "microphone",
          autoBlink: tracking.autoBlink ?? true,
          autoBlinkIntervalMs: tracking.autoBlinkIntervalMs ?? 3500,
          sortIntervalMs: config.face.sortIntervalMs ?? 16,
          // Face-body sync
          faceSyncMode: tracking.faceSyncMode ?? "boneDriven",
          headBoneEntity: "vtuber-body",
          // Expression presets
          expressionPresets: config.splatExpressionPresets ?? [],
          emotionPresets: config.emotionPresets ?? [],
          // Boundary
          boundaryBlendMode: boundaryMode,
        }),
      },
    ],
  });

  // Entity: Hair (mode-dependent)
  if (hair.mode === "splat" && hair.splatKey) {
    entities.push({
      id: "vtuber-hair",
      position: [0.0, 0.0, 0.0],
      rotation: [0.0, 0.0, 0.0, 1.0],
      scale: [1.0, 1.0, 1.0],
      mesh: {
        type: "gaussianSplat",
        splatKey: hair.splatKey,
      },
      components: [
        {
          type: "trigger",
          kind: "splatHair",
          data: JSON.stringify({
            headBoneEntity: "vtuber-body",
            sortIntervalMs: 16,
          }),
        },
      ],
    });
  } else if (hair.mode === "sdf" && hair.sdfParts) {
    const toSceneParts = (parts: SdfBodyPartConfig[]) =>
      parts.map((p) => ({
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

    entities.push({
      id: "vtuber-hair-sdf",
      position: [0.0, 0.0, 0.0],
      rotation: [0.0, 0.0, 0.0, 1.0],
      scale: [1.0, 1.0, 1.0],
      mesh: {
        type: "sdfCharacter",
        resolution: config.sdfResolution ?? 96,
        bodyParts: toSceneParts(hair.sdfParts),
      },
      components: [],
    });
  }
  // hair.mode === "vrm": hair is part of body VRM, no separate entity needed

  // Floor
  entities.push({
    id: "floor",
    position: [0.0, -0.01, 0.0],
    rotation: [0.0, 0.0, 0.0, 1.0],
    scale: [6.0, 0.02, 6.0],
    mesh: { type: "cube", color: [bg[0] * 2, bg[1] * 2, bg[2] * 2, 1.0] },
    components: [],
  });

  return {
    "@context": "https://etzhayyim.com/ns/kami/scene",
    "@type": "IslandScene",
    name: config.name ?? "Hybrid VTuber",
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
    entities,
    characters: [],
  };
}
