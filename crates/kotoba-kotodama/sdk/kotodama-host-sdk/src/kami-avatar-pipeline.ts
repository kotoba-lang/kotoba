/**
 * KAMI Avatar Pipeline — Murakumo Photo→VTuber 3D Generation
 *
 * Orchestrates the full pipeline from a single photo to a deployable VTuber avatar
 * using Murakumo's distributed compute infrastructure (Mac Mini MLX fleet).
 *
 * Architecture:
 *   Photo → R2 → Murakumo CoordinatorDO → DAG pipeline → R2 artifacts → KAMI render
 *
 * 7-Stage DAG Pipeline:
 *   Stage 1: VL Analysis     — qwen3.5-4b (VL) face landmark + appearance extraction
 *   Stage 2: Multi-View Gen  — wai-real-mix-v11 (SDXL) turnaround views (8 angles)
 *   Stage 3: 3DGS Recon      — 3D Gaussian Splatting reconstruction from views
 *   Stage 4: Region Segment  — face region segmentation for expression control
 *   Stage 5: VRM Body Gen    — parametric body generation from VL appearance
 *   Stage 6: Asset Assembly   — combine face .splat + body .vrm + region map
 *   Stage 7: Quality Check   — qwen3.5-4b (VL) verification of generated avatar
 *
 * Usage in app.ts:
 *   import { submitAvatarGeneration, getAvatarStatus } from "@etzhayyim/kotodama-host-sdk/kami-avatar-pipeline";
 *
 *   // Submit photo for avatar generation
 *   const jobId = await submitAvatarGeneration(sdk, {
 *     photoR2Key: "uploads/user-photo.jpg",
 *     outputMode: "hybrid",  // "splat" | "vrm" | "hybrid"
 *     style: "photorealistic",
 *   });
 *
 *   // Poll status (or receive via handleCommit)
 *   const status = await getAvatarStatus(sdk, jobId);
 *   // status.stage = "regionSegment", status.progress = 0.6
 *   // status.artifacts = { faceSplatKey: "...", bodyVrmKey: "...", regionMapKey: "..." }
 *
 * @module
 */

import { resolveModelId } from "./llm-model-registry.js";

/** Avatar generation output mode. */
export type AvatarOutputMode =
  | "splat"   // Full 3DGS avatar (Design A) — highest visual fidelity
  | "vrm"     // Full VRM rigged mesh (Design B) — best animation support
  | "hybrid"; // 3DGS face + VRM body (Design C) — balanced

/** Avatar generation style. */
export type AvatarStyle =
  | "photorealistic"  // Faithful to photo (default)
  | "anime"           // Stylized anime look
  | "semiRealistic"; // Slightly stylized

/** VL-extracted face analysis result. */
export interface FaceAnalysis {
  /** Detected face landmarks (MediaPipe 468-point format). */
  landmarks?: number[][];
  /** Skin tone HSL [hue, saturation, lightness]. */
  skinTone: [number, number, number];
  /** Eye color HSL. */
  eyeColor: [number, number, number];
  /** Hair color HSL. */
  hairColor: [number, number, number];
  /** Hair style classification. */
  hairStyle: "short" | "medium" | "long" | "buzz" | "curly" | "wavy" | "spiky" | "ponytail" | "bun" | "bald" | "afro";
  /** Face shape classification. */
  faceShape: "round" | "oval" | "square" | "heart" | "long" | "diamond";
  /** Estimated age range. */
  ageRange: [number, number];
  /** Estimated gender presentation. */
  genderPresentation: "feminine" | "masculine" | "androgynous";
  /** Accessories detected. */
  accessories: string[];
  /** Clothing visible. */
  clothing: { type: string; color: [number, number, number] }[];
}

/** Multi-view generation parameters. */
export interface MultiViewParams {
  /** Number of views to generate (default: 8). */
  viewCount: number;
  /** View angles in degrees (default: [0, 45, 90, 135, 180, 225, 270, 315]). */
  viewAngles: number[];
  /** Image resolution per view (default: 1024). */
  resolution: number;
  /** Generation model (default: "wai-real-mix-v11" — SDXL, best for identity-consistent turnaround). */
  model: string;
  /** Style prompt modifier. */
  stylePrompt: string;
}

/** 3DGS reconstruction parameters. */
export interface ReconstructionParams {
  /** Number of Gaussians (default: 200000 for face, 500000 for full body). */
  numGaussians: number;
  /** Training iterations (default: 30000). */
  iterations: number;
  /** SH degree (default: 3). */
  shDegree: number;
  /** Output format. */
  outputFormat: "splat" | "ply";
}

