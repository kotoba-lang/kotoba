import { etzhayyim_MM_768_SPACE_ID, type Modality } from "./embedding-768.js";

export type ProjectionKind =
  | "identity-768"
  | "truncate-mrl-or-pca"
  | "linear-adapter"
  | "mrl-or-linear-adapter";

export interface EmbeddingModelSpec {
  modelId: string;
  projectionId: string;
  nativeDimension: number;
  storedDimension: 768;
  supportedModalities: readonly Modality[];
  projectionKind: ProjectionKind;
}

export const EMBEDDING_MODELS = {
  bgeM3: {
    modelId: "bge-m3",
    projectionId: "bge-m3-to-etzhayyim-mm-768",
    nativeDimension: 1024,
    storedDimension: 768,
    supportedModalities: ["text", "pdf"],
    projectionKind: "truncate-mrl-or-pca",
  },
  openClip: {
    modelId: "openclip-vit-b-32",
    projectionId: "openclip-to-etzhayyim-mm-768",
    nativeDimension: 512,
    storedDimension: 768,
    supportedModalities: ["text", "image"],
    projectionKind: "linear-adapter",
  },
  qwen3Vl: {
    modelId: "qwen3-vl-embedding-2b",
    projectionId: "qwen3-vl-to-etzhayyim-mm-768",
    nativeDimension: 2048,
    storedDimension: 768,
    supportedModalities: ["text", "image", "video", "screenshot", "mixed"],
    projectionKind: "mrl-or-linear-adapter",
  },
  imageBind: {
    modelId: "imagebind-huge",
    projectionId: "imagebind-to-etzhayyim-mm-768",
    nativeDimension: 1024,
    storedDimension: 768,
    supportedModalities: ["text", "image", "video", "audio", "depth", "thermal", "imu"],
    projectionKind: "mrl-or-linear-adapter",
  },
} as const satisfies Record<string, EmbeddingModelSpec>;

export type EmbeddingModelKey = keyof typeof EMBEDDING_MODELS;

export function modelForModality(modality: Modality): EmbeddingModelSpec {
  if (modality === "text" || modality === "pdf") return EMBEDDING_MODELS.bgeM3;
  if (modality === "image") return EMBEDDING_MODELS.openClip;
  if (modality === "video" || modality === "screenshot" || modality === "mixed") {
    return EMBEDDING_MODELS.qwen3Vl;
  }
  return EMBEDDING_MODELS.imageBind;
}

export function assertModelSupportsModality(model: EmbeddingModelSpec, modality: Modality): void {
  if (!model.supportedModalities.includes(modality)) {
    throw new Error(`${model.modelId} does not support modality ${modality}`);
  }
}

export function embeddingSpaceId(): string {
  return etzhayyim_MM_768_SPACE_ID;
}
