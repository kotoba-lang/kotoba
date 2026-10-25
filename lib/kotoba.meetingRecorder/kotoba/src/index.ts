/**
 * meeting-recorder kotoba — barrel. WAVE 2 maximal migration (kotoba-E2E
 * split, ADR-2605181100): plaintext provider catalog + four E2E per-person
 * record kinds (session / recordingChunk / transcriptSegment / meetingMinutes).
 * Minutes 議事録 are generated from transcript segments by the deterministic
 * extractive generator (hermetic) or by Murakumo LLM (G4 Murakumo-only,
 * refused-by-default membrane). Recorder-bot join/capture execution, GPU/MLX
 * whisper inference, B2 media-blob custody, and consentToken custody stay
 * etzhayyim via consent-capability.
 */
export * from "./types.js";
export {
  registerProvider,
  getProvider,
  listProviders,
  recordSession,
  getSession,
  listSessions,
  recordChunk,
  listChunks,
  recordSegment,
  listSegments,
  coverage,
} from "./registry.js";
export {
  generateMinutes,
  getMinutes,
  listMinutes,
  countMinutes,
  extractiveMinutes,
  murakumoMinutes,
  LIVE_LLM_GATE_ENV,
} from "./minutes.js";