/** VRM body generation parameters. */
export interface BodyGenParams {
  /** Body build. */
  build: "slim" | "average" | "athletic" | "stocky" | "tall";
  /** Relative height (0.8-1.2). */
  height: number;
  /** Skin tone from face analysis. */
  skinTone: [number, number, number];
  /** Clothing style (uses VL-extracted clothing). */
  clothing: { type: string; color: [number, number, number] }[];
  /** Include blend shapes (default: true). */
  includeBlendShapes: boolean;
  /** Blend shape count (default: 52 ARKit). */
  blendShapeCount: number;
}

/** Avatar generation job configuration. */
export interface AvatarGenerationConfig {
  /** R2 blob key for the source photo. */
  photoR2Key: string;
  /** Output mode: splat, vrm, or hybrid (default: "hybrid"). */
  outputMode?: AvatarOutputMode;
  /** Visual style (default: "photorealistic"). */
  style?: AvatarStyle;
  /** Custom multi-view generation params. */
  multiViewParams?: Partial<MultiViewParams>;
  /** Custom reconstruction params. */
  reconstructionParams?: Partial<ReconstructionParams>;
  /** Custom body generation params (overrides VL-extracted). */
  bodyParams?: Partial<BodyGenParams>;
  /** DID of the avatar owner (for AT record association). */
  ownerDid?: string;
  /** Custom display name for the avatar. */
  displayName?: string;
}

/** Pipeline stage identifier. */
export type PipelineStage =
  | "pending"
  | "vlAnalysis"
  | "multiViewGen"
  | "reconstruction3dgs"
  | "regionSegment"
  | "vrmBodyGen"
  | "assetAssembly"
  | "qualityCheck"
  | "completed"
  | "failed";

/** Avatar generation job status. */
export interface AvatarJobStatus {
  /** Job ID. */
  jobId: string;
  /** Current pipeline stage. */
  stage: PipelineStage;
  /** Progress within current stage (0.0-1.0). */
  progress: number;
  /** Overall progress (0.0-1.0). */
  overallProgress: number;
  /** Face analysis result (available after stage 1). */
  faceAnalysis?: FaceAnalysis;
  /** Generated artifact keys (populated as stages complete). */
  artifacts: AvatarArtifacts;
  /** Error message if failed. */
  error?: string;
  /** Timestamps. */
  createdAt: string;
  updatedAt: string;
  /** Estimated time remaining in seconds. */
  estimatedSecondsRemaining?: number;
}

/** Generated avatar artifact R2 keys. */
export interface AvatarArtifacts {
  /** Multi-view renders (8 images). */
  multiViewKeys?: string[];
  /** Face 3DGS splat file. */
  faceSplatKey?: string;
  /** Full body 3DGS splat file (outputMode="splat"). */
  fullBodySplatKey?: string;
  /** Face region map JSON. */
  faceRegionMapKey?: string;
  /** Body VRM/GLB file (outputMode="vrm" or "hybrid"). */
  bodyVrmKey?: string;
  /** Hair splat file (outputMode="hybrid" with splat hair). */
  hairSplatKey?: string;
  /** Thumbnail preview. */
  thumbnailKey?: string;
  /** Quality check report. */
  qualityReportKey?: string;
}

/** Default multi-view generation parameters. */
const DEFAULT_MULTI_VIEW: MultiViewParams = {
  viewCount: 8,
  viewAngles: [0, 45, 90, 135, 180, 225, 270, 315],
  resolution: 1024,
  model: "wai-real-mix-v11",
  stylePrompt: "",
};

/** Default reconstruction parameters. */
const DEFAULT_RECONSTRUCTION: ReconstructionParams = {
  numGaussians: 200000,
  iterations: 30000,
  shDegree: 3,
  outputFormat: "splat",
};

/** Style-specific prompt modifiers for multi-view generation. */
const STYLE_PROMPTS: Record<AvatarStyle, string> = {
  photorealistic: "photorealistic, high detail, studio lighting, neutral background, 8k",
  anime: "anime style, cel shading, clean lines, vibrant colors, neutral background",
  semiRealistic: "semi-realistic, slightly stylized, soft lighting, neutral background",
};

/**
 * Build VL analysis prompt for face extraction.
 *
 * Sent to Murakumo qwen3-vl with the source photo.
 */
export function buildFaceAnalysisPrompt(): string {
  return `Analyze this face photo and extract the following attributes as JSON:
{
  "skinTone": [hue01, saturation01, lightness01],
  "eyeColor": [hue01, saturation01, lightness01],
  "hairColor": [hue01, saturation01, lightness01],
  "hairStyle": "short|medium|long|buzz|curly|wavy|spiky|ponytail|bun|bald|afro",
  "faceShape": "round|oval|square|heart|long|diamond",
  "ageRange": [minAge, maxAge],
  "genderPresentation": "feminine|masculine|androgynous",
  "accessories": ["glasses", "earring", ...],
  "clothing": [{"type": "tankTop", "color": [h, s, l]}, ...]
}
Only return the JSON object, no explanation.`;
}

