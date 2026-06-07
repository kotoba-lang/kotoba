/**
 * KAMI VTuber SDK — Design B: VRM/glTF Rigged Mesh + ARKit Blend Shapes
 *
 * Industry-standard VTuber pipeline: VRM humanoid rig + 52 ARKit blend shapes.
 * MediaPipe Face Landmarker → blend shape weights → GPU compute morph targets.
 * VRoid Studio / Ready Player Me / UniVRM 互換.
 *
 * Pipeline:
 *   1. Photo upload → R2
 *   2. Murakumo qwen3.5-4b (VL) → face analysis → parametric appearance
 *   3. Murakumo fleet → wai-real-mix-v11 (SDXL) multi-view → VRM generation
 *   4. VRM (glTF + humanoid rig + blend shapes) → R2
 *   5. KAMI kami-gltf loader + kami-skeleton + GPU blend shape compute
 *   6. MediaPipe → 52 ARKit blend shapes → GPU morph → 60fps
 *
 * Requires KAMI engine extensions:
 *   - kami-skeleton: HumanoidRig (VRM 1.0 compatible 55-bone mapping)
 *   - kami-render: blendShape.wgsl compute shader
 *   - kami-render: gpuSkinning.wgsl compute shader
 *   - kami-web: MediaPipe face landmarker JS integration
 *
 * Usage in app.ts:
 *   import { buildVRMVTuberScene } from "@etzhayyim/kotodama-host-sdk/kami-vtuber-vrm";
 *   const scene = buildVRMVTuberScene({
 *     blobKey: "avatar.vrm",
 *     tracking: { source: "mediapipe" },
 *   });
 *
 * @module
 */

/**
 * ARKit-compatible blend shape names (Apple ARKit 52 shapes).
 * Used by MediaPipe FaceLandmarker outputFaceBlendshapes.
 */
export const ARKIT_BLEND_SHAPES = [
  // Eyes (12)
  "eyeBlinkLeft", "eyeBlinkRight",
  "eyeLookDownLeft", "eyeLookDownRight",
  "eyeLookInLeft", "eyeLookInRight",
  "eyeLookOutLeft", "eyeLookOutRight",
  "eyeLookUpLeft", "eyeLookUpRight",
  "eyeSquintLeft", "eyeSquintRight",
  "eyeWideLeft", "eyeWideRight",
  // Jaw (2)
  "jawForward", "jawLeft", "jawRight", "jawOpen",
  // Mouth (19)
  "mouthClose", "mouthFunnel", "mouthPucker",
  "mouthLeft", "mouthRight",
  "mouthSmileLeft", "mouthSmileRight",
  "mouthFrownLeft", "mouthFrownRight",
  "mouthDimpleLeft", "mouthDimpleRight",
  "mouthStretchLeft", "mouthStretchRight",
  "mouthRollLower", "mouthRollUpper",
  "mouthShrugLower", "mouthShrugUpper",
  "mouthPressLeft", "mouthPressRight",
  "mouthLowerDownLeft", "mouthLowerDownRight",
  "mouthUpperUpLeft", "mouthUpperUpRight",
  // Brow (5)
  "browDownLeft", "browDownRight",
  "browInnerUp",
  "browOuterUpLeft", "browOuterUpRight",
  // Cheek (4)
  "cheekPuff", "cheekSquintLeft", "cheekSquintRight",
  // Nose (2)
  "noseSneerLeft", "noseSneerRight",
  // Tongue (1)
  "tongueOut",
] as const;

/** Type for ARKit blend shape name. */
export type ARKitBlendShape = typeof ARKIT_BLEND_SHAPES[number];

/** VRM 1.0 humanoid bone names (55 bones). */
export const VRM_HUMANOID_BONES = [
  "hips", "spine", "chest", "upperChest", "neck", "head",
  "leftEye", "rightEye", "jaw",
  "leftShoulder", "leftUpperArm", "leftLowerArm", "leftHand",
  "rightShoulder", "rightUpperArm", "rightLowerArm", "rightHand",
  "leftUpperLeg", "leftLowerLeg", "leftFoot", "leftToes",
  "rightUpperLeg", "rightLowerLeg", "rightFoot", "rightToes",
  // Fingers (30)
  "leftThumbMetacarpal", "leftThumbProximal", "leftThumbDistal",
  "leftIndexProximal", "leftIndexIntermediate", "leftIndexDistal",
  "leftMiddleProximal", "leftMiddleIntermediate", "leftMiddleDistal",
  "leftRingProximal", "leftRingIntermediate", "leftRingDistal",
  "leftLittleProximal", "leftLittleIntermediate", "leftLittleDistal",
  "rightThumbMetacarpal", "rightThumbProximal", "rightThumbDistal",
  "rightIndexProximal", "rightIndexIntermediate", "rightIndexDistal",
  "rightMiddleProximal", "rightMiddleIntermediate", "rightMiddleDistal",
  "rightRingProximal", "rightRingIntermediate", "rightRingDistal",
  "rightLittleProximal", "rightLittleIntermediate", "rightLittleDistal",
] as const;

