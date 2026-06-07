/**
 * KAMI Character Maker SDK — VL analysis → parametric CharacterDef → mesh generation.
 *
 * Pipeline: photo → qwen3.5-4b VL → CharacterDef JSON → kami-character (Rust) → GLB → R2
 *
 * Maps 1:1 to WIT etzhayyim:kami/character-maker and Rust kami-character crate.
 *
 * @module
 */

/** Face shape parameters (0.0–1.0 continuous). */
export interface FaceShapeParams {
  jawWidth: number;
  jawLength: number;
  chinShape: number;
  cheekboneWidth: number;
  cheekboneHeight: number;
  foreheadHeight: number;
  foreheadWidth: number;
  templeWidth: number;
  faceLength: number;
}

/** Eye parameters. */
export interface EyeParams {
  size: number;
  width: number;
  height: number;
  spacing: number;
  tilt: number;
  depth: number;
  irisSize: number;
  irisColor: [number, number, number];
}

/** Nose parameters. */
export interface NoseParams {
  length: number;
  width: number;
  bridgeHeight: number;
  tipShape: number;
  tipAngle: number;
  nostrilWidth: number;
}

/** Mouth/lip parameters. */
export interface MouthParams {
  width: number;
  upperLipThickness: number;
  lowerLipThickness: number;
  cornerAngle: number;
  philtrumDepth: number;
  lipColor: [number, number, number];
}

/** Eyebrow parameters. */
export interface BrowParams {
  thickness: number;
  archHeight: number;
  spacing: number;
  angle: number;
  color: [number, number, number];
}

/** Skin parameters. */
export interface SkinParams {
  tone: [number, number, number];
  roughness: number;
  subsurface: number;
  freckles: number;
  blemishes: number;
}

/** Hair preset. */
export type HairPreset =
  | "short-straight" | "short-wavy" | "short-curly"
  | "medium-straight" | "medium-wavy" | "medium-layered"
  | "long-straight" | "long-wavy" | "long-curly"
  | "ponytail-high" | "ponytail-low" | "bun-top" | "bun-low"
  | "bob" | "pixie" | "buzz" | "undercut" | "mohawk"
  | "afro-short" | "afro-large"
  | "braids-twin" | "braids-single"
  | "bald";

/** Hair parameters. */
export interface HairParams {
  preset: HairPreset;
  color: [number, number, number];
  highlightColor?: [number, number, number];
  lengthScale: number;
  volume: number;
  partPosition: number;
  shininess: number;
}

/** Clothing preset. */
export type ClothingPreset =
  | "tank-top" | "t-shirt" | "blouse" | "hoodie" | "jacket"
  | "dress-casual" | "dress-formal"
  | "suit-casual" | "suit-formal"
  | "uniform-school" | "uniform-military"
  | "nude-shoulders";

/** Clothing parameters. */
export interface ClothingParams {
  preset: ClothingPreset;
  color: [number, number, number];
  secondaryColor?: [number, number, number];
  fit: number;
}

/** Body parameters. */
export interface BodyParams {
  height: number;
  shoulderWidth: number;
  build: number;
  neckThickness: number;
}

/** Complete character definition — all continuous parameters. */
export interface CharacterDef {
  face: FaceShapeParams;
  eyes: EyeParams;
  nose: NoseParams;
  mouth: MouthParams;
  brows: BrowParams;
  skin: SkinParams;
  hair: HairParams;
  clothing: ClothingParams;
  body: BodyParams;
}

/** Default CharacterDef matching the reference photo (young feminine, blonde, blue eyes). */
export const DEFAULT_CHARACTER_DEF: CharacterDef = {
  face: { jawWidth: 0.4, jawLength: 0.5, chinShape: 0.3, cheekboneWidth: 0.55, cheekboneHeight: 0.6, foreheadHeight: 0.5, foreheadWidth: 0.5, templeWidth: 0.5, faceLength: 0.6 },
  eyes: { size: 0.7, width: 0.6, height: 0.55, spacing: 0.5, tilt: 0.1, depth: 0.5, irisSize: 0.8, irisColor: [0.45, 0.65, 0.85] },
  nose: { length: 0.4, width: 0.35, bridgeHeight: 0.45, tipShape: 0.6, tipAngle: 0.55, nostrilWidth: 0.35 },
  mouth: { width: 0.55, upperLipThickness: 0.5, lowerLipThickness: 0.55, cornerAngle: 0.15, philtrumDepth: 0.5, lipColor: [0.85, 0.62, 0.62] },
  brows: { thickness: 0.35, archHeight: 0.5, spacing: 0.5, angle: 0.1, color: [0.65, 0.55, 0.42] },
  skin: { tone: [0.94, 0.87, 0.82], roughness: 0.45, subsurface: 0.6, freckles: 0.0, blemishes: 0.0 },
  hair: { preset: "long-straight", color: [0.92, 0.85, 0.70], highlightColor: [0.95, 0.90, 0.78], lengthScale: 1.0, volume: 0.6, partPosition: 0.5, shininess: 0.5 },
  clothing: { preset: "tank-top", color: [0.95, 0.95, 0.95], fit: 0.5 },
  body: { height: 1.0, shoulderWidth: 0.4, build: 0.3, neckThickness: 0.35 },
};