/**
 * Build multi-view generation prompt for a given angle.
 *
 * Uses face analysis to maintain consistency across views.
 */
export function buildMultiViewPrompt(
  faceAnalysis: FaceAnalysis,
  angleDeg: number,
  style: AvatarStyle,
): string {
  const stylePrompt = STYLE_PROMPTS[style];
  const hairDesc = `${faceAnalysis.hairStyle} hair`;
  const skinDesc = `skin tone hsl(${Math.round(faceAnalysis.skinTone[0] * 360)}, ${Math.round(faceAnalysis.skinTone[1] * 100)}%, ${Math.round(faceAnalysis.skinTone[2] * 100)}%)`;

  const angleDesc =
    angleDeg === 0 ? "front view" :
    angleDeg === 90 ? "right profile view" :
    angleDeg === 180 ? "back view" :
    angleDeg === 270 ? "left profile view" :
    `${angleDeg} degree view`;

  return `Portrait of the same person, ${angleDesc}, ${hairDesc}, ${skinDesc}, ${faceAnalysis.faceShape} face shape, consistent identity, ${stylePrompt}, white background, bust shot`;
}

/**
 * Build the Murakumo DAG pipeline definition for avatar generation.
 *
 * The DAG is submitted to CoordinatorDO for distributed execution
 * across the Mac Mini fleet.
 */
export function buildAvatarPipelineDAG(
  config: AvatarGenerationConfig,
): Record<string, unknown> {
  const outputMode = config.outputMode ?? "hybrid";
  const style = config.style ?? "photorealistic";
  const mvParams = { ...DEFAULT_MULTI_VIEW, ...config.multiViewParams };
  const reconParams = { ...DEFAULT_RECONSTRUCTION, ...config.reconstructionParams };

  const stages: Record<string, unknown>[] = [
    // Stage 1: VL face analysis
    {
      id: "vlAnalysis",
      type: "VISION_INFERENCE",
      model: resolveModelId("qwen3.5-4b"),
      params: {
        photoR2Key: config.photoR2Key,
        prompt: buildFaceAnalysisPrompt(),
        outputFormat: "json",
      },
      dependsOn: [],
    },
    // Stage 2: Multi-view generation (parallel per angle)
    ...mvParams.viewAngles.map((angle, i) => ({
      id: `multi_view_${i}`,
      type: "IMAGE_GENERATION",
      model: mvParams.model,
      params: {
        angleDeg: angle,
        resolution: mvParams.resolution,
        style,
        stylePrompt: STYLE_PROMPTS[style],
        // Prompt is built at runtime using VL analysis output
        promptTemplate: "multiView",
        viewIndex: i,
      },
      dependsOn: ["vlAnalysis"],
    })),
    // Stage 3: 3DGS reconstruction
    {
      id: "reconstruction3dgs",
      type: "COMPUTE",
      params: {
        task: "gsplatReconstruct",
        numGaussians: reconParams.numGaussians,
        iterations: reconParams.iterations,
        shDegree: reconParams.shDegree,
        outputFormat: reconParams.outputFormat,
        scope: outputMode === "splat" ? "fullBody" : "faceOnly",
      },
      dependsOn: mvParams.viewAngles.map((_, i) => `multi_view_${i}`),
    },
    // Stage 4: Region segmentation (for expression control)
    {
      id: "regionSegment",
      type: "COMPUTE",
      params: {
        task: "faceRegionSegment",
        regions: [
          "leftEye", "rightEye",
          "leftBrow", "rightBrow",
          "nose", "mouth", "jaw",
          "leftCheek", "rightCheek",
          "forehead", "chin",
        ],
      },
      dependsOn: ["reconstruction3dgs"],
    },
  ];

  // Stage 5: VRM body generation (only for vrm/hybrid modes)
  if (outputMode === "vrm" || outputMode === "hybrid") {
    stages.push({
      id: "vrmBodyGen",
      type: "COMPUTE",
      params: {
        task: "vrmBodyGenerate",
        includeBlendShapes: true,
        blendShapeCount: 52,
        headless: outputMode === "hybrid", // No head mesh for hybrid mode
        bodyParams: config.bodyParams ?? {},
      },
      dependsOn: ["vlAnalysis"],
    });
  }

  // Stage 6: Asset assembly
  const assemblyDeps = ["reconstruction3dgs", "regionSegment"];
  if (outputMode === "vrm" || outputMode === "hybrid") {
    assemblyDeps.push("vrmBodyGen");
  }
  stages.push({
    id: "assetAssembly",
    type: "COMPUTE",
    params: {
      task: "avatarAssemble",
      outputMode: outputMode,
      displayName: config.displayName ?? "Avatar",
      ownerDid: config.ownerDid ?? "",
    },
    dependsOn: assemblyDeps,
  });

  // Stage 7: Quality check (VL verification)
  stages.push({
    id: "qualityCheck",
    type: "VISION_INFERENCE",
    model: resolveModelId("qwen3-vl-4b"),
    params: {
      task: "avatarQualityVerify",
      originalPhotoKey: config.photoR2Key,
      outputMode: outputMode,
    },
    dependsOn: ["assetAssembly"],
  });

  return {
    pipelineId: `avatar_gen_${Date.now()}`,
    pipelineType: "avatarGeneration",
    config: {
      outputMode: outputMode,
      style,
      photoR2Key: config.photoR2Key,
      ownerDid: config.ownerDid ?? "",
    },
    stages,
  };
}