/** Viseme (mouth shape for lip-sync) mapping to ARKit blend shapes. */
export interface VisemeMapping {
  /** MPEG-4 viseme ID (0-14). */
  visemeId: number;
  /** Viseme name (e.g. "sil", "aa", "ee", "oh", "oo"). */
  name: string;
  /** Blend shape weights to apply. */
  weights: Partial<Record<ARKitBlendShape, number>>;
}

/** Standard 15 visemes for lip-sync (MPEG-4 compliant). */
export const VISEME_MAP: VisemeMapping[] = [
  { visemeId: 0, name: "sil", weights: {} },
  { visemeId: 1, name: "aa", weights: { jawOpen: 0.7, mouthLowerDownLeft: 0.3, mouthLowerDownRight: 0.3 } },
  { visemeId: 2, name: "ee", weights: { mouthSmileLeft: 0.5, mouthSmileRight: 0.5, jawOpen: 0.15 } },
  { visemeId: 3, name: "ih", weights: { mouthSmileLeft: 0.3, mouthSmileRight: 0.3, jawOpen: 0.2 } },
  { visemeId: 4, name: "oh", weights: { jawOpen: 0.5, mouthFunnel: 0.6 } },
  { visemeId: 5, name: "oo", weights: { mouthPucker: 0.7, mouthFunnel: 0.4, jawOpen: 0.1 } },
  { visemeId: 6, name: "ss", weights: { mouthSmileLeft: 0.2, mouthSmileRight: 0.2, jawOpen: 0.05 } },
  { visemeId: 7, name: "sh", weights: { mouthPucker: 0.4, mouthFunnel: 0.3, jawOpen: 0.1 } },
  { visemeId: 8, name: "ff", weights: { mouthUpperUpLeft: 0.3, mouthUpperUpRight: 0.3, mouthClose: 0.2 } },
  { visemeId: 9, name: "th", weights: { tongueOut: 0.4, jawOpen: 0.15 } },
  { visemeId: 10, name: "nn", weights: { mouthClose: 0.5, jawOpen: 0.05 } },
  { visemeId: 11, name: "rr", weights: { mouthPucker: 0.3, jawOpen: 0.2 } },
  { visemeId: 12, name: "dd", weights: { jawOpen: 0.2, mouthClose: 0.3 } },
  { visemeId: 13, name: "kk", weights: { jawOpen: 0.25, mouthStretchLeft: 0.2, mouthStretchRight: 0.2 } },
  { visemeId: 14, name: "pp", weights: { mouthClose: 0.8, mouthPressLeft: 0.3, mouthPressRight: 0.3 } },
];

/** Emotion preset — named blend shape weight sets. */
export interface EmotionPreset {
  name: string;
  /** Blend weights applied additively over tracking input. */
  weights: Partial<Record<ARKitBlendShape, number>>;
  /** Transition duration in ms (default: 300). */
  transitionMs?: number;
}

/** Standard emotion presets for VTuber expressions. */
export const EMOTION_PRESETS: EmotionPreset[] = [
  { name: "neutral", weights: {} },
  { name: "happy", weights: { mouthSmileLeft: 0.7, mouthSmileRight: 0.7, cheekSquintLeft: 0.3, cheekSquintRight: 0.3, eyeSquintLeft: 0.2, eyeSquintRight: 0.2 }, transitionMs: 400 },
  { name: "sad", weights: { mouthFrownLeft: 0.5, mouthFrownRight: 0.5, browInnerUp: 0.6, browDownLeft: 0.3, browDownRight: 0.3 }, transitionMs: 600 },
  { name: "surprised", weights: { eyeWideLeft: 0.8, eyeWideRight: 0.8, browInnerUp: 0.7, browOuterUpLeft: 0.6, browOuterUpRight: 0.6, jawOpen: 0.5 }, transitionMs: 200 },
  { name: "angry", weights: { browDownLeft: 0.7, browDownRight: 0.7, noseSneerLeft: 0.4, noseSneerRight: 0.4, jawForward: 0.2, mouthPressLeft: 0.3, mouthPressRight: 0.3 }, transitionMs: 300 },
  { name: "disgusted", weights: { noseSneerLeft: 0.6, noseSneerRight: 0.6, mouthFrownLeft: 0.4, mouthFrownRight: 0.4, browDownLeft: 0.3, browDownRight: 0.3, mouthUpperUpLeft: 0.3, mouthUpperUpRight: 0.3 }, transitionMs: 400 },
  { name: "wink", weights: { eyeBlinkLeft: 1.0, mouthSmileLeft: 0.3, mouthSmileRight: 0.5 }, transitionMs: 150 },
];