/**
 * Build VL prompt to extract CharacterDef from a photo.
 * Returns the system + user prompt for qwen3.5-4b.
 */
export function buildCharacterExtractionPrompt(): { system: string; user: string } {
  return {
    system: `You are a character appearance analyzer. Given a photo of a person, extract parametric character definition as JSON. All numeric values are 0.0-1.0 normalized unless noted. Colors are RGB [0-1].`,
    user: `Analyze this photo and output a CharacterDef JSON with these fields:
{
  "face": { "jawWidth": 0-1, "jawLength": 0-1, "chinShape": 0-1 (0=pointed,1=square), "cheekboneWidth": 0-1, "cheekboneHeight": 0-1, "foreheadHeight": 0-1, "foreheadWidth": 0-1, "templeWidth": 0-1, "faceLength": 0-1 (0=round,1=long) },
  "eyes": { "size": 0.5-1.5, "width": 0-1, "height": 0-1, "spacing": 0-1, "tilt": -0.5-0.5 (neg=droopy,pos=cat), "depth": 0-1, "irisSize": 0.5-1.5, "irisColor": [r,g,b] },
  "nose": { "length": 0-1, "width": 0-1, "bridgeHeight": 0-1, "tipShape": 0-1 (0=pointed,1=button), "tipAngle": 0-1 (0=down,1=upturned), "nostrilWidth": 0-1 },
  "mouth": { "width": 0-1, "upperLipThickness": 0-1, "lowerLipThickness": 0-1, "cornerAngle": -0.5-0.5, "philtrumDepth": 0-1, "lipColor": [r,g,b] },
  "brows": { "thickness": 0-1, "archHeight": 0-1, "spacing": 0-1, "angle": -0.5-0.5, "color": [r,g,b] },
  "skin": { "tone": [r,g,b], "roughness": 0-1, "subsurface": 0-1, "freckles": 0-1, "blemishes": 0-1 },
  "hair": { "preset": "long-straight|short-wavy|...", "color": [r,g,b], "lengthScale": 0.5-1.5, "volume": 0-1, "partPosition": 0-1 (0=left,1=right), "shininess": 0-1 },
  "clothing": { "preset": "tank-top|t-shirt|...", "color": [r,g,b], "fit": 0-1 },
  "body": { "height": 0.8-1.2, "shoulderWidth": 0-1, "build": 0-1, "neckThickness": 0-1 }
}
Return ONLY the JSON object.`,
  };
}

/**
 * Build KAMI scene JSON from a CharacterDef (for preview rendering).
 */
export function buildCharacterPreviewScene(def: CharacterDef, glbBlobKey: string): Record<string, unknown> {
  const bg: [number, number, number] = [0.05, 0.04, 0.07];
  return {
    "@context": "https://etzhayyim.com/ns/kami/scene",
    "@type": "IslandScene",
    name: "Character Preview",
    genre: "social",
    maxPlayers: 1,
    cameraMode: "perspective",
    postfxPreset: "baminikuCharacter",
    ambientColor: [bg[0] * 0.7, bg[1] * 0.7, bg[2] * 0.7],
    sunDirection: [-0.5, -1.2, -0.8],
    sunIntensity: 0.8,
    sunColor: [1.0, 0.95, 0.9],
    shadow: { resolution: 2048, cascades: 2, softness: 2.0, bias: 0.004 },
    pointLights: [
      { id: "key", position: [-2, 2.5, 2], color: [1, 0.94, 0.88], intensity: 3.2, range: 12, castShadow: true },
      { id: "fill", position: [1.5, 2, 1.5], color: [0.75, 0.85, 1.0], intensity: 1.3, range: 10 },
      { id: "rim", position: [0, 3, -1.5], color: [0.9, 0.8, 1.0], intensity: 2.5, range: 8 },
      { id: "hair", position: [-0.3, 3.5, -0.5], color: [1, 0.95, 0.85], intensity: 1.8, range: 5 },
      { id: "bounce", position: [0, 0.1, 1.5], color: [0.9, 0.85, 0.75], intensity: 0.5, range: 4 },
    ],
    entities: [
      {
        id: "character",
        position: [0, 0, 0],
        rotation: [0, 0, 0, 1],
        scale: [1, 1, 1],
        mesh: { type: "asset", assetId: glbBlobKey, blobKey: glbBlobKey },
        components: [
          { type: "playerSpawn" },
          {
            type: "trigger",
            kind: "characterPreview",
            data: JSON.stringify({
              characterDef: def,
              autoRotate: true,
              idleBreathing: true,
              autoBlinkIntervalMs: 3500,
            }),
          },
        ],
      },
      {
        id: "floor",
        position: [0, -0.35, 0],
        rotation: [0, 0, 0, 1],
        scale: [4, 0.02, 4],
        mesh: { type: "cube", color: [bg[0] * 2, bg[1] * 2, bg[2] * 2, 1] },
        components: [],
      },
    ],
    characters: [],
  };
}