/**
 * Submit avatar generation job to Murakumo.
 *
 * Creates a DAG pipeline in CoordinatorDO and returns the job ID.
 * Progress can be tracked via getAvatarStatus() or handleCommit subscription.
 *
 * @param sdk - Kotodama host SDK instance
 * @param config - Avatar generation configuration
 * @returns Job ID for tracking
 */
export async function submitAvatarGeneration(
  sdk: { pds: { createRecord: (kind: string, record: Record<string, unknown>) => Promise<string> } },
  config: AvatarGenerationConfig,
): Promise<string> {
  const dag = buildAvatarPipelineDAG(config);
  const jobId = `avt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

  const record = {
    id: jobId,
    pipeline: dag,
    photoR2Key: config.photoR2Key,
    outputMode: config.outputMode ?? "hybrid",
    style: config.style ?? "photorealistic",
    ownerDid: config.ownerDid ?? "",
    displayName: config.displayName ?? "Avatar",
    status: "pending" as const,
    createdAt: new Date().toISOString(),
    orgId: "anon",
    userId: "anon",
    actorId: "",
  };

  await sdk.pds.createRecord("avatarGenerationJob", record);
  return jobId;
}

/**
 * Get avatar generation job status.
 *
 * Queries the job record from yata graph.
 *
 * @param sdk - Kotodama host SDK instance (with createKyselyDb-compatible query bridge)
 * @param jobId - Job ID from submitAvatarGeneration
 * @returns Current job status
 */
export async function getAvatarStatus(
  sdk: { queryAvatarGenerationJob: (jobId: string) => Promise<AvatarJobStatus | null> },
  jobId: string,
): Promise<AvatarJobStatus | null> {
  return sdk.queryAvatarGenerationJob(jobId);
}

/**
 * Build KAMI scene from completed avatar generation artifacts.
 *
 * Automatically selects the appropriate scene builder based on output mode.
 */
export function buildSceneFromArtifacts(
  artifacts: AvatarArtifacts,
  outputMode: AvatarOutputMode,
  options?: {
    name?: string;
    tracking?: { source: "mediapipe" | "mocopi" | "manual" };
    backgroundColor?: [number, number, number];
  },
): Record<string, unknown> {
  // Dynamic imports would be used at runtime; here we inline the scene structure
  switch (outputMode) {
    case "splat":
      if (!artifacts.fullBodySplatKey || !artifacts.faceRegionMapKey) {
        throw new Error("Missing splat artifacts for Design A scene");
      }
      // Return Design A scene structure
      return {
        "@context": "https://etzhayyim.com/ns/kami/scene",
        "@type": "IslandScene",
        name: options?.name ?? "3DGS VTuber",
        avatarMode: "splat",
        artifacts,
        tracking: options?.tracking ?? { source: "mediapipe" },
      };

    case "vrm":
      if (!artifacts.bodyVrmKey) {
        throw new Error("Missing VRM artifacts for Design B scene");
      }
      return {
        "@context": "https://etzhayyim.com/ns/kami/scene",
        "@type": "IslandScene",
        name: options?.name ?? "VRM VTuber",
        avatarMode: "vrm",
        artifacts,
        tracking: options?.tracking ?? { source: "mediapipe" },
      };

    case "hybrid":
      if (!artifacts.faceSplatKey || !artifacts.faceRegionMapKey || !artifacts.bodyVrmKey) {
        throw new Error("Missing hybrid artifacts for Design C scene");
      }
      return {
        "@context": "https://etzhayyim.com/ns/kami/scene",
        "@type": "IslandScene",
        name: options?.name ?? "Hybrid VTuber",
        avatarMode: "hybrid",
        artifacts,
        tracking: options?.tracking ?? { source: "mediapipe" },
      };
  }
}