/** VRM VTuber tracking configuration. */
export interface VRMTrackingConfig {
  /** Input source for face tracking. */
  source: "mediapipe" | "mocopi" | "livelink" | "manual";
  /** Enable lip-sync from audio input (default: false). */
  lipSync?: boolean;
  /** Lip-sync audio source: microphone or audio element. */
  lipSyncSource?: "microphone" | "audioElement";
  /** Enable auto-blink when tracking is active (default: true). */
  autoBlink?: boolean;
  /** Auto-blink interval in ms (default: 3500). */
  autoBlinkIntervalMs?: number;
  /** Smoothing factor for blend shape transitions (0-1, default: 0.6). */
  smoothingFactor?: number;
  /** Enable hand tracking via MediaPipe Hands (default: false). */
  handTracking?: boolean;
  /** Enable body pose from MediaPipe Pose (default: false). */
  bodyPose?: boolean;
}

/** VRM VTuber material override. */
export interface VRMVTuberMaterialOverride {
  meshName: string;
  preset: "skin" | "hair" | "eye" | "lip" | "fabric" | "clearcoat";
  params?: Record<string, unknown>;
}

/** Full VRM VTuber avatar configuration. */
export interface VRMVTuberConfig {
  /** R2 CDN blob key for VRM/GLB file (with humanoid rig + blend shapes). */
  blobKey: string;
  /** Display name. */
  name?: string;
  /** Tracking input configuration. */
  tracking?: VRMTrackingConfig;
  /** Material overrides per sub-mesh. */
  materialOverrides?: VRMVTuberMaterialOverride[];
  /** Initial blend shape weights. */
  initialBlendShapes?: Partial<Record<ARKitBlendShape, number>>;
  /** Emotion presets (default: EMOTION_PRESETS). */
  emotionPresets?: EmotionPreset[];
  /** Camera distance (default: 2.5). */
  cameraDistance?: number;
  /** Camera height offset (default: 0.1). */
  cameraHeightOffset?: number;
  /** Background color [r,g,b]. */
  backgroundColor?: [number, number, number];
  /** Enable SSS for skin materials (default: true). */
  skinSSS?: boolean;
  /** Enable anisotropic hair shading (default: true). */
  anisotropicHair?: boolean;
  /** Idle animation: breathing bob amplitude (default: 0.003). */
  idleBreathingAmplitude?: number;
}

/**
 * Build KAMI IslandScene JSON for VRM VTuber avatar.
 *
 * Rendering pipeline:
 *   1. kami-gltf loads VRM/GLB (vertices + bones + blend shape deltas)
 *   2. blendShape.wgsl: compute shader interpolates morph target deltas
 *   3. gpuSkinning.wgsl: compute shader applies bone transforms
 *   4. pbr.wgsl: PBR fragment with SSS (skin) + anisotropic (hair) + clearcoat (eye)
 *
 * Tracking pipeline (JS → WASM):
 *   1. MediaPipe FaceLandmarker (JS) → 52 blend shape coefficients
 *   2. wasm-bindgen callback → setBlendWeights(Float32Array)
 *   3. ECS BlendShapeWeights component updated → GPU compute dispatch
 *   4. Optional: Web Audio FFT → viseme → lip sync blend shapes
 */
export function buildVRMVTuberScene(config: VRMVTuberConfig): Record<string, unknown> {
  const bg = config.backgroundColor ?? [0.06, 0.05, 0.08];
  const camDist = config.cameraDistance ?? 2.5;
  const camH = config.cameraHeightOffset ?? 0.1;
  const tracking = config.tracking ?? { source: "mediapipe" };

  return {
    "@context": "https://etzhayyim.com/ns/kami/scene",
    "@type": "IslandScene",
    name: config.name ?? "VRM VTuber",
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
      { id: "bounce", position: [0.0, 0.1, 1.5], color: [0.9, 0.85, 0.75], intensity: 0.5, range: 4.0, castShadow: false },
    ],
    entities: [
      {
        id: "vtuber-vrm",
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
            kind: "vrmVtuber",
            data: JSON.stringify({
              // Tracking
              trackingSource: tracking.source,
              lipSync: tracking.lipSync ?? false,
              lipSyncSource: tracking.lipSyncSource ?? "microphone",
              autoBlink: tracking.autoBlink ?? true,
              autoBlinkIntervalMs: tracking.autoBlinkIntervalMs ?? 3500,
              smoothingFactor: tracking.smoothingFactor ?? 0.6,
              handTracking: tracking.handTracking ?? false,
              bodyPose: tracking.bodyPose ?? false,
              // Materials
              skinSss: config.skinSSS ?? true,
              anisotropicHair: config.anisotropicHair ?? true,
              // Animation
              idleBreathingAmplitude: config.idleBreathingAmplitude ?? 0.003,
              // Blend shapes
              initialBlendShapes: config.initialBlendShapes ?? {},
              // Camera
              cameraDistance: camDist,
              cameraHeight: camH,
              // Emotion presets
              emotionPresets: (config.emotionPresets ?? EMOTION_PRESETS).map((p) => ({
                name: p.name,
                weights: p.weights,
                transitionMs: p.transitionMs ?? 300,
              })),
            }),
          },
        ],
      },
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
